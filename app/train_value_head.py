#!/usr/bin/env python3
"""离线训练 REAL-Prover 的独立 value head。

示例（GPU 容器内）：

    python /workspace/app/train_value_head.py \
        --base /workspace/data/real-prover \
        --data /workspace/out/value_train.jsonl \
        --output /workspace/out/value_head.pt \
        --epochs 3 --batch-size 8

输入 JSONL 至少需要 ``prompt``/``state``/``state_pp`` 之一，以及
``value_target``/``return``/``proof_depth`` 之一。``node_visited`` 记录可
直接使用，只要上游写入验证器回报；仅有 ``value.score`` 的记录默认会被
跳过，避免把随机或旧 value 预测当作监督标签。该脚本冻结 policy
backbone，只更新小型 MLP head，输出可由 ``policy_server.py --value-head``
加载的 checkpoint。
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Iterable

import torch

try:
    from value_head import (
        ValueHead,
        ValueHeadTrainer,
        clamp_target,
        discounted_returns,
        last_token_hidden,
        model_hidden_size,
        proof_depth_to_target,
    )
except ImportError:  # package import
    from .value_head import (
        ValueHead,
        ValueHeadTrainer,
        clamp_target,
        discounted_returns,
        last_token_hidden,
        model_hidden_size,
        proof_depth_to_target,
    )


def _prompt(record: dict[str, Any]) -> str | None:
    for key in ("prompt", "state", "state_pp"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _explicit_target(record: dict[str, Any], *, max_depth: int) -> float | None:
    kind = str(record.get("target_kind", "auto")).lower()
    if kind in {"proof_depth", "depth"}:
        depth = record.get("proof_depth", record.get("value_target", record.get("return")))
        if depth is not None:
            return proof_depth_to_target(depth, max_depth=max_depth)
    if kind in {"negative_proof_depth", "nanoproof"}:
        raw = record.get("value_target", record.get("return"))
        if raw is not None:
            raw = float(raw)
            return proof_depth_to_target(-raw if raw < 0 else raw, max_depth=max_depth)
    for key in ("value_target", "return", "td_target", "target_value"):
        if record.get(key) is not None:
            raw = float(record[key])
            # nanoproof replay commonly stores value_target=-proof_depth.  A
            # magnitude above one is therefore interpreted as a distance; a
            # normalized scalar return remains unchanged.
            if kind == "auto" and raw < -1.0:
                return proof_depth_to_target(-raw, max_depth=max_depth)
            return clamp_target(raw, name=key)
    if record.get("proof_depth") is not None:
        return proof_depth_to_target(record["proof_depth"], max_depth=max_depth)
    # A nested explicit target is accepted, but ``value.score`` is deliberately
    # not used: it is the Reap *score* (-V) and may have been produced by an
    # untrained head.  Use --allow-score only for controlled migrations.
    nested = record.get("value")
    if isinstance(nested, dict) and nested.get("target") is not None:
        return clamp_target(nested["target"], name="value.target")
    return None


def iter_examples(
    path: str | Path,
    *,
    max_depth: int = 64,
    allow_score: bool = False,
    include_binary_outcomes: bool = False,
) -> Iterable[tuple[str, float]]:
    """Yield ``(prompt, target)`` pairs from rollout JSONL records."""

    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(record, dict):
                continue

            # A trajectory record can contain parallel states/rewards arrays.
            states = record.get("states")
            rewards = record.get("rewards")
            if isinstance(states, list) and isinstance(rewards, list) and states:
                returns = discounted_returns(rewards, gamma=float(record.get("gamma", 0.99)))
                for state, target in zip(states, returns):
                    if isinstance(state, str) and state.strip():
                        yield state, target
                continue

            prompt = _prompt(record)
            if prompt is None:
                continue
            target = _explicit_target(record, max_depth=max_depth)
            if target is None and allow_score:
                nested = record.get("value")
                if isinstance(nested, dict) and nested.get("score") is not None:
                    # Reap receives score=-V and negates it in Generator.lean.
                    score = float(nested["score"])
                    target = (proof_depth_to_target(score, max_depth=max_depth)
                              if score > 1.0 else clamp_target(-score, name="value.score"))
            if target is None and include_binary_outcomes and "was_solved" in record:
                target = 1.0 if bool(record["was_solved"]) else -1.0
            if target is not None:
                yield prompt, target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="local REAL-Prover/HuggingFace model directory")
    parser.add_argument("--data", required=True, help="rollout JSONL file")
    parser.add_argument("--output", default="/workspace/out/value_head.pt")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--loss", choices=("mse", "huber"), default="mse")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-depth", type=int, default=64)
    parser.add_argument("--max-records", type=int, default=0, help="0 means all examples")
    parser.add_argument("--max-sequence-tokens", type=int, default=4096)
    parser.add_argument("--allow-score", action="store_true",
                        help="use nested value.score as -V (migration only)")
    parser.add_argument("--include-binary-outcomes", action="store_true",
                        help="use was_solved as +/-1 when no verified return exists")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.epochs < 1 or args.batch_size < 1:
        raise SystemExit("--epochs and --batch-size must be positive")
    if args.max_records < 0:
        raise SystemExit("--max-records must be non-negative")
    if args.max_sequence_tokens < 1:
        raise SystemExit("--max-sequence-tokens must be positive")

    examples = list(iter_examples(
        args.data,
        max_depth=args.max_depth,
        allow_score=args.allow_score,
        include_binary_outcomes=args.include_binary_outcomes,
    ))
    if args.max_records:
        examples = examples[:args.max_records]
    if not examples:
        raise SystemExit("no value-labelled examples found in the JSONL input")

    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    # Lazy import keeps --help and JSONL inspection usable without the GPU image.
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(args.base, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    backbone = AutoModelForCausalLM.from_pretrained(
        args.base, local_files_only=True, torch_dtype=dtype, low_cpu_mem_usage=True
    ).to(device)
    backbone.eval()
    for parameter in backbone.parameters():
        parameter.requires_grad_(False)
    hidden_size = model_hidden_size(backbone)
    head = ValueHead(hidden_size, args.hidden_dim).to(device, dtype=torch.float32)
    trainer = ValueHeadTrainer(
        head,
        learning_rate=args.learning_rate,
        loss=args.loss,
    )

    total_steps = 0
    for epoch in range(args.epochs):
        epoch_loss = 0.0
        batches = 0
        for start in range(0, len(examples), args.batch_size):
            rows = examples[start:start + args.batch_size]
            prompts = [row[0] for row in rows]
            targets = [row[1] for row in rows]
            encoded = tokenizer(prompts, return_tensors="pt", padding=True, truncation=False).to(device)
            sequence_length = int(encoded["input_ids"].shape[1])
            if sequence_length > args.max_sequence_tokens:
                raise SystemExit(
                    f"encoded prompt batch has {sequence_length} tokens, "
                    f"exceeding --max-sequence-tokens={args.max_sequence_tokens}; "
                    "shorten prompts explicitly instead of silently truncating"
                )
            with torch.no_grad():
                output = backbone(**encoded, output_hidden_states=True, use_cache=False, return_dict=True)
                hidden = last_token_hidden(output, encoded.get("attention_mask")).detach()
            metrics = trainer.update(hidden, targets)
            epoch_loss += metrics["loss"]
            batches += 1
            total_steps += 1
        mean_loss = epoch_loss / max(1, batches)
        print(json.dumps({
            "epoch": epoch + 1,
            "epochs": args.epochs,
            "examples": len(examples),
            "steps": total_steps,
            "loss": mean_loss,
            "hidden_size": hidden_size,
        }, ensure_ascii=False), flush=True)

    receipt = trainer.checkpoint(
        args.output,
        metadata={
            "source": str(Path(args.data)),
            "examples": len(examples),
            "epochs": args.epochs,
            "target_semantics": "verified discounted return in [-1,1]",
        },
    )
    print(json.dumps({"saved": receipt}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
