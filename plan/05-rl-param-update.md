# 05. RL with Parameter Updates (the core new work)

Everything below is the part **absent from Reap and REAL-Prover repos** — we
write it ourselves.

## 5.1 The loop

```
for iteration k in 0..K:
  1. serve θ_k (policy, vLLM + LoRA adapter; value head φ_k)
  2. rollouts: run reapMCTS/standalone driver over N theorem prompts
     (each node: policy n samples → Lean-verify → values → MCTS select)
  3. collect traces T_k = { (s, a, log p_old, V(s), R, solved) ... }
  4. compute advantages A (section 5.3)
  5. ONE internal pass: GRPO/PPO update on T_k  (section 5.4)
  6. swap adapter θ_k → θ_{k+1} (no server restart); save metrics
```

## 5.2 Reward signal

Exactly Reap's verifier output defines reward at rollout end:

$$R = \begin{cases} 1 & \exists \text{ kernel-verified proof script (checkProof ok)} \\ -\lambda_{\mathrm{exh}} & \text{budget exhausted} \\ 0 + \lambda_{\mathrm{step}} \cdot \#\text{ steps penalty} & \text{failure modes} \end{cases}$$

Shaping (optional, phase B3): subgoal progress $r_t = \mu\cdot(\lg|\text{goal}|_t - \lg|\text{goal}|_{t+1})$ using goal-size ratio so that
progress-like tactics are rewarded without cheating (final reward still only
comes from the verifier).

Scaffold details: 61-step budget default (Reap default `max_steps = 64`), all
rollout stats appended to `reap_wall_clock.jsonl` + raw tree for debug.

## 5.3 Value target & advantages

For a trajectory $(s_0, a_0, \dots, s_L)$ with returns:

$$G_t = r_t + \gamma r_{t+1} + \gamma^2 r_{t+2} + \cdots$$

Value target (with a value head):

$$\hat V(s_t) = G_t = \sum_{j\ge 0}\gamma^j r_{t+j}, \qquad \gamma \in [0.95, 0.99]$$

advantages, 1-step GAE-like (or simple $A_t = G_t - V_\phi(s_t)$):

$$A^{\mathrm{GAE}(\lambda)}_t = \sum_{j\ge 0} (\gamma\lambda)^j \big(r_{t+j} + \gamma V_\phi(s_{t+j+1}) - V_\phi(s_{t+j})\big)$$

The discriminator's job: **how good a node is on the road to a solved proof,
not "is State X close to a closed state that exists in the tree"** — so the
value head is trained against *replay-verified* outcomes only.

## 5.4 Losses (two variants, tried in order)

**(A) GRPO (no critic)** — group of $G$ rollouts per prompt; baseline = mean return
of the group; advantage per sample = reward minus group mean:

$$\mathcal{L}_{\mathrm{GRPO}} = -\mathbb{E}\Big[\tfrac{1}{|G|}\sum_{g}\sum_{t} \min\big(\rho^{(g)}_t \hat A^{(g)}_t, \; \mathrm{clip}(\rho^{(g)}_t, 1-\epsilon, 1+\epsilon)\hat A^{(g)}_t\big)\Big]$$

$$\rho^{(g)}_t = \frac{\pi_\theta(a^{(g)}_t \mid s^{(g)}_t)}{\pi_{\theta_{\mathrm{old}}}(a^{(g)}_t \mid s^{(g)}_t)}$$

**(B) PPO w/ critic** — adds value loss:

$$\mathcal{L}_V(\phi) = \mathbb{E}\,\tfrac{(V_\phi(s_t)-G_t)^2}{2}, \qquad \mathcal{L}_\phi = \mathcal{L}_V + \mathcal{L}_{\mathrm{PPO}}$$

KL guard via a frozen Kullback--Leibler penalty (or simple KL clip)

$$\mathcal{L} = \mathcal{L}_{\mathrm{RL}} + \beta\,\mathbb{E}\,\mathrm{KL}\big[\pi_\theta\|\pi_{\mathrm{ref}}\big]$$

Value head design (phase B3): if the "LLM-prompt value" proves too noisy
(common at small scale), use a small MLP head over the policy backbone's last
hidden state:

$$V_\phi(s) = \mathrm{MLP}_\phi\big(h_{\theta}(s)\big), \quad \text{trained by MSE}$$

served via `{"score": -V_ϕ}` so the harness stays untouched.

## 5.5 Serving ↔ training synchrony

- One process owns the adapter files; vLLM reloads by recipe (swap
  `--lora-modules`), *not* by restart (trainer keeps the session alive).
- Guard: mixed-online-to-offline drift. Since every rollout step records
  `log p_old`, importance ratio handles the delay; if ratios exceed
  $[0.5, 2]$ too often, reduce rollout batch age (tighter loop, shorter
  delay).
- Rollout-side calls must be **stateless** (same prompt → same behavior up to
  sampling), so a server can be replaced without breaking history.

## 5.6 What specifically already exists vs is written by us

| Piece | Status |
|---|---|
| MCTS + PUCT + AND/OR + kernel verification | ✅ in Reap |
| logprob emission | ✅ vLLM, ❌ llama.cpp (needs custom patch) |
| per-decision rollout record | ❌ patch to `TreeSearch.lean` (optional) OR offline builder from raw tree |
| value head serving | ❌ our FastAPI adapter |
| GRPO/PPO + update + reload | ❌ our trainer (TRL or verl) |
| data registry/cleaning | ❌ our scripts |
| evaluation harness | ❌ our runner (Lake + eval subset) |

Risk watch: keep the harness pinned to the version Reap trained with
(`v4.28.0-rc1` — see `lean-toolchain`); major version mismatch changes prompt
state text (pp format), which silently breaks the model.
