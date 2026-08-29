# 06. CPU 层 Lean 化重构完整计划（v1/v2；GPU 模型接口视为已封装）

> 目标约束（用户裁定）：
> ① CPU 层**尽量全部用 Lean 写**，结构对齐原始 reap 仓库；
> ② GPU 层（policy/value + value head + TTT）是**已封装好的接口**——CPU 只消费三个 HTTP 端点；
> ③ 现阶段 **no-miner**（不做任务挖掘器）；
> ④ 多轮工具调用（v2）与此计划同轨：MCTS 与多轮都必须以 Lean 为语言。

## 0. 铁律（与上游一致）

- MCTS 语义：PUCT/OR-AND/γ-backup/progressive sampling——**不动内核**；
- 验证语义：`Step.lean` 的 kernel 校验是唯一成功来源；语言=Lean 4.28.0-rc1；
- 结构：`Reap/TreeSearch/{Basic,MCTS}`、`Reap/Tactic/{Step,State,Generator,Syntax,WallClock}` 原样复用；
- python 仅保留**薄驱动**（文件/进程/断点），其内不可有算法逻辑（算法只准 Lean）。

## 1. 分阶段

### 阶段 A（无新代码，验证基线）
- [x] `new-v1-gather-source-code-cpu` 归集完成；`reap-lean:4.28.0-rc1-reap` 镜像已推（含上游 lake build）。
- 做法：在容器内跑通 `v1_run.py`（生成 Lean 伪代码→执行→sink）——确认“Lean 是执行主体，python 是胶水”。

### 阶段 B（v1 Lean 化：RolloutSink/Driver 全部 Lean）
```
B1  sink 双实现统一：Lean (Reap.Training.RolloutSink)` 成为唯一写面；
    python v1_sink.py 降级为“只校验/分析”工具。
B2  BatchSolver Lean 化：写 `Reap/Training/BatchSolver.lean`
    - 读 batch.jsonl（lean IO/Json）
    - 对每个 theorem：构造 MVar → mkProofCheckContext → runMCTS → replay/checkProof
    - 每步调用 RolloutSink.appendNode/Done（Lean）
    - 每题 checkpoint（state/*.done）由 Lean 写（幂等）
    → python v1_run.py 只做“启动一次 lake env lean + 收集退出码”——算法全在 Lean。
B3  GPU 契约冻结：Lean 端 endpoint 配置（set_option）+ 3 端点请求断言；mock 仅本地调试。

### 阶段 C（v2 Lean 化：多轮工具调用 + MCTS）
按 `new-v2-gather-source-code` 目录的“T1-T5”，全部在 Lean 完成：
```
C1 状态结构  : Lean 定义 `S = (ctx, obs : EffObs, ok : Bool, tower : TowerNode)`（T1/T4）
C2 动作类型化: `Action`（现有 MetaActions）扩展参数化 effect/patch 实例（T2）
C3 时序子程序: `EffectSubroutine`（Lean 顺序执行、预算、中断、检查点；§多轮00 协议）（T3）
C4 树化      : `v2.MCTS` 在 Lean 中实现（复用 Reap.TreeSearch.MCTS 泛型 on σ=S/ε=Action）（引擎不动）
C5 门服务化  : Lean 常驻 gate（`lean --run` server 模式读 stdin/写 verdict）替换 podman 冷启动（T5）
   （gate_lean.py 只作为“远程 gate 客户端”备用）
```
- multi-round 语义：`EffectSubroutine` 是树的“一个动作”；一轮内部是 Lean 的 `while` 循环；
- no-miner：不实现 mine.py 的新增接口（保留 `mine:series` 的 Lean 等效玩法作为 demo，不进课程）。

### 阶段 D（端到端与质量）
- D1 用 mock（模式 `mode==v2`）跑通：多轮=5 轮+塔增长≥3+gate 全校验；
- D2 真策略端点（GPU policy_server）联调：树动作类型全部由外部模型给；
- D3 测试：每个 Lean 模块 `#guard_msgs` 可测（验证器契约检查）；
- D4 结构对齐检查：`tree of Lean libs == Reap/TreeSearch+Reap/Training+Reap/v2`，与上游无漂移（diff 仅新增命名空间）。

## 2. 接口契约（CPU→GPU，冻结）

```
GET  /health                          → {ok, device, generated, mode}
POST /v1/chat/completions  {prompt,n,temperature}            → {choices:[{text, logprob_avg}]}
POST /value               {prompt}                           → {"score": float}
POST /ttt_step            {items}                            → {loss, kl, steps}
POST /adapter/snapshot|restore {name}                        → {"result":…}
```
> 仅此五端点。CPU（Lean）内实现为 `v2.PolicyClient`（Lean `IO`/HTTP via `#eval` 或 lean 库）——
> 这部分也可用现有 `Reap.Tactic.Generator`（OpenAIClient) 的 Lean 客户端模式。

## 3. 技术风险

| 风险 | 对策 |
|---|---|
| Lean 内 HTTP/IO 端点实现成本 | 复用 `openAI_client` 库（上游已有 Lean HTTP/SSE 客户端）；value/adapter 端点用同一客户端 |
| WSL/实例差异 | 可编译性闸门（lake build per commit）；`lean --run` 服务化容器内跑通 |
| 多轮→树（T3）语义 | 先 Lean 单轮（Banner），再 EffectSubroutine（C3）严格验证；多轮先“按轮提交”再做并行 |
| 代码体积 | 与上游 diff 只有三个新命名空间（Training/v2），保持可回归 |

## 4. 验收（DoD）

1. `lean-v1` 全量（B1-B3）与 `v2`（C1-C5）在 `reap-lean` 镜像内 `lake build` 通过；
2. CPU 侧零 python 算法（只留驱动/检查工具）；
3. 与 GPU 五端点全通（mock + 真端点各一遍）；
4. 多轮 demo：5 轮×3 分支、塔高≥3、gate 全部验证、checkpoint 幂等；
5. （对照）`/explain/多轮tool-call/03` T1-T5 全部关闭。
