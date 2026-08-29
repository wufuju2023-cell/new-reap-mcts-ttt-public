# 01. 约束传播与状态化执行：把“多轮”变成可搜索对象

> 本节回答工程问题：“多轮工具调用”为什么以及如何在 v2（CPU）里**不靠 RL 也能被当作搜索对象**。

## 1. 为什么多轮不能是“一坨文本”（否定性论证）

如果工具调用序列 $a_1..a_m$ 由单次文本生成、然后用一个总分评估，则：
$$\mathrm{credit}(a_i)\ \mathrm{cannot\ be\ assigned}\ \Rightarrow\ \mathrm{Var}[\nabla_\theta]\ \uparrow\ (\text{长链}),$$
且**树无法就中间 $s_t$ 复用**（§10）。因此我们逆其道而行：

## 2. 状态化（每个 sub-turn 都有类型化状态快照）

$$\text{turn}_i\ \text{=}\ \big(s_{i-1}, a_i, \mathrm{obs}_i,\ s_i\big) \quad \text{且}\ \mathrm{obs}_i \in \mathrm{TypedObs}$$

在代码即：`RolloutSink.node_visited` 的每条记录就是 $(\text{state\_pp}, \text{tactic}, \text{verdict})$ 三元组——整链可重放（`tree_hash`+`state_key` 幂等键）。

## 3. 约束：把“工具回合数”纳入搜索预算（PUCT 的观测）

- 回合预算 $B_{\mathrm{turn}}$、每回合查询预算 $B_{\mathrm{llm}}$；树宽=候选原语（top-k by π）；树深=回合数。
- **无 miner**：不生成新任务，只沿目标分解；树内新增“slot”类型=**L(库)作为额外可复用上下文**（类似 AlphaProof 的“SMT slot”推广）。

## 4. 验证当回路（多轮的核心价值）

$$\underbrace{\text{run}}_{\text{tool}}\ \to\ \underbrace{\text{verdict}}_{\text{kernel}}\ \to\ \underbrace{\text{next state}}_{\text{typed}}\ \to\ \ldots$$
——这在 Reap 代码中就是：`Step.lean evalTacticStr`（每轮执行+校验）→ `TreeSearch`（PUCT 选下一轮）→
`RolloutSink`（记录）→（若 GPU 侧）`/ttt_step`。**多轮= 同一 loop 的多次迭代**，而不是“一次长生成”。

## 5. 与 LLM agent（DeepSeek 类）多轮对比（本轮重点）

| | LLM agent 多轮 | v2/C 多轮（本协议） |
|---|---|---|
| 多轮状态 | 上下文 tokens | **类型化状态快照**（每轮可重放） |
| 中断恢复 | 上下文丢失（长链） | checkpoint：任一验证点续作（幂等） |
| 回溯 | 不能（文本流） | 树：PUCT 回退/重展开 |
| 多轮计预算 | 无 | $B_{turn}$/$B_{llm}$ 与墙钟 |
| 对“顺序”负责 | 模型自觉 | **树访问统计+值头**（Q 传播） |
| 库增长 | 无（最多文档） | **塔上升**（$L_{t+1}$ 单调） |

## 6. 元编程 v2（CPU/no-miner）收尾

- meta-programming = 同一协议下动作换成“元动作”（addDecl/patch/fill-hole）——树仍可行；
- multi-turn 在多轮内完成“局部库”“局部断言转移”——而**库上升**本身是 turn 间共享的隐式构建；
- 风险与红线（§7-v1-v2 三条）：证明≠计算、自指、塔上升门——这些同样是多轮 tool-call 协议的红线：
  每轮结束前：verifier 必须裁决本轮效果（否则该 effect **不可进入**下一轮状态，只能作为“观测引用”）。
