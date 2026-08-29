# 04. RTTT 挂钩：验证反馈流式化（解决 P4 无 RTTT 挂钩）

## 4.1 触发点（上游 `Tactic/Step.lean` 处打钩）

- `evalTacticStrCore` 的 **结果分支**（ok/error 分类完成处）→ sink 一行 `kind: node_visited`；
- `replaySolvedNode` 成功瞬间 → `kind: task_done`；
- 若题解 → `reapMCTS result` → 调用 `rttt_server` 事件端点。

**最小改动**：替换 `Tactic/Step.lean` 的 `appendLogRecord`（WallClock）为**多路**——原 JSONL 继续 + 每节点追加到 `rollout_out`（`RolloutSink`），不对 Step 实际校验逻辑做任何改动。

## 4.2 事件 → RTTT 协议（Lean 侧无需知道训练细节）

`reap-v1/RolloutSink.lean` 提供三端点实现，与 `policy_server` 的 HTTP 接口对接：

```
POST /ttt_event   body: {"state": "...", "tactic": "...", "verdict": "ok|...",
                         "logprob_avg": -12.3, "core": "value_from_server"}
```
policy_server 内部维护：buffer；`len(buffer) >= k`（默认 8）→ `ttt_step`（单步 REINFORCE+KL/v-TD）→ 清 buffer，输出 `rttt_update` 行。

## 4.3 在线学习的停止条件（RTTT 也是"暂停"）

1. buffer 阈值 `k`（值来自 `reap.rttt_buffer` 配置，默认 8）；
2. 每题结束（task_done）→ 自动 `adapter/snapshot <task_id>` + （可选）保留最新 adapter；
3. `--rttt-off`：不做 ttt（BatchSolver 的纯收集模式）；
4. 回滚保护：单题 KL > 阈值（默认 2.0）→ restore 该题开始时快照。

## 4.4 与 7-reap-v1-v2 §5 关系

本 spec 实现 V1 的 RTTT（在保证"评估/收集只读"的前提下做在线更新）；
V2 才加 `Reap.Agent` 的元动作层（超出本文）。
