# 06. Evaluation

## 6.1 Benchmarks

- **FATE-M** (from `frenzymath/REAL-Prover/Realprover/data/fate_m.jsonl`) —
  primary, matches the trained model's intended domain (algebra/research level).
- **ProofNet** — secondary community benchmark.
- Subsets of **Mathlib nlinarith/ring/star lemmas** (as in the README example)
  for quick smoke.

All with a fixed Lean toolchain pin and identical `max_nodes`/`max_steps`.

## 6.2 Metrics

Let $\mathcal{S}$ = eval set, $B$ = search budget:

$$\text{solve@}B = \frac{|\{p \in \mathcal{S}: \text{proof found} \le B\}|}{|\mathcal{S}|},$$

- mean proof script length (that Lean kernel-checked) — a proxy for "naturalness"
- wall-clock per solved theorem (from `reap.wall_clock_log_path`)
- tokens spent per test (LLM cost)
- per-node validity rate (proposed tactics that parse AND execute AND close)
- rollout variance — for judging the reward signal

## 6.3 Ablation matrix

| Config | Policy | Value | Search | Question |
|---|---|---|---|---|
| A1 | SFT 1.5B | LLM-JSON | MCTS | baseline |
| A2 | SFT 1.5B | head | MCTS | value signal value |
| A3 | SFT 1.5B | none (pure prior) | MCTS | control for value |
| A4 | SFT 1.5B + GRPO | head | MCTS | the full loop |
| B1 | SFT 3B | head | MCTS | scale model |
| B2 | A4 @ 2× budget | | | search vs RL tradeoff |
| C1 | REAL-Prover 7B | LLM-JSON | MCTS | upper reference |

Key comparisons:

- $\text{solve(A4)} - \text{solve(A1)}$: does RL pay for its cost?
- $\text{solve(B2)} - \text{solve(A4)}$: is search scaling more cost-effective than
  RL, at 1B scale?
- A3 vs A1: is the model-value **needed** at all, or does the prior suffice?

## 6.4 Expected curves (hypotheses to test)

$$\text{solve-rate} \approx a \cdot \log B + b \quad (\text{search saturation})$$

- $a$ signals how "searchable" the model is: big $a$ = small model still useful.
- If A3 ≈ A1: drop the value network entirely (simpler loop, less code).
- If A4 ≫ A1 after ~10 iterations: the loop is alive; scale to B-series.

Target: **small-model + RL ≳ 60% of 7B solve-rate per-LLM-token** on FATE-M
subset within the first month of training compute.
