# AlphaProof、Value head 与当前 TTT：07 讲义导读

本目录包含两份文件：

- [完整讲义：07_AlphaProof从零到完整机制_搜索_Value与TTT.md](07_AlphaProof从零到完整机制_搜索_Value与TTT.md)
- 本导读：帮助读者快速找到 value head、搜索和当前实现差距的重点章节。

完整讲义按照一次证明实验的时间顺序展开：先介绍实验开始前模型中已有的 policy 与 value，再依次经过 tactic 生成、Lean 验证、value 评估、MCTS backup、PUCT 选边、搜索终止、参数更新和跨证明实例继承。

## 1. 如果最关心 Value head，建议这样阅读

第一步读完整讲义的“第 2 节：实验开始前，模型里已有 Policy 和 Value”。

这一节从零解释：

- 共享 encoder 怎样把 Lean 状态编码成隐藏向量；
- policy decoder 怎样生成 tactic；
- value head 怎样读取同一个隐藏向量并预测长期回报；
- value head 与完整 value network 的区别；
- policy 的下一步动作概率为什么不能替代 value 的长期状态估计。

第二步重点读“第 3 节：AlphaProof 分别怎样训练共享模型、Policy 和 Value head”。

这一节把通用 3B proof network 预训练与 value head 的专门训练分开，并逐阶段说明训练数据、目标、更新对象和公开边界。

第三步读“第 4 节：当前实现的实验起点”。这一节给出当前随机 value head 的实际结构、折扣回报坐标和 distance 变换。

第四步读“第 6 至第 7 节”。这两节说明 value 输出怎样进入 MCTS backup，以及 PUCT 怎样组合 value、policy prior、访问次数和探索项。

第五步读“第 10 至第 13 节”。这些章节解释当前 joint TTT、失败时非零 value target 的来源、更新继承，以及我们是否需要先训练 value。

## 2. Value head 是什么

AlphaProof 的 encoder 先把 Lean 状态文本 \(x\) 映射成隐藏表示：

\[
h=h_\psi(x)\in\mathbb R^d.
\]

其中 \(x\) 是完整 Lean 输入，\(h_\psi\) 是共享 encoder，\(\psi\) 是 encoder 参数，\(d\) 是隐藏维度，\(h\) 是当前证明状态的向量表示。

Policy decoder 读取 \(h\) 并生成候选 tactic。Value head 也读取 \(h\)，但输出状态的长期前景：

\[
g_\phi:\mathbb R^d\longrightarrow\mathcal Y.
\]

\(\phi\) 是 value head 参数，\(\mathcal Y\) 是价值输出空间。完整 value network 是

\[
g_\phi\circ h_\psi:\mathcal X\longrightarrow\mathcal Y.
\]

因此，value head 只指隐藏向量之后的小型输出模块；value network 还包含共享 encoder。Encoder 更新时，value 输出也会改变。

## 3. AlphaProof 的 Value 表示什么

AlphaProof 每执行一个 tactic 使用步长代价

\[
r_j=-1.
\]

从当前状态 \(s_t\) 到终止的累计回报为

\[
G_t=\sum_{j=t}^{T-1}r_j.
\]

若还需 \(L\) 步完成，则

\[
G_t=-L.
\]

所以 AlphaProof value 主要表达预计剩余证明长度：越接近 0，预计离完成越近；越负，预计剩余分支越长。它不是命题可证概率。

AlphaProof 的 value head 在一组离散回报档位上输出 categorical distribution，再计算期望 return。

## 4. AlphaProof 怎样训练 Value head

### 4.1 通用预训练：建立共享表示

AlphaProof proof network 总体约 3B 参数，是 encoder–decoder Transformer。

通用预训练使用约 300B 个公开代码和数学文本 token，采用 next-token prediction，并使用 dropout 与 masked-span reconstruction。

论文还报告：

- Encoder 累计处理约 12T token；
- Decoder 累计重建约 3T token；
- 训练量约等于在数据集上进行 50 个 epoch。

这一阶段建立 encoder 的代码、逻辑和数学表示，以及 policy decoder 的 token 生成能力。论文没有说明这一阶段使用 proof return 或剩余证明步数标签。

因此，300B-token 预训练为 value 提供强共享表示，但它本身不等于完成 value head 的证明距离训练。

### 4.2 Mathlib SFT：首次明确初始化 Value head

Mathlib SFT 使用约 300,000 个 state–tactic 对和约 5M tactic token，数据来自人类编写、Lean 接受的 Mathlib 证明。

