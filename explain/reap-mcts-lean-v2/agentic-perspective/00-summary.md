# agentic-perspective：reap-mcts-lean v1/v2 的智能体视角规格

> 前提与依据：`explain/4-alpha-proof与智能体训练是否兼容.md`（P-V vs Agent 管线三层桥接）、
> `5-alpha-as-Lean-coding-agent.md`（Lean 作为唯一智能体语言）、
> `8-v2-math-drive.md`（数学驱动 agentic 技能涌现）、
> `10-mcts-usage-and-alternatives.md`（MCTS=信号机器）。
> 核心问题：**v1/v2（miner-trained / no-miner / deterministic-miner）如何做 agentic math writing 与
> Lean coding（含 tool use），与 DeepSeek V4 Flash 类“大任务 agent rollout”有何本质差别**。

## 0. 一句话定位

| 系统 | 定义 |
|---|---|
| **v1（CPU）`reap-mcts-lean-v1`** | 树式 agent rollout：MCTS×Lean 环境（**搜索=推理展开，CPU 侧无在线学习**） |
| **v2（GPU）`policy-value-ttt`** | 同一 agent rollout + **在线学习**（在线 TTT：搜索事件→梯度→下一节点用新值）——“边做边学的 agent” |
| **LLM agent（DeepSeek V4 Flash 类）** | 单链长上下文 rollout：LLM 自生成 CoT→工具调用→结果回注，无树、无逐节点验证、无在线更新 |

## 1. 推荐阅读与后续（v1→v2 演进路径）

1. 本目录 `01-rollout-cot.md` — v1/v2 的 agent rollout & chain-of-thought 的严格定义
2. `02-vs-llm-agent.md` — 与 DeepSeek V4 Flash 类 agent 的逐维对比与并合策略
3. `03-miner-variants.md` — miner-trained / deterministic-miner / no-miner 三态与我们的推荐
