# 7｜Reap 多版本化：V1（Training fork）与 V2（Meta/Harness）
> 归档：初始想法 + 版本化定性分析（Core / Reap.Training / Reap.Agent）
i think thus the original reap-repo need to have more version, v1 is the one which is modifyed to fit the training(not the reap!! in infoview), v2 may neeed to modified into a more meta-programming and harness-lean-like version. answer me first,
回答：reap 的多版本化——先定性，不写代码
一、先把三个对象钉死
与上游 reap 关系
权威原版，我们只同步不魔改
剪枝 + 增加 hooks，不改核心语义
在 V1 之上扩展问题类（证明 → 任意任务谓词），不是分叉是层叠
二、V1 为什么必须存在（必要性论证）
上游 reap 的问题不是算法，是形态：
UI 耦合：Tactic/Syntax.lean 的 InfoView/RPC/React widget 占了一半代码，训练毫不需要；
无批处理：一次一个 session，训练要 10³~10⁵ 个 rollout，必须无状态 driver；
无轨迹面：raw_tree.json 有树但没有"每个状态的（state, tactic, verdict, logprob, value）"训练样本面；
无 RTTT 挂钩：验证反馈的 EvalResult 只在内存里，训练要流式消费。
V1 的严格做法（对上游做减法+加钩子，不动内核）：
保留：TreeSearch/{Basic,MCTS}（通用引擎）、Tactic/Step.lean（安全验证器）、Generator（LLM 协议）、Options
剪枝：Tactic/Syntax.lean 的 widget/RPC/TryThis（Editor 专属）
新增：RolloutSink（逐节点流式发射：state、tactic、EvalError、logprob、value、选中/回传值）+ BatchSolver（题目文件 → solutions.jsonl，断点续传）——我们 tools/ + app/ 已有雏形，正式化即成 Reap.Training
三、V2 的严格定义（不是"更强", 是"同一台机器的新档位"）
V2 = 元编程运行时（Reap.Agent），四个新增语义组件：
Reap.Agent
├─ Eff 通道    : run_effect : EffectSpec ⊸ Eff (Obs, EffectTrace)   ← 世界层原语注册表（FFI/子进程外包）
├─ 元状态      : 状态 = (ProofCtx, Env, obs-history, 库 L)           ← 同像性：观测与动作都是 Lean 对象
├─ 动作空间    : 元变换（fill-hole / patch-Expr / addDecl(塔上升) / run-effect）
│                类型检查通过 = 动作合法（零非法率，这是自由文本 agent 做不到的）
├─ 塔上升      : 验证入库 ⇔ 语言塔上升（L_{t+1} = L_t ∪ {verified 原语}）
│                这正是我们 d_g（抽象深度增长）的可执行定义
└─ 层次不变量  : agent 生成的代码禁止触碰学习器自身（自指切开），训练器只经 harness 固化
与 V1 代码关系：V1 是 V2 的底（验证器、MCTS、协议、RTTT 全部复用）；V2 只替换"目标谓词"、加"效应接口"与"元动作空间"。因此它们在架构上是单棵树的上下层，不是两个平行分身。
四、建议的仓库/版本组织（工程结论）
reap-core            ← 上游 fork：Core 层（算法+验证器）【三版本共享】
  ├─ v1: Reap.Training   BatchSolver/RolloutSink/RTTT-Sink     （训练 fork）
  └─ v2: Reap.Agent      Eff 通道 + 元动作 + 塔 + 层次不变量     （meta/harness fork，依赖 v1）
harness（已有部分）
  ├─ amdbridge（Lean↔世界的桥：计算/训练/检索/实验）
  └─ trainer（GRPO/TTT loop，价值头+RTTT）
理由：Core 只用“一份算法”，V1/V2 只是它上面的两种“problem hat”；避免三份代码漂移（上游如果改验证器，我们需要在 Core 一处同步）。
五、一句话回答你的问题
V1 必要且必须做：它不是改进，是把"给人类用的证明搜索器"改成"给机器用的数据生成器"（无 UI + 全轨迹 + RTTT 挂钩）——这是训练管线能跑起来的唯一形态。
V2 是正确方向：它把问题类从"证明"扩张到"任意目标谓词"，并且它精确地等价于我们前面定义的"语言塔上升 ⇔ 库增长"——让 MCTS 直接写 Lean 元程序，是"唯一语言闭环"最自然的实现；
但V2 需要在设计期就锁定三条红线（证明≠计算、自指不变量、塔上升验证门）——否则会退化成"元编程的大杂烩"。
我们的现行工作（V1 雏形 + policy_server/RTTT + amdbridge）正好是 V1 的既成事实 + V2 的 harness 种子，所以这个版本化是对现状的正确盘点，而不是新计划。
需要的话，下一步我可以把这三层写成 reap-core / Reap.Training / Reap.Agent 的正式接口规格草案（挂在 explain/6-* 下），先不改代码——要吗？
