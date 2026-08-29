# 10｜MCTS 的用途与意义：从 AlphaGo → AlphaProof → V1/V2（以及别的选择?）

> 归档：严格分析 MCTS 在 AI-Math 管线里的角色；回答“有没有更好的搜索算法/是否真正用满了 TTT-policy+value 与 Lean RL 环境”。

## 0. 一句话定位

MCTS 在这类系统里**不是“搜索”**（找解）这么简单——它是**“值-策略-验证”三者的算法焊点**：搜索把验证器的稀疏终局信号转成**中间状态的价值估计**，再把价值与策略先验按**访问统计学**融合，同时**就地、渐进**地扩展状态图。它的意义=**学习信号的生产机器**，其次才是求解器。

## 1. AlphaGo/AlphaZero：MCTS 的“信任-学习”模型

设状态 $s$，动作 $a$，树内统计 $(N(s), N(s,a), Q(s,a), W(s,a))$。PUCT 选择：

$$\mathrm{score}(s,a) = \underbrace{Q(s,a)}_{\text{价值（经 V 传播）}} + \underbrace{c\,p(a|s)\,\frac{\sqrt{N(s)}}{1+N(s,a)}}_{\text{先验×探索}}$$

AlphaZero 的关键决策是：**放弃 rollout 模拟，直接让 $V_\theta$ 充当叶值**。这带来两个推论：

1. **样本效率**：模拟成本 $O(\text{rollout})$ 被 $O(\text{策略一次前向})$ 替换；
2. **表示耦合**：$V_\theta$ 与 $\pi_\theta$ 共享骨干 → 搜索的价值反馈**直接**回到梯度（这是我们 TTT-P/V 管线的祖先）。

因此 MCTS 的角色是：**用访问统计把“先验质量”与“实际可解性”融合**——它的“价值”不在树的形式，而在**它形成的价值信号的去噪**。

## 2. AlphaProof：把 MCTS 单玩家化、多目标化

AlphaProof（以及我们直接复刻的 Reap）对 AlphaZero 做了三类改造：

- **单玩家、验证终结**：终局= kernel 闭环；深度退回：节点扩展是“确定转移”（Lean 校验），所以*没有*对手的干扰，但**存在 AND/OR 结构**（子目标必须全解）；
- **AND/OR 与 min-backup**（`Tactic/TreeSearch.lean`）：OR 节点取 max，AND 节点值=未解子目标的 $\min$（必须全部可解才算可解）——这使树的结构**精确表达逻辑必然**；
- **访问折扣** $\gamma$（`visit_discount`）与 c 递增：把“搜索深度”折算成**求解概率几何**：
$$Q_{\text{disc}} = \gamma^{-(1-c_{\text{depth}})}\ (\text{代入还原的 PUCT} Q)\quad\text{—— 这正是 AlphaProof 的推广}$$

于是 MCTS 的语义更新为：**它把“我能否证明/证反”估计成功传播为“这个中间状态离证明有多远”**——这正是 Lean 稀疏奖励（$\{0,1\}$ 终局）下训练价值/策略的**唯一可靠转导**：$V_\theta(s)$ 的监督信号来自搜索回传 $Q$（不是终局奖励，终局奖励几乎处处为 0）。

## 3. 我们的 V1：MCTS = RTTT-环境的“采样器+信号机”

V1 中 MCTS 承担三重职能：

$$\underbrace{\text{rollout collection}}_{\text{策略-验证轨迹}}\ \oplus\ \underbrace{\hat Q(s,a)\ \text{每步价值}}_{\text{搜索回传给价值头}}\ \oplus\ \underbrace{\text{在线更新触发}}_{\text{buffer→ttt_step}}$$

关键：**RTTT 与 MCTS 是在线的同一循环**——值头在搜索进行中就被更新（$V \leftarrow V+\alpha_V(G_t - V)$），然后**搜索继续**，下一节点用**已更新的值**选择。这种“边搜索边学”是只有**树+搜索访问统计**支持的（单轨 rollout 没有“价值回传”事件，无从在线更新）。即：

> MCTS 是 TTT 的**事件发生器**：每节点的验证反馈（verdict）→ 价值头/策略的在线梯度源；这依赖搜索的回传结构，**纯 agent rollouts 做不到**。

## 4. 有哪些其他选择？（系统谱系与理由）

