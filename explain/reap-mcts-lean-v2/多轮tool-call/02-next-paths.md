# 02. 下一步执行路径（把本文档接入当前 repo 的 v2 路线）

> 只定义“做什么/改哪些文件”，不涉及具体实现细节（以免过早耦合）。

## 1. 现状盘点（已有 = agentic 多轮的基础）

| 已有 | 说明 |
|---|---|
| `Reap/Tactic/Step.lean` | 每轮执行的验证器（多轮安全性的源头） |
| `TreeSearch/{Basic,MCTS}.lean` + `Tactic/TreeSearch.lean` | 多轮可搜索的连接件（树） |
| `RolloutSink` / `v1_sink.py` | 每轮的记录面（类型化状态快照） |
| `policy_server`（GPU） | 策略/价值/`/ttt_step`（多轮内在线更新） |
| amdbridge / runner | **世界效应原语桥**（python/检索/训练/文件/进程） |
| `lean-v1/` | 库（lean 类型化协议的表达基础） |

## 2. v2（CPU, no-miner）要补的三个“桥接件”

1. **Effect 原语注册表**（对应 §0 的 Env）：为 amdbridge runner 队列里的每个原语声明
   （python-exec / retrieve / train-launch / file-io）为 $\mathrm{Eff}$ 项，提供（类型, 执行器, 观测转换）。
   - 可挂在 `app/effect_registry.json` + `lean-v1/Reap/Training/Effect.lean`（类型化可执行项封装）。
2. **turn-level 树化**：`BatchSolver.lean` 每个“turn”即一个含 typecheck 的 action 扩展点；
   与 `step.lean`（现有验证器）相同调用，仅上层“多次迭代”组合。
3. **塔上升门**：库登记器（`addDecl` 步骤前）强制 `kernel` 验证 + 禁止自指（agent 生成代码不得触碰
   学习器/训练器自身——§7 的红线）；库增长度量 `d_g` 自动记录进 sink。

## 3. 顺序建议（与既有 V1-1 并行推进）

1. **先并行写"Effect 原语"最小集**（3 个：python-run / fs-read / retrieve-local）——因为它们
   是“多轮”里唯一真实世界接口；Lean 侧以 `#eval` 或 FFI 落定
2. **再扩展 `RolloutSink` 的观测类型**（effect_obs 事件族）
3. **最后**把“深度优先多轮循环”demo 写进 BatchSolver（不依赖 miner，题目=同一批 FATE-M）

## 4. 关联文档

`explain/4…`（三层桥接）、`5-alpha…`（Lean 唯一语言）、`7-reap-v1-v2`（Reap.Agent 设计）、
`8-v2-math-drive`（数学驱动）、`10-mcts-usage…`（MCTS 是信号机器）、`agentic-perspective/01`（rollout 定义）。
