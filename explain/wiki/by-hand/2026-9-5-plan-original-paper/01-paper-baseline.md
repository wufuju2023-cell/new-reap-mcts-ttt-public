# 01 — AlphaProof 原论文：可对齐的技术基线

本文只记录随附论文明确写出的内容。补充材料中的超参数表、精确层数、bin 数、学习率和 batch size 不在本 PDF 中，不能从正文臆测。

## 1. Lean 环境与 value 的数学语义

**[论文，AP pp. 2–3、9]** 状态是 pretty-printed Lean tactic state，动作是一段 tactic 字符串。每执行一个 tactic 的奖励为 $-1$。

对单目标状态，return 是到终止的奖励和。若一个 tactic 分裂出必须全部完成的独立子目标，return 不是子目标 return 的和，而是它们的最小值：

$$
G(s_{\mathrm{AND}})=\min_i G(s_i).
$$

因为 $G$ 是负的剩余步数，这等价于用最长／最难分支的剩余深度：

$$
G(s)=-D(s),\qquad
D(s_{\mathrm{AND}})=\max_i D(s_i).
$$

这不是一个“能否证明”的二元分类器。它决定了 search 对并列子目标的资源分配：快的分支完成后，搜索仍应集中在最难的未完成分支。

## 2. 模型

**[论文，AP pp. 3、9–10]** AlphaProof 使用约 3B 参数的 encoder-decoder Transformer。

- encoder 读 tactic state；
- decoder 是 policy，同时采样 $K$ 个 tactics；
- encoder 顶部的 value head 输出 return 的**分类分布**，再得到期望 value。

因此论文的 value 是 joint policy/value 模型的一部分，语义是负的剩余关键路径长度，而非一个与 policy 无关的任意分数。

## 3. 搜索

**[论文，AP pp. 9–10]** 搜索是 AlphaZero / Sampled MuZero 风格的单一全局 proof tree。一次 proof attempt 从 root 一直扩展同一棵树，直到找到已验证的 proof / disproof 或耗尽预算；它不在每一步贪心提交一个 tactic 后重启新树。

普通 OR 节点的选择项是：

$$
Q(s,a)+c(s)\,\pi(a\mid s)^{1/\tau}
\frac{\sqrt{\sum_b N(s,b)}}{N(s,a)+1}.
$$

其中论文令：

$$
Q(s,a)=\gamma^{-V(s,a)-1}.
$$

$V$ 的符号和尺度必须保持“负的剩余步数”这一约定，否则这个 $Q$ 变换不再有原本含义。

论文还明确包含四个不能省略的搜索机制：

1. **invalid action discard**：Lean 无法执行的 tactic 不进入树。
2. **等价后继合并**：到达等价 Lean state 的多个 tactics 合并，保留字符串长度／执行代价更低者。
3. **progressive sampling**：高访问节点按 $n(s)\le C N(s)^\alpha$ 再采样一批 $K$ 个 tactics，避免固定小候选集锁死关键路径。
4. **AND node**：多子目标状态在选择时优先最难的未证明子目标，回传时取 child value 的最小值。

## 4. 训练闭环

**[论文，AP pp. 2–3、10–11]** 训练不是“给一批人工题做 SFT”：

| 阶段 | 论文报告 |
| --- | --- |
| 基础预训练 | 约 300B code / math tokens；encoder 实际处理约 12T tokens，decoder 约 3T |
| Lean SFT | 约 300k Mathlib state–tactic pairs，约 5M tactic tokens |
| auto-formalization | 约 100 万自然语言题生成约 8000 万 Lean statements |
| main RL | 约 100 万 training steps；matchmaker、分布式 actors、central learner |
| learner batch | 90% 已验证的 self-generated replay + 10% Mathlib SFT |
| compute | SFT 约 10 TPU-days；auto-formalization 约 100,000 TPU-days；main RL 约 80,000 TPU-days |

matchmaker 会把题目随机设为 prove 或 disprove，根据新颖性、失败／成功的混合程度和近期历史决定优先级；多次失败的题会获得更大 search budget。成功 proof/disproof 中的 state–tactic pairs 进入训练，timeout 不直接作为 learner 的监督样本。

这一点很重要：auto-formalization 不必总是忠实翻译原自然语言题。只要 Lean statement 合法，它仍可以成为可 prove 或 disprove 的 grounded RL 起点。

## 5. TTRL 的正确含义

**[论文，AP pp. 3、11–12]** Test-Time RL / TTRL 从 main-RL generalist 初始化一个 target specialist，但先构造目标题 $T$ 的变体课程 $V_T$：

1. 用 problem–variant examples 提示生成器；
2. 生成简化、泛化、lemma、类比、分解等 Lean variants，并加入程序化局部变换；
3. 对所有候选做 Lean syntax validation、去重；
4. 以相似的优质变体为种子递归演化，论文报告最多 $N_{\mathrm{evo}}=15$ 轮；
5. 在 $T\cup V_T$ 上运行与 main RL 同构的 matchmaker + actors + learner 闭环。

论文报告每个 target 有数十万级有效变体；正文图示约 400k，方法描述为 hundreds of thousands。其 TTRL ablation 覆盖 10、100、1k、10k、100k variants；结果表的 target compute 是 50–500 TPU-days。模型参数量不是这一机制的充分替代品。

## 6. 与 Reap 对齐时不能偷换的词

| 词 | 论文中的最低含义 |
| --- | --- |
| value | 预测负的剩余最长分支长度的分类 return model |
| MCTS | 有 policy prior、value backup、AND/OR、持续 proof tree 的搜索 |
| RL replay | 从 Lean-verified proof/disproof 的轨迹生成训练对 |
| TTRL | target + 大量相关 variants 上的 focused RL，不是只对 target 做一次 CE 更新 |
| solve | 有独立 Lean 最终检查的闭合证明，而非某一节点返回了看似合理的 tactic |

后续页面用这些定义判断差异；不能只因接口也叫 value、MCTS 或 TTT 就把两个系统视作同一件事。