#### 候选 1：Best-first + 值（`BestFirst.lean` 已实现）
$$\text{expand } \arg\max_{s\in\text{fringe}} \boxed{V_\phi(s)}$$
- 优点：单轮简单、与 RTTT 兼容；缺点：**没有在线探索平衡（先验信息）**——价值高估会死锁在“局部不可开”分支；树的重用低效。
- 定性：是“MCTS 的一种退化”（$\mathrm{select}=\max V$），对新问题可行、对“先验不可靠”时不稳。

#### 候选 2：A*/IDA*（需 admissible 启发式）
- 需要 $h(s) \le V^{*}$；我们的 $V_\phi$ 是**基于学习的估计，无任何可采纳性保证**——A* 在此严格不适用（会错过最短路证明）。**排除**。

#### 候选 3：Beam / 贪心单轨（标准 LLM agent RL）
- 无树 = 无价值回传；TTT 只有“整轨奖励”，稀疏且高方差。**定为“无搜索的退化”，只作为对照基线**。

#### 候选 4：进化/遗传搜索（程序或符号合成）
- 对“表达式合成”类好；对 Lean 证明状态：状态不可“繁殖”成子代（缺少自然的交叉算子），采样噪声大。**排除为第一选择**。

#### 候选 5：BFS/DFID 无值
- 组合爆炸下毫无效率；仅作为安全下界。

#### 候选 6：**LLM-MCTS 变体（LATS/RAP/ToT）**
- 正是我们领域（LLM 策略+树）的最佳实践族；与 Reap 的差异只在“节点=Lean 态、验证=内核”。**它证明我们选对了算法家族**；本仓库 `TreeSearch/MCTS.lean` + `Tactic/TreeSearch.lean` 已是该家族的核心。

#### 候选 7：**RL 元搜索**（学习“如何搜索”——adaptive hyperparameter / learning-based scheduler）
- 理论上可选，但对“在线 TTT”需要额外 meta-level 训练；与当前 RTTT 冲突（增加信号信道而非简化）。**留作 v3 增强**。

## 5. MCTS 的“不完全 fit”三点与对策（诚实面，v1→v2 需处理）

1. **先验主导性**：PUCT 的 $U$ 项来自 LLM logprobs——Lean 里先验对错误动作给“低但非零”概率，导致树前期污染。对策：**剪枝性先验**（只保留 top-$k$ 合法动作）+ **已验证动作的确定化再注入**（把 logprob 当作“先验核”，不被错误重复污染）。
2. **访问数×值的冗余**：RTTT 后价值头已变，而树内 $Q$ 仍基于旧值。对策：**树降温**（TTT 后对树内节点做 $V$-再校准，以 1 次前向重估/节点，牺牲少量精度换取一致性）——这是 v1→v2 最重要的增量。
3. **树宽×深的预算**：节点扩展即 LLM query（贵），`max_goals/max_steps` 是硬的。对策：**progressive widening 已存在**（`shouldProgressiveSample`）+ **预算指导的宽度衰退**（开始时 6 候选，深层降为 3——我们有 `num_samples` 可调）与**中继扩展**（扩展深度>阈值时批量处理子目标）。

## 6. 结论（严格）

1. MCTS 不是“一个可替换的搜索器”，它是**唯一**同时满足：（a）单玩家多目标树（AND/OR），（b）用 $V_\phi$ 做叶值，（c）在线 TTT 更新的事件生成，（d）固定计算预算下渐进扩展——的算法。**没有比它更合适的**；A* 不可行（heuristic 不可采纳）、Best-first 是退化、Evo 的状态不兼容、beam 不支持值。
2. **要换的不是算法，是“树与值头之间的一致性协议”**：v1 已具备（PUCT/OR-AND/$\gamma$/progressive sampling）；v2 要新加的是 (i) 树降温再校准（应对 TTT 在线更新）（ii) 先验剪枝（应对大动作空间）——这两项是“用满 MCTS × TTT 潜能”的关键。
3. **与 AlphaZero 的继承关系**：V1 = AlphaZero 的“单玩家+多目标”版 + 在线 TTT 版；V2 = 同样的机器、更大的对象域（元程序/工具调用）。MCTS 的机理从头到尾不变——这正是为什么它被 AlphaProof 选中、也理应被我们原样延用：**在“验证器精确+价值可学+策略可学”的三元组下，MCTS 是理论上的首选而非工程上的妥协**。

> 参考对应仓库实现：`Reap/TreeSearch/{Basic,MCTS,BestFirst}.lean`；`Reap/Tactic/{TreeSearch,Step}.lean`。
