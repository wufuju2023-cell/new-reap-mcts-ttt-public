# 01. 架构：与上游 reap 的差集（保留 / 剪枝 / 新增）

## 1.1 保留（核心，不改语义）

| 上游文件 | 角色 | V1 处理 |
|---|---|---|
| `Reap/TreeSearch/Basic.lean` `MCTS.lean` | 通用树/状态数组引擎 | 原样 |
| `Reap/Tactic/Step.lean` | 验证器（parse/禁止/超时/kernel check） | 原样——**V1 的信用核心** |
| `Reap/Tactic/Generator.lean` | LLM/价值/PS 协议（含 logprobs） | 加导出钩子（见 §4），不重写 |
| `Reap/Options.lean` | 选项 → 配置 | **按上游 issue #15 思路重构为 `TacticConfig` 结构**，向后兼容 set_option |
| `Reap/Tactic/State.lean` | 状态 key/去重 | 原样 |

## 1.2 剪枝（编辑器专属，V1 不需要）

- `Tactic/Syntax.lean` 中：`TacticWidgetRangeInfo`、`ReapMCTSProgressView`、`reapMCTSProgressWidget`（React JS）、RPC 方法、TryThis 生成、`reap!!` 的异步搜索包装；
- `Tactic/Syntax.lean:241-285`（`reap!!` elab + widget + async task）→ 保留 `reapMCTS` 的同步语义，别名给出；
- 仅当 `#guard_msgs` 类测试需要（上游 #4）：把 TryThis 生成收敛到**标准 error/info 消息通道**（`IOException` 改为 `logInfo` 带 `mainContext`? —— 采用抛 `Checkpoint.formatTryThis` 输出为 `info` 消息，可被 `#guard_msgs` 捕获）。

## 1.3 新增模块（V1 本体）

```
src/reap-v1/（Lean 侧，挂到 Reap 的 `Reap.Training` 命名空间）
├─ RolloutSink.lean    # 流式样本发射器（§2）
├─ BatchSolver.lean    # 题目→drive（§3）
├─ Verdict.lean        # EvalResult → 结构化 verdict（字符串枚举 + 消息摘要）
├─ Config.Lean         # TacticConfig（对应上游 #15 的接口重构）
├─ MCTSDriver.lean     # proofCheckContext + runMCTS + replay + 导出
Python 侧（app/，与 Lean 通过文件/HTTP 交互）
├─ v1_run.py           # batch 编排器（workers/chunk/断点，调 lean 子进程）
├─ v1_sink.py          # jsonl 写面（schema 校验）
├─ policy_server.py    # 已在（RTTT 端点 §5）
└─ rttt_client.py      # 让 Lean 侧“发 rttt 事件”的 HTTP 客户端（见 §5）
```

## 1.4 任务生命周期（BatchSolver 状态机）

```
ENQUEUE → (LOAD: lean 工具链+mathlib: 每次 worker 进程一次性)
        → (PER_TASK:
             load task (id, theorem statements)
             v1_reapMCTS:  maxSteps=maxNodes=maxGoals
             on solution: emit Solution + ReplayScript + TREE
             on timeout : emit Failure(type=budget)
             on LLM error: retry ≤2 → Failure(type=llm)
           )
        → checkpoint(state/…) 每 task 原子写入
        → DONE
```
- checkPoint = `state/<batch>/<id>.done` + `out/<batch>/solutions.jsonl` append-only；
- 中断恢复：跳过 `.done`，其他追加。

## 1.5 Worker / 并发 / 预算

- `--workers N`：每 worker = 1 个 `lean --run v1_driver` 进程（携带自己的 policy/value 会话——policy_server 无状态 http，安全并发）；
- 每题预算：`maxSteps` 默认 64，超时 `--per-task-timeout 300s`；
- LLM 调用统一走 `retryCoreM?` style：≤2 retries + 300s。
