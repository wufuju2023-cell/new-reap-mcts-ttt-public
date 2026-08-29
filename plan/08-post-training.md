# 08. Continued Training / Post-Training on Reap (不从头训练)

Goal: never train from scratch. Start from an existing policy (REAL-Prover 7B
**or** a Math-SFT small model) and let Reap's rollouts supply the "new"
experience that makes the model better at *this* search harness.

## 8.1 The three-stage continuation

### Stage P0 — continue-SFT (warm start with replay)

Take the base policy $\pi_{\theta_0}$ (HuggingFace `FrenzyMath/REAL-Prover`,
or our M2 small-SFT model) and continue training on a mix:

$$D_{\mathrm{P0}} = \underbrace{D_{\mathrm{pairs}}}_{\text{old: FrenzyMath/state}\_\text{tactic}\_\text{pairs}} \oplus \underbrace{D_{\mathrm{rollout}}}_{\text{new: Reap traces with hard labels}}$$

Loss (same as SFT, on masked tokens), plus replay weight $w_{\mathrm{old}}$
to prevent forgetting:

$$\mathcal{L}_{\mathrm{P0}} = -\mathbb{E}_{(s,a)\sim D_{\mathrm{pairs}}} w_{\mathrm{old}}\log \pi_\theta(a\mid s) \;-\; \mathbb{E}_{(s,a)\sim D_{\mathrm{rollout}}}\log \pi_\theta(a\mid s)$$

- Low lr (1e-5--5e-5), 1 epoch, LoRA or full (7B full = risky on 24 GB → LoRA first).
- The new part is **whose rollouts**: traces from `reap` MCTS under
  $\pi_{\theta_0}$ itself, kernel-verified by Reap's `checkProof` — i.e. the
  model learns the same distribution it will act in (distribution match).

### Stage P1 — RL from the warm start

Exactly §05 GRPO/PPO, but $\theta_{\mathrm{start}} = \theta_{\mathrm{P0}}$ and
optionally with anchor:

$$\mathcal{L} = \mathcal{L}_{\mathrm{RL}} + \beta\,\mathrm{KL}\big[\pi_\theta \| \pi_{\theta_{\mathrm{start}}}\big]$$

### Stage P2 — self-improvement (uses only Reap verdicts)

Sample *new* theorem statements (FATE-M leftover test split, Mathlib
statements), run Reap rollouts, and only keep **solver-produced** state–tactic
pairs (one LoRA pass). No human labels; the verifier is the labeler:
`replaySolvedNode` + `checkProof` already produce the full verified scripts.

## 8.2 Why continue (not from zero)

| Path | Cost | Expected | Risk |
|---|---|---|---|
| From random → SFT → RL | months of compute | low | policy can't even emit syntax-valid tactics |
| **From REAL-Prover → P0 → P1** | 1–2 wk GPU | high (state-of-art init) | fine-tune drift; license OK (Apache-2.0) |
| **From 1.5B SFT → P0 → P1** | 3–4 d GPU | medium | size ceiling; but exactly the "search-compensates" test |

Both "continued" paths reuse an existing checkpoint — zero starts.

## 8.3 Replay memory (avoid forgetting on rollouts)

Small replay buffer $B_{\mathrm{replay}}$ of 50k old pairs; ratio
$|\mathrm{rollout}|:|\mathrm{replay}| = 1:1$ per batch. Optional bonus:
anchor loss above acts as a "remember old policy" term.

## 8.4 Curriculum via Reap signals

Order training theorems by measured difficulty (Reap solve rate at budget
$B$): easy → medium → hard; warm it up on easy, then hard. Compute
difficulty *on the base policy once* (cheap at 64 nodes per theorem), then fix
the curriculum. Track K: rank of difficulty; stop at percentile

$$P_{\mathrm{diff}} = 80\%$$

## 8.5 Checkpoints & gates

- Gate before each stage: pass an eval set of 30 fixed theorems (solve@B with
  the **same** hyperparams as §06) above a threshold or undo.
- Always keep $\theta_0$ snapshot — RL updates can be destructive; rollback = copy.
- Mixing old pairs + new rollouts: keep replay ratio ≈ 0.5 on hard test
  extremes. Record every step's metadata in `run_meta.jsonl` (stage, lr,
  policy hash, per-theorem solve@B).