一条成功证明同时提供两种标签：

1. 当前状态的正确下一步 tactic，用来训练 policy；
2. 从当前状态到终局的真实剩余步数，用来初始化 value head。

若完整证明长 \(L\) 步，状态 \(s_t\) 位于第 \(t\) 步，则

\[
G_t=-(L-t).
\]

Value head 学习该 return 的 categorical distribution。多子目标状态使用最长未完成分支所对应的 return。

这一步是 AlphaProof 在正式 RL 前获得可用 value 起点的关键。论文正文没有逐项给出 categorical 桶边界、policy/value loss 的精确组合权重、各组件学习率和组件级冻结安排。

论文报告 Mathlib SFT 的计算量约为 10 TPU days。

### 4.3 Main RL：用成功 Proof/Disproof 继续训练

Main RL 从完成预训练和 Mathlib SFT 的 proof network 开始。

训练规模包括：

- 约 80M 自动形式化 Lean 问题；
- 约 3,500 个额外人工形式化问题；
- 约 1M learner training steps。

分布式 actors 使用当前 policy、value 和树搜索尝试 proof 或 disproof。只有成功 proof/disproof 轨迹进入 learner，失败和超时尝试被过滤。

Learner batch 的公开比例是 10% Mathlib SFT 和 90% actor 成功 replay。Policy head 用交叉熵预测成功 tactic；value head 预测当前 proof subgoal 实际获得的 return。

论文报告 main RL 约消耗 80,000 TPU days。产生约 80M 问题课程的自动形式化过程另约消耗 100,000 TPU days。

### 4.4 TTRL：从 Generalist 训练 Specialist

TTRL 从 main-RL generalist 初始化 specialist，不从随机 value 开始。

系统针对每个目标原始难题生成数十万 Lean-valid 变体，再运行与 main RL 类似的 actor、matchmaker 和 learner 流程。

成功 proof/disproof 继续更新 specialist proof network：policy 学成功 tactic，value 学成功轨迹的实际 return。公开论文没有报告只冻结 policy、单独训练 value head 的 TTRL 版本。

## 5. AlphaProof 为什么依赖已经训练好的 Value

MCTS 遇到尚未搜索到底的新叶子时，需要 value 提供临时前景估计。该估计沿树 backup，影响边的 \(Q\)；PUCT 再使用 \(Q\) 分配后续访问。

若 value 持续高估死路，有限预算会向死路倾斜。AlphaProof 通过以下训练链降低风险：

    强共享 encoder
      → Mathlib 真实剩余步数初始化 value head
      → 大规模成功 proof/disproof RL
      → 问题特定 TTRL 继续适应

AlphaProof 的搜索效果来自 value head 结构与长期训练历史的组合。

## 6. 当前实现与 AlphaProof 的核心差距

当前 fresh session 的 value head 随机初始化，只在单个证明实例中进行少量 joint policy/value TTT。

当前输出是 sigmoid 折扣回报坐标，再转换成 search distance。它没有经过 AlphaProof 式的大规模剩余证明步数 SFT，也没有经过 80M 问题和百万级 learner steps 的 main RL。

因此：

- 当前代码能够运行 value-guided MCTS；
- 初始 value 排序缺少 AlphaProof 的训练基础；
- 非终局自举可能继承早期随机排序；
- Loss 下降只说明拟合当前 backup target；
- 搜索收益需要 held-out value 测量和完整 matched search。

合理路径是先从隔离成功证明轨迹训练 head-only value，在未用于训练的状态上验证剩余距离排序，再到真实存在多个合法竞争后继的证明实例中验证搜索收益。Policy 仍需先产生足够多的合法、不同后继。

## 7. 最短阅读路线

只想快速理解整体流程，可阅读完整讲义：

1. 第 2 节：Policy、value head 与 value network；
2. 第 3 节：AlphaProof 各组件的训练过程；
3. 第 5 至第 7 节：候选生成、Lean 验证、value、backup 与 PUCT；
4. 第 10 至第 13 节：当前 TTT、自举信号和 value 训练结论；
5. 第 17 节：AlphaProof 与当前实现的两条完整流程。

如果只保留一句话：

> AlphaProof 的 value head 在 Mathlib SFT 中由真实剩余证明步数初始化，随后在大规模 Main RL 和 TTRL 中继续从成功 proof/disproof 的实际 return 学习；当前随机 head 缺少这段训练历史，因此需要独立训练和验证后，才能稳定承担搜索预算分配职责。
