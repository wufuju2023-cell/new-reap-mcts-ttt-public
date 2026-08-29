"""可独立训练、保存和加载的 REAL-Prover value head。

该模块只依赖 PyTorch，不依赖 Transformers/PEFT，因此可以在 CPU 控制面
和 GPU 推理进程中复用。值头读取 policy backbone 的最后一个 hidden state，
输出归一化到 ``[-1, 1]`` 的连续状态价值。训练标签应使用验证器产生的
discounted return；如果上游记录的是 nanoproof 风格的剩余证明深度，可先用
``proof_depth_to_target`` 转换为归一化目标。
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor, nn
from torch.nn import functional as F


VALUE_HEAD_SCHEMA = "reap.value-head.v1"


class ValueHead(nn.Module):
    """Small MLP critic over a decoder-only model's final hidden state.

    ``hidden_states`` may be ``[batch, hidden]`` or ``[batch, seq, hidden]``.
    In the latter case the final sequence position is selected.  Padding-aware
    selection is available through :func:`last_token_hidden` before calling the
    head.
    """

    def __init__(self, hidden_size: int, hidden_dim: int = 256) -> None:
        super().__init__()
        if type(hidden_size) is not int or hidden_size <= 0:
            raise ValueError("hidden_size must be a positive integer")
        if type(hidden_dim) is not int or hidden_dim <= 0:
            raise ValueError("hidden_dim must be a positive integer")
        self.hidden_size = hidden_size
        self.hidden_dim = hidden_dim
        self.mlp = nn.Sequential(
            nn.Linear(hidden_size, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, 1),
            nn.Tanh(),
        )

    def forward(self, hidden_states: Tensor) -> Tensor:
        if not torch.is_tensor(hidden_states):
            raise TypeError("hidden_states must be a torch.Tensor")
        if hidden_states.ndim == 3:
            hidden_states = hidden_states[:, -1, :]
        if hidden_states.ndim != 2:
            raise ValueError("hidden_states must have shape [B,H] or [B,T,H]")
        if hidden_states.shape[-1] != self.hidden_size:
            raise ValueError(
                f"hidden size mismatch: expected {self.hidden_size}, "
                f"got {hidden_states.shape[-1]}"
            )
        # Keep the head in fp32 even when the policy backbone runs in bf16.
        return self.mlp(hidden_states.float()).squeeze(-1)


def model_hidden_size(model: Any) -> int:
    """Infer a model hidden size without assuming a particular HF architecture."""

    config = getattr(model, "config", None)
    for obj in (config, model):
        if obj is None:
            continue
        for name in ("hidden_size", "n_embd", "d_model", "n_embed"):
            value = getattr(obj, name, None)
            if isinstance(value, int) and value > 0:
                return int(value)
    embeddings = getattr(model, "get_input_embeddings", lambda: None)()
    value = getattr(embeddings, "embedding_dim", None)
    if isinstance(value, int) and value > 0:
        return int(value)
    raise ValueError("cannot infer model hidden size from config or embeddings")


def last_token_hidden(output: Any, attention_mask: Tensor | None = None) -> Tensor:
    """Return the last non-padding hidden state from a model output.

    The helper accepts both HuggingFace ``BaseModelOutput`` objects and simple
    dictionaries used by tests.  Selecting the maximum valid position works for
    both left- and right-padded batches.
    """

    hidden = getattr(output, "last_hidden_state", None)
    if hidden is None and isinstance(output, Mapping):
        hidden = output.get("last_hidden_state")
    if hidden is None:
        states = getattr(output, "hidden_states", None)
        if states is None and isinstance(output, Mapping):
            states = output.get("hidden_states")
        if not states:
            raise ValueError("model output does not contain hidden states")
        hidden = states[-1]
    if not torch.is_tensor(hidden) or hidden.ndim != 3:
        raise ValueError("hidden states must have shape [B,T,H]")
    if attention_mask is None:
        return hidden[:, -1, :]
    if (not torch.is_tensor(attention_mask) or attention_mask.ndim != 2
            or attention_mask.shape[:2] != hidden.shape[:2]):
        raise ValueError("attention_mask must have shape [B,T]")
    positions = torch.arange(hidden.shape[1], device=hidden.device).unsqueeze(0)
    positions = positions.expand(hidden.shape[0], -1)
    valid = attention_mask.to(dtype=torch.bool)
    # A malformed all-zero row is handled deterministically at position zero;
    # callers that require non-empty prompts should validate that upstream.
    last = torch.where(valid, positions, torch.zeros_like(positions)).amax(dim=1)
    rows = torch.arange(hidden.shape[0], device=hidden.device)
    return hidden[rows, last, :]


def finite_scalar(value: Any, name: str = "value") -> float:
    """Convert a scalar-like value to a finite Python float."""

    if torch.is_tensor(value):
        if value.numel() != 1:
            raise ValueError(f"{name} must contain exactly one scalar")
        value = value.detach().cpu().item()
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def clamp_target(value: Any, *, name: str = "value_target") -> float:
    """Validate and clamp a scalar return to the head's ``[-1,1]`` range."""

    return max(-1.0, min(1.0, finite_scalar(value, name)))


