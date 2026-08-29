# 09. Test-Time Training (TTT): update policy & value after API calls

The idea: **don't freeze the parameters during search** — after every (or
every few) policy API calls, the verifier returns a label
(tactic works / fails / closes), and we take a **small online gradient step**
on both the policy adapter and the value head. The search makes the model
better at *this* theorem in real time.

## 9.1 Two granularities

| Mode | Scope of update | Persistence | Cost |
|---|---|---|---|
| **TTT-intra** | within one theorem's search | discarded after theorem | cheap; adapts to current goal |
| **TTT-inter (RTTT)** | after theorem n → model for n+1 | persists (adapter memory) | accumulates; must guard leakage |

Both share the same update rule; they differ in when the adapter resets.

## 9.2 What the API call returns (the signal we use)

Every policy call (per node expansion) yields a **verifier verdict** from
Reap's `EvalResult` (`Tactic/Step.lean`):

$$\big(s,\ a,\ \log p_{\theta}(a\mid s),\ v := \text{verdict}\big),\qquad v \in \{\text{parseError},\ \text{forbidden},\ \text{timeout},\ \text{errorMsg},\ \text{ok},\ \text{solved}\}$$

Folded into a scalar reward $\hat r(s,a)$:

$$\hat r = \begin{cases} +1 & \text{kernel-checked success (\texttt{checkProof} ok)} \\ -\eta & \text{errorMsg / parseError (repeat offender: } -\eta\,\cdot\,\log\text{-count)} \\ 0 & \text{otherwise} \end{cases}$$

## 9.3 Policy update (per-verdict on-policy step)

$$\theta \leftarrow \theta - \alpha\, \nabla_\theta\!\left[-\hat r(s,a)\,\log \pi_\theta(a\mid s)\right] - \alpha\,\beta\,\nabla_\theta\,\mathrm{KL}\big[\pi_\theta \,\Vert\, \pi_{\theta_{\text{base}}}\big]$$

so the model:
- **pulls up** tactics the verifier accepted (positive feedback),
- **pushes down** its own repeated errors — this directly cures the MCTS
  killer: emitting the same invalid tactic over and over,
- stays near $\theta_{\text{base}}$ (the pre-search weights) so one theorem
  cannot destroy mathlib knowledge.

Per update we sample **multiple** (state, tactic) pairs from the current
search's store, so each step is a small batch (even batch of 1 is fine).

## 9.4 Value network update (TD, from the search tree)

The search already produces Monte-Carlo evidence: the discounted backups.
Use a TD step that doesn't require finishing the rollout:

$$V_\phi(s) \leftarrow V_\phi(s) + \alpha_V\big[\,\hat r(s,a) + \gamma\, V_\phi(s') - V_\phi(s)\,\big]$$

$$V_\phi(s') = \text{value of the child reached by } a \text{ (from search or bootstrap)}$$

Per node updated = cheap; the **value sees the exact errors the search hits**
(the distribution mismatch "LLM value model vs. Lean reality" is corrected
online — this is where TTT value shines, because the head is trained against
*this* run's backups).

## 9.5 Update triggers & budget

| Trigger | Pros | Cons |
|---|---|---|
| every API call (per node) | most reactive | vLLM adapter reload per step = minutes; too slow |
| every $k$ nodes (default $k=8$) | amortized reload | lag |
| per rollout / per theorem batch | fits real serving | less adaptive |

Budget per theorem:

$$\#\text{grad steps} \le G_{\mathrm{ttt}} = 16,\qquad \alpha \approx 10^{-3},\ \text{LoRA rank} \le 16,\ \text{base frozen}$$

## 9.6 Serving reality check (the decisive constraint)

- **vLLM**: no per-request LoRA hot-swap per node in OSS builds — vLLM warms
  adapters per module; reload ≥ seconds. So "update each API call" **must be
  every-$k$-nodes or per-theorem**, or
- **our own adapter server**: FastAPI + HuggingFace `peft`, base loaded
  frozen, `enable_lora=True`; forward+backward in-process. 1.5B fits 24 GB
  comfortably, 3B tight → *this is the TTT server*. On the user's laptop (8 GB
  RAM, no NVIDIA): TTT needs a GPU, no way around it (compute + memory for
  backprop; llama.cpp can't compute gradients).
- TTT-intra on CPU-only models ≈ zero gradient scale → skip; run TTT on the
  rented GPU in the same process as rollouts.

## 9.7 Leakage discipline (must)

- TTT-inter: adapters are trained on the *training* subset only; identical
  theorem text appearing in eval → TTT makes metrics meaningless.
- Eval protocol: every eval theorem is evaluated with **fresh base weights**,
  TTT disabled, or TTT + measured separately ("TTT budget report": report both
  $\text{solve@}B_{\text{static}}$ and $\text{solve@}B_{\text{static}+G_{\mathrm{ttt}}}$).

## 9.8 Why the user's instinct is good (anticipate gains)

1. **MCTS already caches per-node state** — TTT exploits the *same* search
   trace as supervision: near-free labels.
2. **Repeat-error kills search**: progressive sampling at $N\uparrow$ resamples
   the same bad tactic (policy probability is high for the wrong thing);
   negative push-down restores exploration in minutes.
3. **RL convergence without global RL**: TTT is "local" RL — same formulas,
   smaller scope; predictable; can be turned off instantly (reset adapter).
4. **Value correction**: chat-JSON LLM value is coarse; TTT-head update is
   the cheapest way to inject verifier-consistent values into PUCT.

## 9.9 Open questions to test

- Does TTT-intra help more on hard (high $N$ needed) theorems than easy ones?
  (Hypothesis: it sharpens on repeated errors → benefits hard.)
- $\eta$ (push-down weight) vs. $\alpha$: too large → entropy collapse within
  one theorem (right after start to add noise to prompts).
- TTT-inter drift after 100 theorems — measure KL to base; if KL > $2\beta$,
  rewind.
- Best blend: TTT-off with a better static model vs. TTT-on with base — i.e.,
  $\mathrm{solve}_{TTT}/\mathrm{solve}_{\mathrm{static}}$ on eval set.
