# Reap MCTS × TTT

Sanitized public snapshot of **Reap** — an open, lightweight AlphaProof-style system:
Lean-native MCTS proof search × meta-actions (Eff/Tower) × policy/value head + test-time-training (TTT).

> Reap：把 AlphaProof 变为开放、轻量、可复现的系统。搜索在 Lean 内、每个 rollout 可观察、1.7B 小模型研究 RL 为何有效。

## What is this?

An **AlphaZero-style search + RL loop** for Lean 4 theorem proving:

- CPU/Learn side keeps proof states **inside Lean** and runs MCTS; the kernel is the verifier and the reward.
- The policy proposes tactic strings; the **value head** predicts remaining critical-path cost — $V_\theta$ 决定 $Q$（`Q = γ^{−V̄(s′)}`），PUCT 选边，AND/OR 节点精确表达子目标依赖。
- Replay + final kernel check mean **no false-positive rewards**; every failure is an artifact.
- Small models (0.5B–3B checkpoint loop) run on one budget GPU — results below come from a **1.7B** Qwen3-based policy–value model.

## Results (Reaper 1.7B, pass@32)

| Bench | miniF2F-test | ProofNet-test | FATE-M |
|---|---|---|---|
| REAL-Prover (7B) | 54.1% | 23.7% | 56.7% |
| DeepSeek-Prover-V2 (7B) | 75.6% | 25.4% | – |
| OptProver (7B) | 73.0% | 26.3% | – |
| Reaper (1.7B) | **78.7%** | **33.8%** | **81.3%** |

single-checkpoint @32 = 77.5%, accumulated = 80.3%, **+18.3% RL gain over SFT baseline**.

## 目录（速览）

| 目录 | 内容 | 速读 |
|---|---|---|
| `app/` | **GPU 侧服务**：policy server、value head、RTTT、批量 driver | [`app/VALUE_HEAD.md`](app/VALUE_HEAD.md) |
| `v1-spec/` | 与云平台无关的 **V1 协议与训练方法**（P0 SFT → P1 GRPO → P2 TTTRL） | [`v1-spec/00-overview.md`](v1-spec/00-overview.md) |
| `reap-mcts-lean-v2-code-1/` | V2 元动作 + Eff/Tower 的**最小可运行原型**（Lean + Python） | [`README.md`](reap-mcts-lean-v2-code-1/README.md) |
| `explain/` | 深度分析归档（1–13）+ **wiki 知识页**（含 30 页演示文稿图解） | [`explain/README.md`](explain/README.md) · [`explain/wiki/README.md`](explain/wiki/README.md) |
| `plan/` | 研究计划 11 篇：动机/架构/RL 参数更新/评估/路线图/TTT/递归自改进 | [`plan/00-index.md`](plan/00-index.md) |
| `discussion/` | AlphaProof 从零到完整机制讲义（搜索/Value/TTT） | `discussion/alphaproof-value-head/README.md` |
| `lean-v1/`, `lean-v2/` | 上游 Lean 核心 + V2 元层草图（Eff/MetaActions/Tower） | — |
| `docker/` | 容器构建（lean / reap-lean / train） | [`docker/README.md`](docker/README.md) |
| `tests/`, `tools/` | 单测；`scan-secrets.sh`（机密扫描）、`check_md_math.mjs`（KaTeX 校验） | — |

## 基本原则

1. **验证在 Lean**：所有状态转移由 kernel 检查；搜索成功必须先 replay，再经 `checkProof` 终检才计奖励。
2. **模型是外置服务**：CPU 侧只依赖约定端点（`/v1/chat/completions` ／ `/value` ／ `/ttt_step`），不关心 GPU 内部实现。
3. **多轮观测写回状态**；外部工具凭据只来自运行时环境变量。
4. **可观察优先于性能**：树、value、visit、premise、wall-clock trace 全部落盘，失败即工件。

## 本地检查

```bash
python -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=reap-mcts-lean-v2-code-1 python -m v2.smoke_v2          # V2 单元
PYTHONPATH=reap-mcts-lean-v2-code-1 python -m v2.smoke_v2_full     # V2 全链（gate 真验证 + MCTS）
PYTHONPATH=reap-mcts-lean-v2-code-1 python -m v2.runner --steps 8  # 元动作 demo
bash tools/scan-secrets.sh                                          # 提交前
node tools/check_md_math.mjs explain/wiki/*.md                      # 文档数学校验
```

## 发布说明

本快照为**无历史公有化快照**：不含云平台控制脚本、运行证据、模型权重、私有配置或嵌套私有仓库（详见 [PUBLICATION.md](PUBLICATION.md)）。请勿提交 `.env`、私钥、访问令牌、模型权重、运行日志或带个人/实例标识的内容。

---

*机制已复现；规模仍是开放问题。加入我们——search inside Lean，inspect every rollout，learn with small models。*