def discounted_returns(rewards: Sequence[Any], gamma: float = 0.99) -> list[float]:
    """Compute backward discounted returns and clip them to ``[-1,1]``."""

    gamma = finite_scalar(gamma, "gamma")
    if not 0.0 <= gamma <= 1.0:
        raise ValueError("gamma must be in [0,1]")
    result = [0.0] * len(rewards)
    running = 0.0
    for index in range(len(rewards) - 1, -1, -1):
        running = finite_scalar(rewards[index], f"rewards[{index}]") + gamma * running
        result[index] = max(-1.0, min(1.0, running))
    return result


def proof_depth_to_target(depth: Any, max_depth: int = 64) -> float:
    """Map a nanoproof-style remaining proof depth to a scalar target.

    nanoproof commonly stores a negative proof-depth *value_target* (terminal =
    0).  This helper accepts the non-negative depth magnitude; callers with a
    negative replay value should negate it first.  The scalar critic is bounded,
    so normalize by ``max_depth`` rather than passing an unbounded integer to
    MSE.  Depth zero is the best value (0.0).
    """

    depth_number = finite_scalar(depth, "proof_depth")
    if depth_number < 0:
        raise ValueError("proof_depth must be non-negative")
    if type(max_depth) is not int or max_depth <= 0:
        raise ValueError("max_depth must be a positive integer")
    return -min(depth_number, float(max_depth)) / float(max_depth)


def _cpu_state_dict(module: nn.Module) -> dict[str, Tensor]:
    return {name: tensor.detach().cpu().clone() for name, tensor in module.state_dict().items()}


def _optimizer_to(optimizer: torch.optim.Optimizer, device: torch.device | str) -> None:
    device = torch.device(device)
    for state in optimizer.state.values():
        for key, value in list(state.items()):
            if torch.is_tensor(value):
                state[key] = value.to(device)


