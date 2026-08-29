# 03. Environment & MCTS (what we reuse)

## 3.1 Reuse as-is (already read)

| File | Role |
|---|---|
| `Reap/Tactic/Step.lean` | parse → syntax-ban → heartbeat/timeout → kernel-final-check. The exact verifier an RL trainer needs. |
| `Reap/Tactic/TreeSearch.lean` | OR/AND tree, PUCT (lines 312--331), progressive sampling (333), discounted backup (393--404), proof extraction (531--578) |
| `Reap/Tactic/State.lean` | save/restore + `StateKey` dedup (line 42: hash of pretty-printed goals) |
| `Reap/Tactic/WallClock.lean` | JSONL timing log |
| `Reap/Options.lean` | all knobs: `c_base`, `c_init`, `visit_discount` ($\gamma$), `prior_temperature` ($\tau$), `max_nodes`, `max_steps` |

## 3.2 The exact MCTS equations as implemented

For node with $N$ visits and children $(e_i, n_i)$, prior $\hat p_i = e^{\log p_i}$, normalized $p_i = \hat p_i / \sum_j \hat p_j$:

$$c(N) = c_{\mathrm{init}} + \ln\frac{N + c_{\mathrm{base}} + 1}{c_{\mathrm{base}}}$$

$$Q_i = \begin{cases} \gamma^{-1 - \text{value}_i} - \text{stepcost}_i & \text{OR node} \\ 1 - \text{value}_i & \text{AND node} \end{cases}$$

$$U_i = c(N)\cdot p_i\cdot\frac{\sqrt{N}}{1 + n_i}, \qquad n_i = \text{visits of child } i$$

score $= Q_i + U_i$; select max; progressive sampling: if
$n_{\text{evals}} \le c \cdot N^{\alpha}$ re-expand instead of selecting
($c = 0.01$, $\alpha = 0.6$ by default).

Backup: leaf value $V_{\text{search}}$; for AND children backup is the min of
unsolved children (must solve *all* subgoals):

$$V_{\text{OR}} = \text{child } V; \qquad V_{\text{AND}} = \min_{\text{unsolved children}} V$$

Leaf value source (implemented): the value LLM call, negated; fallback $-\text{score}$.
This is where our RL value head plugs in.

## 3.3 What must be changed for RL

1. **Rollout capture**: Reap logs the raw tree
   (`reap.raw_tree_path`) and wall-clock records, but not per-decision
   samples (state, selected tactic, prior, value, return, solved). Add a JSONL
   emitter at `visitNode` / backprop points (small patch to
   `Reap/Tactic/TreeSearch.lean`), or reconstruct from raw tree + logs offline.
2. **Value semantics**: the chat-JSON value gives $\approx$ one scalar per state;
   an RL value head needs targets from returns. Compute offline per rollout:
   discounted return with the same discount:

$$
R_t = \begin{cases} 1 & \text{solved at } t \\ \gamma^{L - t} & \text{solved at } L \text{ (depth} L\text{)} \\ 0 & \text{exhausted} \end{cases}
$$

   with step penalty $-\lambda$ per tactic — two knobs ($\gamma$, $\lambda$).
3. **Off-policy bookkeeping**: since updates happen after serving older weights,
   store the old policy logprob $\log \pi_{\theta_{\text{old}}}(a|s)$ for
   importance ratios.

## 3.4 Cost model (why this matters for scheduling)

Per node expansion ≈ 1 policy call ($n$ completions) + 1 value call + 1
premise call + **1 Lean tactic execution** (expensive: ~10ms--2s each under
`lake env lean`, dominated by mathlib imports for the elab loop).

Budget heuristic for 64 nodes deep:

$$\text{cost} \approx \#\text{nodes} \times (\text{LLM latency} + \text{Lean eval})$$

A small model at ~40 tok/s and 100--300 tokens/tactic ≈ 3--8 s policy;
Lean eval 200ms average ⇒ ~5--10 min per theorem. So datasets of ~1k rollouts
on one GPU = the right unit of compute for ML3.
