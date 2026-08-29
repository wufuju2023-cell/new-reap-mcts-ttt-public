#!/usr/bin/env python3
"""policy_server — V1-1 主线实现 (0 long-train + on-demand RTTT)

- 直载 REAL-Prover (BF16, cuda:0)
- LoRA adapter init_lora_weights=False (等价 base, 零长训)
- 端点:
    GET  /health
    POST /v1/chat/completions   policy 采样: {prompt, n, temperature} -> [{text, logprob_avg}]
    POST /value                 value head: {prompt} -> {"score": float}
    POST /ttt_step              RTTT 一步: {items:[{prompt, target, r, logprob_old}]}
                                -> {"loss":..., "kl":..., "steps":1}  (adapter 自动 hot 保持)
    POST /adapter/snapshot      快照 {name} -> 保存 adapter 状态字典
    POST /adapter/restore       回滚 {name}
- 用法: nohup /opt/venv/bin/python /workspace/app/policy_server.py \
        --base /workspace/data/real-prover --port 8760 > /workspace/logs/policy.log 2>&1 &
"""
import argparse, json, io, math, os, threading, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model

try:
    from value_head import (
        ValueHead,
        clamp_target,
        last_token_hidden,
        load_value_head,
        model_hidden_size,
        proof_depth_to_target,
        save_value_head,
    )
except ImportError:  # package import (e.g. ``import app.policy_server``)
    from .value_head import (
        ValueHead,
        clamp_target,
        last_token_hidden,
        load_value_head,
        model_hidden_size,
        proof_depth_to_target,
        save_value_head,
    )

TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
BETA_KL = 0.05  # KL 防忘系数 (见 v1-spec 02)
DEFAULT_VALUE_LR = 3e-4
DEFAULT_POLICY_LR = 1e-4
DEFAULT_VALUE_COEFFICIENT = 0.5
DEFAULT_GAMMA = 0.99
DEFAULT_MAX_GRAD_NORM = 1.0
DEFAULT_MAX_DISTANCE = 64
MAX_TTT_ITEMS = 16