def save_value_head(
    path: str | os.PathLike[str],
    head: ValueHead,
    optimizer: torch.optim.Optimizer | None = None,
    *,
    optimizer_steps: int = 0,
    examples_seen: int = 0,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically save a portable value-head checkpoint.

    Only the small head and optional optimizer state are written; the large
    policy backbone remains an external dependency.  This avoids accidentally
    replacing a policy checkpoint when saving frequent RTTT updates.
    """

    if not isinstance(head, ValueHead):
        raise TypeError("head must be a ValueHead")
    if type(optimizer_steps) is not int or optimizer_steps < 0:
        raise ValueError("optimizer_steps must be a non-negative integer")
    if type(examples_seen) is not int or examples_seen < 0:
        raise ValueError("examples_seen must be a non-negative integer")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": VALUE_HEAD_SCHEMA,
        "hidden_size": head.hidden_size,
        "hidden_dim": head.hidden_dim,
        "head": _cpu_state_dict(head),
        "optimizer_steps": optimizer_steps,
        "examples_seen": examples_seen,
        "metadata": dict(metadata or {}),
    }
    if optimizer is not None:
        payload["optimizer"] = optimizer.state_dict()
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
    )
    os.close(fd)
    try:
        torch.save(payload, temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "path": str(destination),
        "schema_version": VALUE_HEAD_SCHEMA,
        "hidden_size": head.hidden_size,
        "hidden_dim": head.hidden_dim,
        "optimizer_steps": optimizer_steps,
        "examples_seen": examples_seen,
    }


def load_value_head(
    path: str | os.PathLike[str],
    head: ValueHead,
    optimizer: torch.optim.Optimizer | None = None,
    *,
    map_location: str | torch.device = "cpu",
) -> dict[str, Any]:
    """Load a value-head checkpoint and validate its architecture metadata."""

    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"value-head checkpoint not found: {source}")
    try:
        payload = torch.load(source, map_location=map_location, weights_only=True)
    except TypeError:  # PyTorch < 2.6
        payload = torch.load(source, map_location=map_location)
    if not isinstance(payload, Mapping):
        raise ValueError("invalid value-head checkpoint payload")
    # Accept a raw state_dict for migration from the original skeleton, while
    # requiring metadata for checkpoints produced by this module.
    if "schema_version" not in payload and all(torch.is_tensor(v) for v in payload.values()):
        head.load_state_dict(payload, strict=True)
        return {"legacy": True, "path": str(source), "optimizer_loaded": False}
    if payload.get("schema_version") != VALUE_HEAD_SCHEMA:
        raise ValueError(
            f"unsupported value-head schema: {payload.get('schema_version')!r}"
        )
    if int(payload.get("hidden_size", -1)) != head.hidden_size:
        raise ValueError(
            f"value-head hidden size mismatch: checkpoint={payload.get('hidden_size')}, "
            f"model={head.hidden_size}"
        )
    if int(payload.get("hidden_dim", -1)) != head.hidden_dim:
        raise ValueError(
            f"value-head hidden dim mismatch: checkpoint={payload.get('hidden_dim')}, "
            f"model={head.hidden_dim}"
        )
    state = payload.get("head")
    if not isinstance(state, Mapping):
        raise ValueError("value-head checkpoint is missing head state")
    head.load_state_dict(state, strict=True)
    optimizer_loaded = False
    if optimizer is not None and isinstance(payload.get("optimizer"), Mapping):
        optimizer.load_state_dict(payload["optimizer"])
        _optimizer_to(optimizer, next(head.parameters()).device)
        optimizer_loaded = True
    return {
        "path": str(source),
        "schema_version": VALUE_HEAD_SCHEMA,
        "hidden_size": head.hidden_size,
        "hidden_dim": head.hidden_dim,
        "optimizer_steps": int(payload.get("optimizer_steps", 0)),
        "examples_seen": int(payload.get("examples_seen", 0)),
        "metadata": dict(payload.get("metadata") or {}),
        "optimizer_loaded": optimizer_loaded,
    }


class ValueHeadTrainer:
    """Head-only MSE/Huber trainer operating on precomputed hidden states."""

    def __init__(
        self,
        head: ValueHead,
        *,
        optimizer: torch.optim.Optimizer | None = None,
        learning_rate: float = 3e-4,
        loss: str = "mse",
        max_grad_norm: float = 1.0,
    ) -> None:
        if loss not in {"mse", "huber"}:
            raise ValueError("loss must be 'mse' or 'huber'")
        if not math.isfinite(float(learning_rate)) or learning_rate <= 0:
            raise ValueError("learning_rate must be positive and finite")
        if not math.isfinite(float(max_grad_norm)) or max_grad_norm <= 0:
            raise ValueError("max_grad_norm must be positive and finite")
        self.head = head
        self.optimizer = optimizer or torch.optim.AdamW(head.parameters(), lr=learning_rate)
        self.loss_name = loss
        self.max_grad_norm = float(max_grad_norm)
        self.optimizer_steps = 0
        self.examples_seen = 0

    def update(self, hidden_states: Tensor, targets: Tensor | Sequence[Any]) -> dict[str, float]:
        if not torch.is_tensor(hidden_states):
            hidden_states = torch.as_tensor(hidden_states)
        if hidden_states.ndim != 2 or hidden_states.shape[-1] != self.head.hidden_size:
            raise ValueError("hidden_states must have shape [B, head.hidden_size]")
        target_tensor = torch.as_tensor(
            targets, dtype=torch.float32, device=hidden_states.device
        ).reshape(-1)
        if target_tensor.numel() != hidden_states.shape[0]:
            raise ValueError("targets length must equal hidden_states batch size")
        target_tensor = target_tensor.clamp(-1.0, 1.0)
        self.head.train()
        self.optimizer.zero_grad(set_to_none=True)
        prediction = self.head(hidden_states)
        if self.loss_name == "mse":
            loss = F.mse_loss(prediction, target_tensor)
        else:
            loss = F.smooth_l1_loss(prediction, target_tensor)
        if not bool(torch.isfinite(loss).item()):
            raise FloatingPointError("non-finite value-head loss")
        loss.backward()
        parameters = [p for p in self.head.parameters() if p.grad is not None]
        if not parameters or not all(bool(torch.isfinite(p.grad).all().item()) for p in parameters):
            raise FloatingPointError("non-finite value-head gradient")
        grad_norm = torch.nn.utils.clip_grad_norm_(
            list(self.head.parameters()), self.max_grad_norm
        )
        if not bool(torch.isfinite(torch.as_tensor(grad_norm)).item()):
            raise FloatingPointError("non-finite value-head gradient norm")
        self.optimizer.step()
        if not all(bool(torch.isfinite(p).all().item()) for p in self.head.parameters()):
            raise FloatingPointError("non-finite value-head parameter")
        self.optimizer_steps += 1
        self.examples_seen += int(target_tensor.numel())
        return {
            "loss": float(loss.detach().cpu()),
            "prediction_mean": float(prediction.detach().mean().cpu()),
            "target_mean": float(target_tensor.detach().mean().cpu()),
            "grad_norm": float(torch.as_tensor(grad_norm).detach().cpu()),
            "optimizer_steps": float(self.optimizer_steps),
            "examples_seen": float(self.examples_seen),
        }

    def checkpoint(
        self, path: str | os.PathLike[str], *, metadata: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return save_value_head(
            path,
            self.head,
            self.optimizer,
            optimizer_steps=self.optimizer_steps,
            examples_seen=self.examples_seen,
            metadata=metadata,
        )
