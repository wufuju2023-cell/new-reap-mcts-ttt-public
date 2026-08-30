# 01. Motivation

## 1.1 What Reap is

Reap is a Lean 4 **tactic plugin** that runs tree search over proof states:

- Each node = a saved Lean proof state; each edge = a generated tactic string.
- The **policy** is an LLM: given the pretty-printed state and retrieved premises,
  it returns $n$ candidate tactics plus their $\log p$ (OpenAI `logprobs`).
  Prior probability of a child:

$$
p(a\mid s) = e^{\log p_{\mathrm{LLM}}(a\mid s)}
$$

- The **value** model scores each state (an LLM returning `{"score": float}`).
- **Lean is the verifier**: any tactic the policy proposes is executed, and on
  success a full kernel check (`checkProof` in `Reap/Tactic/Step.lean`) rejects
  unsound shortcuts (`sorry`, `admit`, unassigned goals, aux-decl mvars).

Reap itself contains **no gradients and no parameter updates**. It is an
environment + search harness. The weights behind its endpoints (REAL-Prover,
Qwen2.5-Math-7B) were trained elsewhere, mostly by SFT on ~50k state--tactic
pairs (`FrenzyMath/state_tactic_pairs`).

## 1.2 The gap this project fills

We want the **full AlphaProof-style loop**: parametrized policy $\pi_\theta$,
parametrized value $V_\phi$, MCTS with discounted backprop, and **parameter
updates from those rollouts**:

$$\theta \leftarrow \theta - \eta \nabla_\theta \mathcal{L}_{\mathrm{RL}}$$

Since the original repos omit this loop, we must build it.

## 1.3 Why a smaller model

1. **Hardware**: REAL-Prover 7B BF16 needs $\ge 16$ GB VRAM for vLLM; a
   1.5B--3B model fits on a single budget GPU ($4\text{GB}$--$ 9\text{GB}$),
   and 0.5B--1B can almost run CPU-only for smoke tests.
2. **The search-scaling tradeoff**: weaker policies can still solve theorems
   given enough search, because each node cost is cheap and the verifier is
   exact:

$$
\text{solve-rate} \approx f(\text{model quality}) \circ g(\text{search budget})
$$

   AlphaProof reports this superlinearly: doubling search depth buys roughly a
   10x solve-rate lift. A small model's correctness deficit can be absorbed by
   deeper MCTS — this is precisely the hypothesis we can test.
3. **Learnability**: small models let us prototype RL iterations in minutes
   instead of days, so the loop (rollouts → updates → re-serve) is actually
   runnable on a student budget.

## 1.4 Research questions

1. How much search must $\approx$ 1B policy expend to match 7B policy at fixed
   solve rate on FATE-M-style math?
2. Does RL on MCTS rollouts (with a lean verifier reward) improve the 1B policy
   relative to SFT-only, and by how much per training compute?
3. Which value signal is best at this scale: LLM-prompt-JSON value, MLP value
   head trained against MCTS returns, or no value (pure PUCT with priors only)?
4. Can the full loop be self-contained: `reap` rollouts → data → updates →
   weights → same endpoints, on one rented GPU?

## 1.5 Scope boundaries (honest limits)

- We will **not** beat REAL-Prover on benchmarks; we want a clean, small, open,
  reproducible RL+search circuit.
- The premise retriever (LeanSearch-PS) is heavy self-hosting; phase C swaps in
  Lean's built-in library-suggestion interface (already supported in
  `Reap/PremiseSelection/Syntax.lean` via `set_library_suggestions reapSelector`).
- Mathlib version: Reap was trained against `v4.28.0-rc1` and is compatible to
  `v4.30.0` — pin the toolchain to match before RL experiments.
