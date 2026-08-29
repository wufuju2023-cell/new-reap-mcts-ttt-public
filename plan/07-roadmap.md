# 07. Roadmap

## Milestones

| Milestone | Deliverable | Machines | Est. |
|---|---|---|---|
| M0 | Build Reap (`lake build`), mock endpoints, `reap!!` end-to-end on a toy theorem, UI widget works | this laptop | 2–4 h |
| M1 | Dataset: pull `state_tactic_pairs`, filter via Lean parse/close, dedup, format JSONL; snapshot | laptop + 40 GB disk | 1 d |
| M2 | SFT small model (1.5B LoRA), serve vLLM w/ logprobs; golden unit test `mkPrompt` | rented 24 GB GPU | 0.5 d |
| M3 | Rollout harness: drive `reap` on FATE-M subset with gated logging; JSONL traces + solvability stats | GPU + laptop | 2–3 d |
| M4 | GRPO trainer + adapter hot-swap; 3 iterations on 200 theorems; record solve-rate before/after | GPU | 1–2 d |
| M5 | Value head (FastAPI) + PPO; rerun ablation A1/A2/A3/A4 | GPU | 3–5 d |
| M6 | Final eval matrix (06), report + repo write-up; open-source attempt | — | 2 d |
| M7 | Post-training (08): continuation from REAL-Prover (or 1.5B SFT) — P0 continue-SFT w/ replay, P1 GRPO warm start, P2 self-improvement | GPU | 5–7 d |
| M8 | Test-time training (09): per-theorem gradient steps on policy LoRA + value TD from API-call verdicts; serve+train colocated adapter server; TTT on/off ablation | GPU (24 GB) | 3–5 d |
| M9 | Batch solver: `Reap/Batch.lean` (no-UI), `solutions.jsonl` output | 本机 | 0.5 d |
| M10 | Evolution v1: mutate (const→var), well-typed, Diff ranking | GPU | 2–3 d |
| M11 | Closed loop §10: π_g → P_{g+1} → π_{g+1}, eval gate + KL guard | GPU | 5–7 d |
| M12 | Recursive self-improvement report (solve@B per generation) | — | 2 d |
| M13 | Curriculum baseline (§11): 20 hard goals × 20 "just-able" variants, Diff re-scaling closed loop, π_0→SFT→π_1, library growth stubs | GPU | 5–7 d |
| M14 | Two-model loop (§12): A=v0 teacher (existing LLM API, frozen), B=student reap batch solver; A→variants→Diff gate→B→traces→A DPO retrain; library L_g shared context | GPU | 7–10 d |

## Hardware decisions

- **Training/serving**: 1× 24 GB (RTX 4090/A10G-capable VPS) — 1.5B fits with
  margin; 3B close but fine with 4-bit.
- **Lean env**: this laptop (8 GB RAM WSL) — M0 smoke OK; mathlib build is the
  cost (~10+ GB deps). Prefer prebuilt latest release mathlib or use the
  laptop only for the harness repo (no `import Mathlib` in Reap itself — its
  deps are small; theorem eval happens in user projects).
- **Rollout runs**: must sit on the same file system as the trainer for
  logflow (or NFS/rclone; JSONL is small).

## Immediate next actions (do tonight)

1. `lake env lean` baseline: run `lake build` in the local Reap checkout.
2. Write `tools/mock_server/` (~100 lines): chat completions endpoint returning
   a canned tactic + random logprobs; value endpoint returning
   `{"score": 0.5}`; PS endpoint returning nothing (mocked).
3. Run one theorem from the README with `reap.policy_endpoint` → laptop
   mock, watch the progress widget; dump `raw_tree.json`; confirm
   `proofScriptForSolvedNode` works end-to-end.
4. Pin toolchain + commit `new-update-model/` as working notes.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| logprobs unsupported by some servers | vLLM native `logprobs`; fallback llama.cpp custom grammars; worst case: uniform prior (PUCT degrades, still usable) |
| Mathlib version drift | pin toolchain (`v4.28.0-rc1` family), record exact hash |
| value-model noise at 1B scale | baseline = no value; try head early; keep GRPO (critic-free) as primary |
| GPU budget | 1.5B at 4-bit: ~3–4 GB; use spot instances; batch rollouts |
| Reap relies on UI widget for proof output | for batch use call `reapMCTS`/`runMCTS` programmatically (async Tactic — same function), or parse raw tree |
| RL collapse (entropy collapse) | KL bonus $\beta\| \pi_\theta \| \pi_{ref} \|$, entropy floor, temperature of sampling during rollouts ~1.0 |
| TTT adapter tooling (vLLM no hot per-request LoRA) | TTT server = own FastAPI + `peft` (base frozen, LoRA forward/backward in-process); update every $k$ nodes, not every node |
| TTT leakage into eval | eval theorems always run from fresh base weights (or TTT measured separately) |
| Forgetting during post-training | replay old pairs (1:1) + KL anchor to checkpoint; eval gate before each stage |

## Who/what to read next

- `Reap/Tactic/Step.lean` (verifier semantics) — 15 min
- `Reap/Tactic/TreeSearch.lean:312–331` (PUCT numbers) — 10 min
- `Reap/Tactic/Generator.lean` (exact prompt + protocol) — 10 min
- `frenzymath/REAL-Prover/Realprover/README.md` (their rollout harness) — later
