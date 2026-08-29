# 04. Data & SFT

## 4.1 Sources

| Source | Contents | Phase |
|---|---|---|
| `FrenzyMath/state_tactic_pairs` | ~50k (state, tactic) pairs over Mathlib | M1 (free) |
| `frenzymath/REAL-Prover` → `Realprover/data/fate_m.jsonl` | FATE-M theorem statements | evaluation target |
| Own rollouts | state → chosen tactic chains, incl. fail/error samples | M3 (organic, unlabeled) |
| FATE-M / ProofNet statements | labeled by Lean executing rollouts | reward-only |

Format per sample:
```json
{"id": "...", "state_pp": "...", "context": ["premise1", "premise2", ...],
 "tactic": "...", "logprob_old": -12.31, "solved": false, "error": null}
```

## 4.2 Cleaning (before any training)

Apply the same verifier the search uses (cheap set):

1. `lake env lean` accepts the file (parse-level).
2. The generated tactic executes and closes the goal **or** fails in a
   deterministic way (record the error — a failed-tactic sample is still a
   useful negative).
3. No `sorry`/`admit`/`?` in the tactic (Reap already bans them).
4. Dedup by `StateKey`-equivalent (pp-goal hash).

Filtering budget: 50k pairs → expect ~80--90% usable for state--tactic SFT.

## 4.3 SFT recipe (phase B)

Base: `Qwen/Qwen2.5-Math-1.5B-Instruct` (or 3B if VRAM permits).

Loss (token-level, mask prompt):

$$\mathcal{L}_{\mathrm{SFT}}(\theta) = -\mathbb{E}_{(s,a)\sim\mathcal{D}}\sum_{t}\log \pi_\theta(a_t \,|\, s, a_{<t})$$

Config outline: LoRA rank 32, $\alpha = 64$, lr $2\times10^{-4}$, cosine,
1--2 epochs, bf16, seq length 4096, grad accum 16, paged optimizer on 24GB card.

Env/format detail: the prompt template must **exactly** match
`mkPrompt` in `Reap/Tactic/Generator.lean:73-82`
("User: Please generate a tactic in lean4 ..." + related theorems + "STATE:" +
state + "TACTIC:" + "Assistant:") — otherwise the served model inherits a
format shift. Keep a frozen prompt template module in the trainer repo and a
golden unit test against Reap's `mkPrompt`.

## 4.4 Verification-driven cleaning (the key difference vs plain SFT)

Plain SFT learns hallucinated tactics too. Reap's `checkProof` + Lean compile
gives us a **hard label**:

- pairs where the tactic parses and the goal is **closed and kernel-checked**
  → positive sample weight $w=1$
- pairs where it parses but fails to close → negative supervision via
  (state, tactic, error) triples, weight $w=0.1$

Simple model of why this matters: a policy that keeps producing syntax-valid
but wrong tactics wastes 95% of MCTS compute.
