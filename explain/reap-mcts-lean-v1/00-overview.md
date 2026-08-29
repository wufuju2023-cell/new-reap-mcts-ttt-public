# V1 spec：Reap.MCTS + Lean，面向训练的生产版（reap-mcts-lean-v1）

> 依据 `explain/7-reap-v1-v2.md` §2 提出的**上游 reap 四个问题**逐一求解。
> 目标：把"给人类用的编辑器证明搜索器"变成"给机器用的批量数据生成器 + RTTT 训练环"。

## 0.1 上游四个问题的回应（本文档的验收锚点）

| # | 问题（7-reap-v1-v2 §2） | V1 要求 | 本文章节 |
|---|---|---|---|
| P1 | UI 耦合（InfoView/RPC/React widget） | 剪枝所有 editor 专属代码；CLI 驱动 | §1 |
| P2 | 无批处理 | BatchSolver：题目文件 → 逐题 rollout，断点续传 | §3 |
| P3 | 无轨迹面 | RolloutSink：每个节点流式发射完整样本 | §2 / §4 |
| P4 | 无 RTTT 挂钩 | 验证反馈即时流出 → buffer → ttt_step | §5 |

## 0.2 范围与非目标

- 范围：与上游同算法的**批量 driver + 样本出口 + 在线更新钩子**；Lean 侧利用 checkProof 完整闭环。
- 非目标：不改 MCTS 核心语义（PUCT/AND-OR/backup）；不做编辑器 widget（V2 才做 meta）；不做遥控 UI。
- 版本锚：reap lean-toolchain `v4.28.0-rc1`（已容器化 `ghcr.io/example-org/reap-lean:4.28.0-rc1-reap`）。

## 0.3 端到端数据流（V1 总图）

```
题目池 batch.jsonl
   → BatchSolver（同步 CLI，无 UI）
       每道题: theorem s → Lean 加载 → reapMCTS（策略/价值/PS 三 endpoint）
       └─ RolloutSink（每节点）：(state, tactic, EvalError, logprob, value, parent, depth)
             ├→ solutions.jsonl   （kernel 验证通过的证明脚本+树）
             ├→ failures.jsonl    （失败轨迹：错误/超时/违规）
             └→ rttt_buffer.jsonl（流式给 policy_server /ttt_step）
   → trainer 消费 solutions/failures（GRPO/TTT 数据）
```

## 0.4 验收标准（Definition of Done）

1. `v1 run batch.jsonl --workers 4 --max-runtime 1800` 单命令跑通 100 题；
2. `solutions.jsonl` 每行含完整 proof script 且 `lean` 复检通过（kernel 验证，非 only-close）；
3. 失败轨迹可定位：每条含 `EvalError` 精确类型（parse/forbidden/timeout/errorMsg/unassigned/aux/sorry/kernelcheck）；
4. 任意题中途杀进程 → 重跑续作（checkpoint 幂等），不重复 LLM 调用；
5. 断点、日志、样本面 schema 稳定；**无 30s+ 卡死**（每次 LLM 调用有超时与重试上限）。
