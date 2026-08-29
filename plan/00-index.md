# Reap-Small: Plan Index

A research plan to reproduce the Reap / REAL-Prover mechanism with a **smaller model** and a **full RL loop with parameter updates**.

| File | Focus |
|---|---|
| [01-motivation.md](01-motivation.md) | Why this project: Reap architecture, model reality, the search-scaling hypothesis |
| [02-architecture.md](02-architecture.md) | System design: Reap as environment, endpoints, model choices |
| [03-environment-mcts.md](03-environment-mcts.md) | How the MCTS part works and what we reuse vs rewrite |
| [04-data.md](04-data.md) | Data sources & SFT phase |
| [05-rl-param-update.md](05-rl-param-update.md) | The RL training loop, parameter updates, value network design |
| [06-evaluation.md](06-evaluation.md) | Benchmarks, metrics, ablations, expected results |
| [07-roadmap.md](07-roadmap.md) | Milestones, hardware, risks |
| [08-post-training.md](08-post-training.md) | Improvement A: continued training / post-train on Reap (no cold start) |
| [09-test-time-training.md](09-test-time-training.md) | Improvement B: test-time training — online policy & value updates after API calls |
| [10-recursive-self-improvement.md](10-recursive-self-improvement.md) | 递归自改进：reap + 演化器自动生成更难题目，闭环代际迭代 |
| [11-curriculum-traditional-llm.md](11-curriculum-traditional-llm.md) | 课程学习 + 变体逼近（传统 LLM：pre-train/SFT/post-train，推理冻结）+ 累积 mathlib |
| [12-two-model-architecture.md](12-two-model-architecture.md) | 双模型：A=传统 teacher 生成变体课程（推理冻结） × B=RSI-Reap student（TTT + 递归）解阶梯、逼近难题 |

## One-paragraph summary

Reap (IQuestLab / frenzymath) implements an AlphaProof-style MCTS prover: an LLM policy proposes Lean tactics from a prompt of the current proof state and retrieved premises; the value model estimates state solvability; Lean itself is the verifier (`checkProof`). The open-source repos contain the **search harness** but not the **training loop**. This project reuses the harness, swaps in a small open model (0.5B--3B), and adds a genuine RL loop (SFT $\to$ rollout collection $\to$ GRPO update $\to$ repeat) where the learned value target and policy gradients come from MCTS rollouts that Lean verifies.

**Two process improvements (added on top of the base plan):**
1. **Continue, never start from zero** (§08): warm-start from REAL-Prover or an SFT checkpoint; rollout data + old-pair replay, then RL, then self-improvement.
2. **Test-time training** (§09): during search itself, after each policy call the Lean verdict becomes a label; a small online LoRA step pushes the accepted tactic up / the repeated error down, and the value head takes TD updates against the search's own backups — parameters are NOT frozen at inference.
