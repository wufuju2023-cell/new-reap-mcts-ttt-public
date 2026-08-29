# 7｜Reap 多版本化：V1（Training fork）与 V2（Meta/Harness）

> 归档：初始想法 + 版本化定性分析（Core / Reap.Training / Reap.Agent）。

## 0. 初始想法（原文）

> "原 reap 仓库需要更多版本：v1 是修改为适配训练（不是 `reap!!` in infoview 的编辑器版）；
> v2 可能需修改为更 meta-programming 与 harness-lean-like 的版本。"

## 1. 先把三个对象钉死

| | 版本 | 定位 | 与上游关系 |
|---|---|---|---|
| upstream | **Reap（原版）** | 编辑器内 `reap!!`：InfoView widget + MCTS + LLM 端点，消费型（给人按 apply） | 权威原版（只同步不魔改） |
| **V1** | `Reap.Training` | 同一核心算法，面向生成数据/训练：无 UI 依赖、批量 driver、轨迹与树导出、协议对接、RTTT 挂钩 | 剪枝 + 加 hooks，不改核心语义 |
| **V2** | `Reap.Agent` | 同套搜索-价值-策略机器，但动作空间升到元层（Lean 唯一智能体语言） | 在 V1 之上扩展问题类（证明→任意任务谓词），是层叠非分叉 |

## 2. V1 为什么必须存在（必要性论证）

上游 reap 的问题**不是算法是形态**：

1. **UI 耦合**：`Tactic/Syntax.lean` 的 InfoView/RPC/React widget 占了一半代码，训练毫不需要；
2. **无批处理**：一次一个 session，训练要 $10^3$–$10^5$ 个 rollout，必须无状态 driver；
3. **无轨迹面**：`raw_tree.json` 有树但没有"每个状态 (state, tactic, verdict, logprob, value)"的训练样本面；
4. **无 RTTT 挂钩**：验证反馈 `EvalResult` 只在内存里，训练要流式消费。

**V1 的严格做法**（对上游做减法 + 加钩子，不动内核）：

- 保留：`TreeSearch/{Basic,MCTS}`（通用引擎）、`Tactic/Step.lean`（验证器）、`Generator`（LLM 协议）、`Options`；
- 剪枝：`Tactic/Syntax.lean` 的 widget/RPC/TryThis（Editor 专属）；
- 新增：`RolloutSink`（逐节点流式发射 state/tactic/EvalError/logprob/value/选中值）+ `BatchSolver`（题目文件 → `solutions.jsonl`，断点续传）；
- 现状：`tools/` + `app/` 已有雏形 ⇒ 正式化即 `Reap.Training`。

## 3. V2 的严格定义

> 不是"更强"，而是"同一台机器的新档位"。V2 = 元编程运行时 `Reap.Agent`，四个新增语义组件：

```
Reap.Agent
├─ Eff 通道    : run_effect : EffectSpec ⊸ Eff (Obs, EffectTrace)   ← 世界层原语注册表（FFI/子进程外包）
├─ 元状态      : 状态 = (ProofCtx, Env, obs-history, 库 L)           ← 同像性：观测与动作都是 Lean 对象
├─ 动作空间    : 元变换（fill-hole / patch-Expr / addDecl(塔上升) / run-effect）
│                类型检查通过 = 动作合法（零非法率，自由文本 agent 做不到）
├─ 塔上升      : 验证入库 ⇔ 语言塔上升（L_{t+1} = L_t ∪ {verified 原语}）
│                ← 这正是 d_g（抽象深度增长）的可执行定义
└─ 层次不变量  : agent 生成的代码禁止触碰学习器自身（自指切开），训练器只经 harness 固化
```

**与 V1 代码关系**：V1 是 V2 的底（验证器、MCTS、协议、RTTT 全部复用）；V2 只替换"目标谓词"、加"效应接口"与"元动作空间"。架构上是单棵树的上下层，不是两个平行分身。

## 4. 建议的仓库/版本组织（工程结论）

```
reap-core            ← 上游 fork：Core 层（算法+验证器）【三版本共享】
  ├─ v1: Reap.Training   BatchSolver/RolloutSink/RTTT-Sink    （训练 fork）
  └─ v2: Reap.Agent      Eff 通道 + 元动作 + 塔 + 层次不变量    （meta/harness fork，依赖 v1）
harness（已有部分）
  ├─ amdbridge（Lean↔世界的桥：计算/训练/检索/实验）
  └─ trainer（GRPO/TTT loop，价值头+RTTT）
```

理由：Core 只用"一份算法"，V1/V2 只是它上面的两种 problem hat；避免三份代码漂移（上游若改验证器，只需在 Core 一处同步）。

## 5. 结论

- **V1 必要且必须做**：把"给人类用的证明搜索器"改成"给机器用的数据生成器"（无 UI + 全轨迹 + RTTT 挂钩）——训练管线能跑通的唯一形态；
- **V2 是正确方向**：把问题类从"证明"扩张到"任意目标谓词"，且精等于"语言塔上升 ⇔ 库增长"——让 MCTS 直接写 Lean 元程序是"唯一语言闭环"最自然的实现；
- 但 V2 须锁三条红线：**证明≠计算、自指不变量、塔上升验证门**（否则退化成"元编程大杂烩"）；
- 现行工作（V1 雏形 + policy_server/RTTT + amdbridge）＝ V1 既成事实 + V2 harness 种子——版本化是对现状的正确盘点而非新计划。