class Engine:
    """REAL-Prover policy + independently trainable scalar value head.

    The policy remains a PEFT LoRA model.  The value head is a small fp32 MLP
    over the backbone's final hidden state and is optimized in a separate
    parameter group.  ``value_head_path`` is optional; without it the head is
    intentionally random and the health response reports that fact.
    """

    def __init__(
        self,
        base_dir,
        device="cuda:0",
        lora_r=16,
        *,
        value_head_path=None,
        value_hidden_dim=256,
        value_lr=DEFAULT_VALUE_LR,
        policy_lr=DEFAULT_POLICY_LR,
        value_coefficient=DEFAULT_VALUE_COEFFICIENT,
        gamma=DEFAULT_GAMMA,
        max_grad_norm=DEFAULT_MAX_GRAD_NORM,
        value_output_mode="scalar",
        max_distance=DEFAULT_MAX_DISTANCE,
        output_dir="/workspace/out",
    ):
        if not 0.0 <= float(gamma) <= 1.0:
            raise ValueError("gamma must be in [0,1]")
        if float(value_lr) <= 0.0 or float(policy_lr) <= 0.0:
            raise ValueError("learning rates must be positive")
        if float(value_coefficient) < 0.0:
            raise ValueError("value_coefficient must be non-negative")
        if float(max_grad_norm) <= 0.0:
            raise ValueError("max_grad_norm must be positive")
        if value_output_mode not in {"scalar", "distance"}:
            raise ValueError("value_output_mode must be 'scalar' or 'distance'")
        if type(max_distance) is not int or max_distance < 1:
            raise ValueError("max_distance must be a positive integer")
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.gamma = float(gamma)
        self.value_coefficient = float(value_coefficient)
        self.max_grad_norm = float(max_grad_norm)
        self.value_output_mode = value_output_mode
        self.max_distance = int(max_distance)
        self.value_head_path = Path(value_head_path) if value_head_path else None
        self.value_head_loaded = False
        self.value_optimizer_steps = 0
        self.value_examples_seen = 0
        self._update_lock = threading.RLock()
        self.tok = AutoTokenizer.from_pretrained(base_dir)
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            base_dir, torch_dtype=torch.bfloat16, device_map=self.device)
        base.config.use_cache = True
        lora = LoraConfig(r=lora_r, lora_alpha=32, lora_dropout=0.02,
                          target_modules=TARGET_MODULES,
                          bias="none",
                          init_lora_weights=True)  # 零 B 初始化 => 等价 base
        self.model = get_peft_model(base, lora)
        self.model.eval()
        self.hidden_size = model_hidden_size(self.model)
        # Value head stays fp32 while the policy commonly runs in bf16.
        self.vhead = ValueHead(self.hidden_size, int(value_hidden_dim)).to(
            self.device, dtype=torch.float32
        )
        self.vhead.eval()
        policy_params = [p for p in self.model.parameters() if p.requires_grad]
        param_groups = []
        if policy_params:
            param_groups.append({"params": policy_params, "lr": float(policy_lr)})
        param_groups.append({"params": list(self.vhead.parameters()), "lr": float(value_lr)})
        # Keep a head-only optimizer for portable value_head.pt checkpoints.
        # ``self.opt`` remains the joint optimizer used by RTTT updates.
        self.value_opt = torch.optim.AdamW(self.vhead.parameters(), lr=float(value_lr))
        self.opt = torch.optim.AdamW(param_groups)
        if self.value_head_path is not None and self.value_head_path.is_file():
            metadata = load_value_head(
                self.value_head_path,
                self.vhead,
                self.value_opt,
                map_location=self.device,
            )
            checkpoint_metadata = metadata.get("metadata", {})
            checkpoint_mode = checkpoint_metadata.get("value_output_mode") if isinstance(checkpoint_metadata, dict) else None
            if checkpoint_mode is not None and checkpoint_mode != self.value_output_mode:
                raise ValueError(
                    "value-head checkpoint output mode does not match server "
                    f"({checkpoint_mode!r} != {self.value_output_mode!r})"
                )
            self.value_head_loaded = True
            self.value_optimizer_steps = int(metadata.get("optimizer_steps", 0))
            self.value_examples_seen = int(metadata.get("examples_seen", 0))
        elif self.value_head_path is not None:
            raise FileNotFoundError(f"value-head checkpoint not found: {self.value_head_path}")
        self.generated = 0

    def _encode(self, prompt):
        if not isinstance(prompt, str):
            raise ValueError("prompt must be a string")
        # An empty state is still representable by tokenizers that provide BOS
        # or an EOS fallback.  HTTP callers should normally send a non-empty
        # Lean state; accepting empty text keeps low-level smoke tests and
        # tokenizer-specific deployments from failing before model inference.
        return self.tok(prompt, return_tensors="pt").to(self.device)

    @staticmethod
    def _item_prompt(item):
        if not isinstance(item, dict):
            raise ValueError("training item must be an object")
        for key in ("prompt", "state", "state_pp"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value
        # Preserve an explicit empty prompt for tokenizer-level compatibility;
        # the tokenizer itself decides whether BOS/EOS can represent it.
        for key in ("prompt", "state", "state_pp"):
            if key in item and isinstance(item[key], str):
                return item[key]
        raise ValueError("training item requires prompt/state/state_pp")

    def _hidden_from_encoded(self, encoded, *, requires_grad=False):
        kwargs = dict(
            input_ids=encoded["input_ids"],
            attention_mask=encoded.get("attention_mask"),
            output_hidden_states=True,
            return_dict=True,
            use_cache=False,
        )
        # Some lightweight test doubles reject an explicit None mask.
        if kwargs["attention_mask"] is None:
            kwargs.pop("attention_mask")
        if requires_grad:
            out = self.model(**kwargs)
            return last_token_hidden(out, encoded.get("attention_mask"))
        was_training = self.model.training
        self.model.eval()
        try:
            with torch.no_grad():
                out = self.model(**kwargs)
                return last_token_hidden(out, encoded.get("attention_mask"))
        finally:
            self.model.train(was_training)

    def _raw_value(self, prompt):
        encoded = self._encode(prompt)
        self.vhead.eval()
        hidden = self._hidden_from_encoded(encoded, requires_grad=False)
        with torch.no_grad():
            value = self.vhead(hidden).reshape(-1)[0]
        if not bool(torch.isfinite(value).item()):
            raise FloatingPointError("value head returned a non-finite value")
        return float(value.detach().cpu())

    def generate(self, prompt, n=6, temperature=0.99, max_new_tokens=128):
        if type(n) is not int or n < 1 or n > 64:
            raise ValueError("n must be an integer in [1,64]")
        enc = self._encode(prompt)
        outs = self.model.generate(
            **enc,
            do_sample=True,
            temperature=max(float(temperature), 1e-5),
            num_return_sequences=n,
            max_new_tokens=int(max_new_tokens),
            pad_token_id=self.tok.pad_token_id,
            return_dict_in_generate=True,
            output_scores=False,
        )
        res = []
        for seq in outs.sequences:
            prompt_len = enc["input_ids"].shape[1]
            gen_ids = seq[prompt_len:]
            text = self.tok.decode(gen_ids, skip_special_tokens=True).split("\n")[0].strip()
            res.append({"text": text, "logprob_avg": 0.0})
        self.generated += n
        return res

    def value(self, prompt):
        """Return the configured Reap score.

        ``scalar`` returns ``-V(s)`` (the project's original contract).  The
        optional ``distance`` mode maps the bounded quality value to
        ``[1,max_distance]`` for nanoproof/verified-collector clients; those
        clients negate the JSON score exactly once on their side.
        """

        with self._update_lock:
            raw = self._raw_value(prompt)
        return self._score_from_raw(raw)

    def _score_from_raw(self, raw):
        raw = float(raw)
        if not math.isfinite(raw):
            raise FloatingPointError("value head returned a non-finite value")
        raw = max(-1.0, min(1.0, raw))
        mode = getattr(self, "value_output_mode", "scalar")
        max_distance = int(getattr(self, "max_distance", DEFAULT_MAX_DISTANCE))
        if mode == "distance":
            # V=+1 denotes the best state and V=-1 the worst state.  The
            # affine map gives the protocol's positive distance support.
            return 1.0 + (max_distance - 1.0) * (1.0 - raw) / 2.0
        return -raw

    def raw_value(self, prompt):
        """Return the learned critic value ``V(s)`` in ``[-1,1]``."""

        with self._update_lock:
            return self._raw_value(prompt)

    def _target_for_item(self, item):
        """Resolve an item into a bounded critic target.

        Priority is explicit ``value_target``/``return``; then a nanoproof
        ``proof_depth``; finally a one-step TD target from ``r``/``reward`` and
        optional ``next_prompt`` or ``next_value``.  ``r`` is retained as a
        fallback for the existing RTTT demo and is expected to be verifier
        normalized to ``[-1,1]``.
        """

        if not isinstance(item, dict):
            raise ValueError("each training item must be an object")
        target_kind = str(item.get("target_kind", "auto")).lower()
        if target_kind in {"proof_depth", "depth"}:
            depth = item.get("proof_depth", item.get("value_target", item.get("return")))
            if depth is not None:
                return proof_depth_to_target(depth, max_depth=int(item.get("max_depth", 64)))
        if target_kind in {"negative_proof_depth", "nanoproof"}:
            raw = item.get("value_target", item.get("return"))
            if raw is not None:
                raw = float(raw)
                return proof_depth_to_target(abs(raw), max_depth=int(item.get("max_depth", 64)))
        for key in ("value_target", "return", "td_target", "target_value"):
            if key in item and item[key] is not None:
                raw = float(item[key])
                # nanoproof replay stores negative remaining proof depth.  A
                # magnitude larger than one is unambiguously a depth; regular
                # scalar returns remain in [-1,1].
                if target_kind == "auto" and raw < -1.0:
                    return proof_depth_to_target(-raw, max_depth=int(item.get("max_depth", 64)))
                return clamp_target(raw, name=key)
        if "proof_depth" in item and item["proof_depth"] is not None:
            max_depth = int(item.get("max_depth", 64))
            return proof_depth_to_target(item["proof_depth"], max_depth=max_depth)
        reward = item.get("reward", item.get("r"))
        if reward is None:
            return None
        reward = clamp_target(reward, name="reward")
        done = bool(item.get("done", item.get("terminal", False)))
        next_value = item.get("next_value")
        if next_value is None and item.get("next_prompt") and not done:
            next_value = self._raw_value(item["next_prompt"])
        if next_value is not None and not done:
            next_value = clamp_target(next_value, name="next_value")
            reward = reward + self.gamma * next_value
        return clamp_target(reward, name="td_target")

    def _value_optimizer(self):
        """Return the head-only optimizer, including legacy test shells."""

        optimizer = getattr(self, "value_opt", None)
        if optimizer is None:
            optimizer = torch.optim.AdamW(self.vhead.parameters(), lr=DEFAULT_VALUE_LR)
            self.value_opt = optimizer
        return optimizer

    def _sync_value_optimizer_state(self):
        """Mirror joint-optimizer moments into the portable head optimizer."""

        value_optimizer = getattr(self, "value_opt", None)
        if value_optimizer is None:
            return
        for parameter in self.vhead.parameters():
            state = self.opt.state.get(parameter)
            if state is None:
                continue
            value_optimizer.state[parameter] = {
                key: value.detach().clone() if torch.is_tensor(value) else value
                for key, value in state.items()
            }

    def _save_value_head(self):
        if self.value_head_path is None:
            return None
        value_optimizer = self._value_optimizer()
        return save_value_head(
            self.value_head_path,
            self.vhead,
            value_optimizer,
            optimizer_steps=self.value_optimizer_steps,
            examples_seen=self.value_examples_seen,
            metadata={
                "hidden_size": self.hidden_size,
                "value_coefficient": self.value_coefficient,
                "gamma": self.gamma,
                "value_output_mode": getattr(self, "value_output_mode", "scalar"),
                "max_distance": int(getattr(self, "max_distance", DEFAULT_MAX_DISTANCE)),
            },
        )

    def train_value(self, items, *, epochs=1):
        """Head-only update for ``POST /value/train`` batches."""

        if not isinstance(items, list) or not items:
            raise ValueError("items must be a non-empty list")
        if type(epochs) is not int or epochs < 1 or epochs > 32:
            raise ValueError("epochs must be an integer in [1,32]")
        with self._update_lock:
            self.model.eval()
            self.vhead.train()
            total_loss = 0.0
            total_examples = 0
            last = None
            for _ in range(epochs):
                hidden, targets = [], []
                for item in items[:MAX_TTT_ITEMS]:
                    target = self._target_for_item(item)
                    if target is None:
                        continue
                    encoded = self._encode(self._item_prompt(item))
                    hidden.append(self._hidden_from_encoded(encoded, requires_grad=False).detach())
                    targets.append(target)
                if not targets:
                    raise ValueError("no value targets found in items")
                features = torch.cat(hidden, dim=0)
                target_tensor = torch.tensor(targets, device=self.device, dtype=torch.float32)
                value_optimizer = self._value_optimizer()
                value_optimizer.zero_grad(set_to_none=True)
                prediction = self.vhead(features)
                value_loss = torch.nn.functional.mse_loss(prediction, target_tensor)
                if not bool(torch.isfinite(value_loss).item()):
                    raise FloatingPointError("non-finite value loss")
                (self.value_coefficient * value_loss).backward()
                params = list(self.vhead.parameters())
                grad_norm = torch.nn.utils.clip_grad_norm_(params, self.max_grad_norm)
                if not bool(torch.isfinite(torch.as_tensor(grad_norm)).item()):
                    raise FloatingPointError("non-finite value gradient")
                value_optimizer.step()
                self.value_optimizer_steps += 1
                self.value_examples_seen += len(targets)
                total_loss += float(value_loss.detach().cpu())
                total_examples += len(targets)
                last = {
                    "value_loss": float(value_loss.detach().cpu()),
                    "value_prediction_mean": float(prediction.detach().mean().cpu()),
                    "value_target_mean": float(target_tensor.mean().cpu()),
                    "value_grad_norm": float(torch.as_tensor(grad_norm).detach().cpu()),
                }
            self.vhead.eval()
            if self._save_value_head() is not None:
                self.value_head_loaded = True
            return {
                "loss": total_loss / epochs,
                "value_loss": total_loss / epochs,
                "examples": total_examples,
                "steps": epochs,
                "optimizer_steps": self.value_optimizer_steps,
                **(last or {}),
            }

    def ttt_step(self, items):
        """联合 policy REINFORCE/KL 与 value MSE/TD 的一次更新。"""

        if not isinstance(items, list) or not items:
            return {"error": "empty items"}
        batch = items[:MAX_TTT_ITEMS]
        with self._update_lock:
            self.model.train()
            self.vhead.train()
            policy_params = [p for p in self.model.parameters() if p.requires_grad]
            params = policy_params + list(self.vhead.parameters())
            self.opt.zero_grad(set_to_none=True)
            policy_total = torch.zeros((), device=self.device, dtype=torch.float32)
            kl_total = torch.zeros((), device=self.device, dtype=torch.float32)
            value_total = torch.zeros((), device=self.device, dtype=torch.float32)
            value_predictions, value_targets = [], []
            trained_values = 0
            for it in batch:
                prompt = self._item_prompt(it)
                target_text = it.get("target", it.get("tactic", ""))
                enc = self._encode(prompt)
                if not isinstance(target_text, str) or not target_text:
                    raise ValueError("each policy item requires a non-empty target/tactic")
                tgt = self.tok(target_text + self.tok.eos_token, return_tensors="pt").to(self.device)
                input_ids = torch.cat([enc["input_ids"], tgt["input_ids"]], dim=1)
                attention = enc.get("attention_mask")
                if attention is not None:
                    attention = torch.cat([attention, torch.ones_like(tgt["input_ids"])], dim=1)
                labels = torch.full_like(input_ids, -100)
                labels[:, enc["input_ids"].shape[1]:] = tgt["input_ids"]
                kwargs = {"input_ids": input_ids, "labels": labels,
                          "output_hidden_states": True, "return_dict": True,
                          "use_cache": False}
                if attention is not None:
                    kwargs["attention_mask"] = attention
                out = self.model(**kwargs)
                nll = out.loss.float()
                logp = -nll
                # Policy log-probabilities are not value targets and may be
                # much smaller than -1; validate finiteness without clamping.
                logp_old = float(it.get("logprob_old", -12.0))
                if not math.isfinite(logp_old):
                    raise ValueError("logprob_old must be finite")
                reward = float(it.get("r", it.get("reward", 0.0)))
                if not math.isfinite(reward):
                    raise ValueError("reward must be finite")
                policy_loss = -reward * (logp - logp_old)
                kl = BETA_KL * (logp - logp_old).pow(2)
                policy_total = policy_total + policy_loss
                kl_total = kl_total + kl
                value_target = self._target_for_item(it)
                if value_target is not None:
                    prompt_position = enc["input_ids"].shape[1] - 1
                    value_hidden = out.hidden_states[-1][:, prompt_position, :].float()
                    prediction = self.vhead(value_hidden).reshape(-1)
                    target_tensor = torch.tensor([value_target], device=self.device, dtype=torch.float32)
                    value_total = value_total + torch.nn.functional.mse_loss(prediction, target_tensor)
                    value_predictions.append(float(prediction.detach().mean().cpu()))
                    value_targets.append(value_target)
                    trained_values += 1
            count = float(len(batch))
            total = (policy_total + kl_total + self.value_coefficient * value_total) / count
            if not bool(torch.isfinite(total).item()):
                raise FloatingPointError("non-finite total training loss")
            total.backward()
            if params:
                grad_norm = torch.nn.utils.clip_grad_norm_(params, self.max_grad_norm)
                if not bool(torch.isfinite(torch.as_tensor(grad_norm)).item()):
                    raise FloatingPointError("non-finite gradient norm")
            else:
                grad_norm = torch.tensor(0.0, device=self.device)
            self.opt.step()
            self._sync_value_optimizer_state()
            self.value_optimizer_steps += int(trained_values > 0)
            self.value_examples_seen += trained_values
            self.model.eval()
            self.vhead.eval()
            if self._save_value_head() is not None:
                self.value_head_loaded = True
            result = {
                "loss": float(total.detach().cpu()),
                "policy_loss": float((policy_total / count).detach().cpu()),
                "kl": float((kl_total / count).detach().cpu()),
                "value_loss": float((value_total / max(1.0, float(trained_values))).detach().cpu()) if trained_values else 0.0,
                "value_updates": trained_values,
                "value_prediction_mean": sum(value_predictions) / len(value_predictions) if value_predictions else None,
                "value_target_mean": sum(value_targets) / len(value_targets) if value_targets else None,
                "grad_norm": float(torch.as_tensor(grad_norm).detach().cpu()),
                "steps": len(batch),
                "optimizer_steps": self.value_optimizer_steps,
            }
            return result

    def snapshot(self, name):
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ValueError("snapshot name must be a non-empty file-safe string")
        path = self.output_dir / f"adapter_{name}.pt"
        payload = {
            "schema_version": "reap.policy-server.snapshot.v2",
            "hidden_size": self.hidden_size,
            "model": self.model.state_dict(),
            "value_head": self.vhead.state_dict(),
            "optimizer": self.opt.state_dict(),
            "value_optimizer": getattr(self, "value_opt", None).state_dict()
            if getattr(self, "value_opt", None) is not None else None,
            "value_optimizer_steps": self.value_optimizer_steps,
            "value_examples_seen": self.value_examples_seen,
            "value_output_mode": getattr(self, "value_output_mode", "scalar"),
            "max_distance": int(getattr(self, "max_distance", DEFAULT_MAX_DISTANCE)),
        }
        torch.save(payload, path)
        return f"snapshot:{name}"

    def restore(self, name):
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ValueError("snapshot name must be a non-empty file-safe string")
        path = self.output_dir / f"adapter_{name}.pt"
        try:
            payload = torch.load(path, map_location=self.device, weights_only=True)
        except TypeError:
            payload = torch.load(path, map_location=self.device)
        if isinstance(payload, dict) and payload.get("schema_version") == "reap.policy-server.snapshot.v2":
            if int(payload.get("hidden_size", -1)) != self.hidden_size:
                raise ValueError("snapshot hidden size does not match loaded model")
            current_mode = getattr(self, "value_output_mode", "scalar")
            current_max_distance = int(getattr(self, "max_distance", DEFAULT_MAX_DISTANCE))
            if payload.get("value_output_mode", current_mode) != current_mode:
                raise ValueError("snapshot value output mode does not match server")
            if int(payload.get("max_distance", current_max_distance)) != current_max_distance:
                raise ValueError("snapshot max distance does not match server")
            self.model.load_state_dict(payload["model"])
            self.vhead.load_state_dict(payload["value_head"])
            self.opt.load_state_dict(payload["optimizer"])
            value_optimizer = getattr(self, "value_opt", None)
            if value_optimizer is not None and isinstance(payload.get("value_optimizer"), dict):
                value_optimizer.load_state_dict(payload["value_optimizer"])
            self.value_optimizer_steps = int(payload.get("value_optimizer_steps", 0))
            self.value_examples_seen = int(payload.get("value_examples_seen", 0))
        elif isinstance(payload, dict):
            # Backward compatibility with the original skeleton's raw LoRA
            # state_dict snapshots; the value head remains unchanged.
            self.model.load_state_dict(payload)
        else:
            raise ValueError("invalid policy-server snapshot")
        self.model.eval()
        self.vhead.eval()
        return f"restored:{name}"

ENGINE = None

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    @staticmethod
    def _prompt(req):
        if not isinstance(req, dict):
            raise ValueError("request body must be a JSON object")
        for key in ("prompt", "state"):
            prompt = req.get(key)
            if isinstance(prompt, str) and prompt.strip():
                return prompt
        messages = req.get("messages", []) if isinstance(req, dict) else []
        if isinstance(messages, list):
            # Reap's OpenAIClient sends one user message.  Joining multiple
            # messages keeps this endpoint useful for ordinary OpenAI clients.
            parts = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                content = message.get("content", "")
                if isinstance(content, str) and content:
                    parts.append(content)
            if parts:
                return "\n".join(parts)
        raise ValueError("request requires a non-empty prompt or messages")

    @staticmethod
    def _value_chat(score, model="value-head"):
        # Lean's OpenAIClient parses assistant.content as JSON and then
        # negates score.  Keep the raw score finite and protocol-compatible.
        content = json.dumps({"score": float(score)}, separators=(",", ":"), allow_nan=False)
        return {
            "id": f"value-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
        }

    @staticmethod
    def _policy_chat(choices, model="policy"):
        """Return both the legacy ``text`` fields and OpenAI chat fields."""

        normalized = []
        for index, choice in enumerate(choices):
            text_value = str(choice.get("text", "")) if isinstance(choice, dict) else str(choice)
            row = dict(choice) if isinstance(choice, dict) else {"text": text_value}
            row.update({
                "index": index,
                "message": {"role": "assistant", "content": text_value},
                "finish_reason": "stop",
            })
            normalized.append(row)
        return {
            "id": f"policy-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "model": model,
            "choices": normalized,
        }

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {
                "ok": True,
                "device": str(ENGINE.device),
                "generated": ENGINE.generated,
                "hidden_size": ENGINE.hidden_size,
                "value_head": {
                    "kind": "linear-silu-linear-tanh",
                    "hidden_dim": ENGINE.vhead.hidden_dim,
                    "output_mode": ENGINE.value_output_mode,
                    "max_distance": ENGINE.max_distance,
                    "loaded": ENGINE.value_head_loaded,
                    "optimizer_steps": ENGINE.value_optimizer_steps,
                    "examples_seen": ENGINE.value_examples_seen,
                    "checkpoint": str(ENGINE.value_head_path) if ENGINE.value_head_path else None,
                },
                "adapter_loaded": "zero-init lora (0 long-train)",
            })
        else:
            self._json(404, {"error": self.path})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            path = self.path.split("?", 1)[0]
            is_value_chat = path.endswith("/value/chat/completions") or path.endswith("/value/v1/chat/completions")
            if is_value_chat:
                prompt = self._prompt(req)
                self._json(200, self._value_chat(ENGINE.value(prompt), req.get("model", "value-head")))
            elif path.endswith("/chat/completions"):
                prompt = self._prompt(req)
                outs = ENGINE.generate(prompt, n=req.get("n", 6),
                                       temperature=req.get("temperature", 0.99),
                                       max_new_tokens=req.get("max_tokens", 128))
                self._json(200, self._policy_chat(outs, req.get("model", "policy")))
            elif path.endswith("/value") or path.endswith("/value/"):
                self._json(200, {"score": ENGINE.value(self._prompt(req))})
            elif path.endswith("/value/train") or path.endswith("/value_head/train"):
                self._json(200, ENGINE.train_value(req.get("items", []), epochs=req.get("epochs", 1)))
            elif path.endswith("/ttt_step") or path.endswith("/ttt/step"):
                self._json(200, ENGINE.ttt_step(req.get("items", [])))
            elif path.endswith("/adapter/snapshot") or path.endswith("/snapshot"):
                self._json(200, {"result": ENGINE.snapshot(req.get("name", "t"))})
            elif path.endswith("/adapter/restore") or path.endswith("/restore"):
                self._json(200, {"result": ENGINE.restore(req.get("name", "t"))})
            else:
                self._json(404, {"error": path})
        except Exception as e:
            self._json(500, {"error": str(e)})

