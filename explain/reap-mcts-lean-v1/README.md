# V1 spec：Reap.MCTS + Lean（reap-mcts-lean-v1）

**一句话**：把上游 reap（编辑器版 `reap!!`）改造成**批量训练版 V1**——无 UI、可断点、全轨迹、挂钩 RTTT，
Lean 侧以 `checkProof` 为唯一成功判定。对应 `explain/7-reap-v1-v2.md` §2 提出的四个上游问题逐一求解。

| 文档 | 内容 |
|---|---|
| [00-overview.md](00-overview.md) | 目标、范围、P1–P4 问题映射、端到端数据流、验收标准 |
| [01-architecture.md](01-architecture.md) | 上游差集（保留/剪枝/新增模块）、任务状态机、Worker/预算 |
| [02-rollout-sink.md](02-rollout-sink.md) | **RolloutSink** 训练样本 schema（node_visited/task_done/rttt_update）、规则、消费面 |
| [03-batch-solver.md](03-batch-solver.md) | **BatchSolver**：输入格式、Lean driver、python 编排、checkpoint/幂等、失败统计、容器运行 |
| [04-rttt-hook.md](04-rttt-hook.md) | **RTTT 挂钩**：Step 处打钩、buffer→/ttt_step 协议、暂停/回滚保护 |
| [05-quality-gates.md](05-quality-gates.md) | Lean 验证闭环、测试（#guard_msgs 可测性，承接上游 #4）、配置报错（承接 #3）、交付物清单 |