def main():
    global ENGINE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/workspace/data/real-prover")
    ap.add_argument("--port", type=int, default=8760)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--value-head", dest="value_head_path", default=None,
                    help="value-head checkpoint; defaults to /workspace/out/value_head.pt when present")
    ap.add_argument("--value-hidden-dim", type=int, default=256)
    ap.add_argument("--value-lr", type=float, default=DEFAULT_VALUE_LR)
    ap.add_argument("--policy-lr", type=float, default=DEFAULT_POLICY_LR)
    ap.add_argument("--value-coefficient", type=float, default=DEFAULT_VALUE_COEFFICIENT)
    ap.add_argument("--gamma", type=float, default=DEFAULT_GAMMA)
    ap.add_argument("--max-grad-norm", type=float, default=DEFAULT_MAX_GRAD_NORM)
    ap.add_argument("--value-output-mode", choices=("scalar", "distance"), default="scalar",
                    help="scalar=-V (project default); distance=positive [1,max-distance] for nanoproof/Reap collector")
    ap.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)
    ap.add_argument("--output-dir", default="/workspace/out")
    a = ap.parse_args()
    os.makedirs("/workspace/logs", exist_ok=True)
    value_path = a.value_head_path
    default_value_path = Path(a.output_dir) / "value_head.pt"
    if value_path is None:
        value_path = str(default_value_path) if default_value_path.is_file() else None
    print("[policy_server] loading base:", a.base)
    ENGINE = Engine(
        a.base,
        device=a.device,
        lora_r=a.lora_r,
        value_head_path=value_path,
        value_hidden_dim=a.value_hidden_dim,
        value_lr=a.value_lr,
        policy_lr=a.policy_lr,
        value_coefficient=a.value_coefficient,
        gamma=a.gamma,
        max_grad_norm=a.max_grad_norm,
        value_output_mode=a.value_output_mode,
        max_distance=a.max_distance,
        output_dir=a.output_dir,
    )
    # Even a fresh head should be persisted after its first update, matching
    # app/smoke.sh and app/archive.sh's artifact convention.
    if ENGINE.value_head_path is None:
        ENGINE.value_head_path = default_value_path
    print("[policy_server] ready on :%d (value head hidden=%d loaded=%s)" %
          (a.port, ENGINE.hidden_size, ENGINE.value_head_loaded))
    ThreadingHTTPServer(("0.0.0.0", a.port), H).serve_forever()

if __name__ == "__main__":
    main()
