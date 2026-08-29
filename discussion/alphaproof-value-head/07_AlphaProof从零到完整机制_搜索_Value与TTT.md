# 从一次证明实验看懂 AlphaProof、Value head 与当前 TTT

本文按照一次证明实验发生的顺序讲解：实验前准备什么；模型怎样生成 tactic；Lean 怎样建立真实搜索树；value 怎样估计状态；PUCT 怎样分配预算；何时产生学习信号；参数怎样更新和继承。

主线采用 [AlphaProof 的 Nature 论文](https://www.nature.com/articles/s41586-025-09833-y) 的公开机制。每一步讲完 AlphaProof 后，紧接着说明本项目当前实现和差距。

先给出贯穿全文的结论：

> AlphaProof 的搜索很依赖一个经过大量离线训练、又经过大规模强化学习继续更新的 value。它进入正式搜索和 TTRL 时，value 已学过大量成功证明中的剩余步数。我们当前 fresh session 的 value head 从随机参数开始，只做很少的题内联合更新，因此不能预期它自动具有 AlphaProof value 的判断力。若希望 value 稳定引导搜索，需要先用真实证明轨迹训练并验证 value；同时 policy 要能产生足够多的合法、不同后继，否则 value 没有分支可比较。

下面从头解释这段话中的每个概念。

---

## 1. 一次实验解决什么

**原始难题**是最终希望解决或用于能力评测的根定理，例如冻结的 Pell、F1 或 challenge 根题。

**中间课程变体**是训练侧的独立 Lean 命题，通常更简单，用来练习归纳、存在见证和改写等结构。它可以提供可验证经验，但它的成功不能记作原始难题成功。中间课程变体应与测试根题族隔离，不能包含原始难题答案或派生状态。

**一次证明实例**是固定一个原始难题或中间课程变体，再固定模型、session、seed、prompt、Lean 环境和搜索预算后进行的一次完整运行。

### 1.1 根 Lean 状态

证明实例开始时，Lean 把待证定理转成根状态。记所有合法 Lean tactic state 的集合为

\[
\mathcal S.
\]

当前状态记为

\[
s\in\mathcal S.
\]

状态 \(s\) 包含局部变量、假设和全部未完成目标，例如：

```lean
a b : ℤ
h : a ∣ b
⊢ ∃ k, b = a * k
```

全文中，\(s\) 始终表示真实 Lean 状态。

### 1.2 模型真正读取的输入

定义状态到模型文本的映射

\[
\operatorname{Obs}:\mathcal S\longrightarrow\mathcal X,
\qquad x=\operatorname{Obs}(s).
\]

其中 \(\mathcal X\) 是完整输入文本的集合，\(x\) 是本次真正送入模型的文本。它可以包含 Lean 状态、系统指令、动作协议、检索引理和 thought prefix。

全文统一用 \(x\) 表示完整输入，不使用未定义的 `c`。同一个状态 \(s\) 搭配不同 prompt、检索结果或 thought prefix，会得到不同的 \(x\)。

---

## 2. 实验开始前，模型里已有 Policy 和 Value

### 2.1 共享状态表示

模型先把输入 \(x\) 编码成隐藏向量：

\[
h_\psi:\mathcal X\longrightarrow\mathbb R^d,
\qquad h=h_\psi(x).
\]

这里 \(h_\psi\) 是编码过程，\(\psi\) 是相关参数，\(d\) 是隐藏维度，\(h\in\mathbb R^d\) 是模型对当前状态的内部表示。Policy 和 value 都使用这个共享表示。

### 2.2 Policy：提出下一步 tactic

记所有有限 tactic 字符串的集合为 \(\Sigma^*\)。Policy 定义为

\[
\pi_\theta:\mathcal X\longrightarrow\Delta(\Sigma^*).
\]

其中 \(\theta\) 是 policy 参数，\(\Delta(\Sigma^*)\) 是 tactic 上的概率分布集合，\(\pi_\theta(a\mid x)\) 是输入 \(x\) 时生成完整 tactic \(a\) 的概率。全文中，\(a\) 始终表示 tactic。

若 \(a\) 的 token 是 \((z_1,\ldots,z_L)\)，则

\[
\pi_\theta(a\mid x)
=\prod_{j=1}^{L}p_\theta(z_j\mid x,z_1,\ldots,z_{j-1}).
\]

Policy 回答：“根据当前状态和模型经验，下一条 tactic 写什么？”高概率动作仍可能被 Lean 拒绝，也可能合法但走入死路。

### 2.3 Value head：估计状态的长期前景

先定义要预测的量。AlphaProof 每执行一个 tactic 使用步长代价

\[
r_j=-1.
\]

从状态 \(s_t\) 到终止的累计回报为

\[
G_t=\sum_{j=t}^{T-1}r_j,
\]

其中 \(T\) 是终止时刻。若还需 \(L\) 步完成，则

\[
G_t=-L.
\]

回报越接近 0，预计离完成越近；越负，预计证明越长。

Value head 是隐藏向量到价值输出的小模块：

\[
g_\phi:\mathbb R^d\longrightarrow\mathcal Y.
\]

其中 \(\phi\) 是 head 参数，\(\mathcal Y\) 是输出空间。完整 value network 是

\[
\operatorname{Value}_{\psi,\phi}
=g_\phi\circ h_\psi:
\mathcal X\longrightarrow\mathcal Y.
\]

Value head 只指末端小模块 \(g_\phi\)；value network 还包含共享表示 \(h_\psi\)。共享表示更新时，value 输出也会改变。

本文把 AlphaProof 的状态价值预测记为

\[
\widehat G_{\psi,\phi}(s)
\approx\mathbb E[G_t\mid s_t=s].
\]

它表示在当前策略和后续搜索条件下，从状态 \(s\) 开始预计还有多少负步长回报。

AlphaProof 的 value head 输出离散回报档位上的概率。设档位为 \(\mathcal B=\{b_1,\ldots,b_M\}\)，则

\[
g_\phi(h)\in\Delta(\mathcal B),
\]

系统再从该分布计算期望回报。

### 2.4 为什么 Policy 不能替代 Value

Policy 判断一条动作是否符合模型的局部生成经验。Value 判断动作执行后的状态长期是否有希望。

例如，`simp` 可能有很高 policy 概率，却只改变表面形式；一个概率较低的存在见证动作可能打开证明路线。Policy 适合提出候选和给初始先验，value 适合在候选通过 Lean、成为真实子状态以后估计搜索前景。

---

## 3. AlphaProof 分别怎样训练共享模型、Policy 和 Value head

这里需要把“3B proof network 的通用预训练”和“value head 的价值训练”分开。300B-token 语言模型预训练本身不等于已经完成 value head 的证明距离训练。完整过程分成三段：

1. 通用预训练主要建立共享 encoder 与 policy decoder 的代码、数学和语言能力。
2. Mathlib SFT 在训练 Lean tactic policy 的同时，首次明确地用剩余证明步数初始化 value head。
3. Main RL 和 TTRL 再用成功 proof/disproof 的实际 return 继续训练 policy 与 value。

### 3.1 先看 AlphaProof 的组件关系

AlphaProof 的 proof network 总体约有 3B 参数，是一个 encoder–decoder Transformer。

Encoder 接收 pretty-printed Lean 状态 \(x\)，产生共享表示：

\[
h=h_\psi(x)\in\mathbb R^d.
\]

这个表示送往两个输出分支：

\[
h
\longrightarrow
\begin{cases}
\text{decoder / policy：生成 }K\text{ 条 tactic},\\
\text{value head：预测当前状态的未来 return}.
\end{cases}
\]

因此需要区分三组对象。

**共享 encoder 参数 \(\psi\)** 决定怎样理解 Lean 状态。Policy 和 value 都依赖它。

**Policy decoder 参数 \(\theta\)** 决定怎样根据共享表示自回归生成 tactic。

**Value head 参数 \(\phi\)** 位于 encoder 之上，把共享表示映射成回报档位的 categorical distribution。

论文公开了 proof network 总体约 3B 参数、encoder–decoder 架构以及 categorical value head。公开正文没有给出 encoder、decoder 和 value head 各自精确占多少参数，也没有逐层列出 value head 的矩阵形状。关键架构超参数被指向补充表；本文不对未列出的形状和参数量作推断。

### 3.2 第一阶段：通用预训练训练了什么

通用预训练数据约为 300B 个公开代码和数学文本 token。目标包括 next-token prediction，并使用 dropout 和 masked-span reconstruction 作正则化。

论文还给出训练量口径：encoder 共处理约 12T token，decoder 共重建约 3T token，约相当于在该数据上训练 50 个 epoch。

这一阶段明确训练的是 proof network 的通用表示与生成能力：

- Encoder 学习代码、逻辑结构和数学文本的表示。
- Decoder，也就是后来的 policy，学习预测和生成 token。
- 这些参数会为后续 Lean SFT 提供初始化。

论文明确描述这一阶段使 policy decoder 获得程序语法、逻辑结构和数学语言能力。它没有说明在通用预训练阶段使用 proof return 或剩余证明步数标签，也没有说明 value head 此时接受了独立的价值监督。

因此，value head 的 AlphaProof 特有训练不能从“300B token 预训练”直接推出。共享 encoder 在这一阶段得到强表示；value head 的剩余步数语义在下一阶段才被明确建立。

公开正文也没有逐项说明：value head 在通用预训练期间是否已经实例化、若已实例化是否冻结、是否存在辅助 loss。可确认的事实是，该阶段公开的目标是语言建模与 span reconstruction，value 的证明距离监督首次明确出现在 Mathlib SFT。

### 3.3 第二阶段：Mathlib SFT 怎样专门初始化 Value head

Mathlib SFT 使用约 300,000 个 state–tactic 对，包含约 5M tactic token，数据来自人类编写并由 Lean 接受的 Mathlib 证明。

考虑一条完整证明：

\[
s_0\xrightarrow{a_0}s_1
\xrightarrow{a_1}\cdots
\xrightarrow{a_{L-1}}s_L=s_{\mathrm{solved}}.
\]

其中：

- \(L\) 是整条轨迹的 tactic 步数；
- \(s_t\) 是第 \(t\) 步前的 Lean 状态；
- \(a_t\) 是该状态下人类证明采用并由 Lean 接受的 tactic；
- 从 \(s_t\) 到终局还剩 \(L-t\) 步。

这条轨迹同时产生两种监督。

#### Policy 监督

Policy 学习从 \(x_t=\operatorname{Obs}(s_t)\) 生成 \(a_t\)。其概念损失为

\[
\mathcal L_{\mathrm{policy}}^{\mathrm{SFT}}
=-\sum_t\log\pi_\theta(a_t\mid x_t).
\]

这个训练改善 Lean 语法、状态理解和专家 tactic 模仿。

#### Value head 监督

每步奖励为 \(-1\) 时，状态 \(s_t\) 的真实剩余 return 为

\[
G_t=-(L-t).
\]

Value head 不直接回归一个任意实数；它把 value 参数化为回报档位上的 categorical distribution。设档位集合为

\[
\mathcal B=\{b_1,\ldots,b_M\},
\]

目标分布为 \(z_t(b)\)，预测分布为

\[
p_{\psi,\phi}(b\mid x_t).
\]

概念上的 value 交叉熵为

\[
\mathcal L_{\mathrm{value}}^{\mathrm{SFT}}
=-\sum_t\sum_{b\in\mathcal B}
z_t(b)\log p_{\psi,\phi}(b\mid x_t).
\]

训练后，从该分类分布计算期望 return：

\[
\widehat G_{\psi,\phi}(s_t)
=\sum_{b\in\mathcal B}
b\,p_{\psi,\phi}(b\mid x_t).
\]

这一步才是“AlphaProof 在 RL 前训练 value head”的核心。Value head 看到的标签不是“该命题可证的概率”，而是成功 Mathlib 证明结构给出的剩余证明距离或相应 return。

多子目标状态的 return 遵循 AlphaProof 的 AND 语义：全部子目标都需完成，整体 return 由最长证明分支决定。线性轨迹中的 \(L-t\) 是最容易理解的特例。

论文正文说明 SFT 会进一步训练 policy，并初始化 value head。它没有在正文逐项说明：

- categorical 桶的全部边界与目标投影细节；
- policy loss 与 value loss 的精确权重；
- SFT 中 encoder、decoder、value head 是否使用不同学习率；
- 是否存在分阶段冻结或 warmup；
- 每条证明轨迹怎样在所有复杂 AND 状态上具体展开成训练行。

公开表述称整个 proof network 进行 SFT，并同时描述 policy refinement 和 value initialization；正文没有报告某个组件被冻结。因此可以确认两种目标共同用于该阶段，不能进一步断言未公开的参数冻结细节。

### 3.4 第三阶段：Main RL 怎样继续训练 Value head

Main RL 从已经完成预训练和 Mathlib SFT 的 proof network 开始。训练课程主要包含约 80M 自动形式化 Lean 问题，另有约 3,500 个人人工形式化问题。系统运行约 1M learner steps。

Actor 使用当前 policy、value 和树搜索尝试 proof 或 disproof。完整成功轨迹经过 Lean 验证后进入 replay；超时和失败尝试被过滤，不参与网络更新。

Learner 的 batch 按固定比例混合：

- 约 10% 来自 Mathlib SFT；
- 约 90% 来自 actor 成功 proof/disproof 的 replay buffer。

对 replay 中的状态–动作样本：

- Policy head 用交叉熵预测成功轨迹中的 tactic。
- Value head 预测当前 proof subgoal 实际获得的 return。

也就是说，Main RL 的 value 标签来自已经完成的 proof/disproof，而不是来自“搜索失败但看起来有希望”的路径。若成功轨迹从状态 \(s_t\) 到该子目标终局实际还需 \(L_t\) 步，则 value 学习相应的负步长 return；多子目标仍按最长分支语义处理。

论文称 learner 持续更新 proof network parameters，并分别说明 policy head 与 value head 的训练目标。公开正文没有逐项给出：

- Encoder、decoder、value head 的精确梯度冻结安排；
- Policy loss 与 value loss 的组合系数；
- categorical target 的全部数值桶；
- 每个组件的优化器状态与学习率；
- Value 预测在不同训练阶段的单独离线校准结果。

因此可以确认 Main RL 会继续训练 value head，并会更新整个 proof network；无法仅凭正文把提升拆成“共享 encoder 贡献”“policy decoder 贡献”和“value head 单独贡献”。

### 3.5 第四阶段：TTRL 怎样更新 Value head

TTRL 先从 main-RL generalist 初始化 specialist。它围绕原始难题 \(T\) 和数十万 Lean-valid 变体 \(V_T\) 运行与 Main RL 相同的核心学习循环。

成功 proof/disproof 提供状态–tactic 对并更新 specialist proof network。由于 TTRL 明确复用 Main RL 的 learner 过程，policy 继续学习成功 tactic，value 继续学习成功轨迹在当前子目标获得的 return。

TTRL 的训练对象是 specialist proof network，并继续使用 policy 与 value 两种目标，同时使用大规模问题特定课程。公开正文没有报告只冻结 policy、单独微调 value head 的 TTRL 版本，也没有提供组件级冻结表。

### 3.6 把每一部分的训练历史串起来

**共享 encoder**：先由 300B-token 语言/代码/数学预训练建立表示；随后作为 proof network 的一部分参与 Mathlib SFT、Main RL 和 TTRL。正文没有给出各阶段组件级冻结表。

**Policy decoder**：预训练时做 token 生成；Mathlib SFT 学人类 Lean tactic；Main RL 和 TTRL 学成功 proof/disproof 中的 tactic。

**Value head**：通用预训练没有公开的 proof-return 监督；Mathlib SFT 首次明确用剩余证明步数初始化；Main RL 和 TTRL 再用成功 proof/disproof 的实际 return 持续更新。

**自动形式化模型与 TTRL 变体生成器**：它们是用于产生训练命题和课程的独立 Gemini 系统，不是 proof network 的 value head，也不在一次 proof search 中替 value 打分。

### 3.7 这一训练史为什么重要

AlphaProof 的搜索使用 value 来估计未展开叶子，并通过 PUCT 分配大量搜索预算。这个 value 同时依赖：

1. 预训练 encoder 提供的强状态表示；
2. Mathlib SFT 对 value head 的真实剩余步数初始化；
3. Main RL 中大量成功 proof/disproof 的 return 更新；
4. TTRL 中问题特定成功轨迹的继续适应。

所以“AlphaProof 有一个 value head”只描述了结构；“这个 value head 已经怎样训练”才解释了它为什么能参与搜索。我们当前随机 head 与 AlphaProof 的主要差距集中在第二至第四项，而不仅是 7B/9B 基座是否做过通用语言模型预训练。

---

## 4. 当前实现的实验起点

当前搜索 session 使用冻结基座、session LoRA 和 session value head。

记冻结基础参数为 \(\theta_0\)，LoRA 为 \(\delta\theta\)，当前 policy 为

\[
\pi_{\theta_0+\delta\theta}(a\mid x).
\]

Fresh LoRA 初始与基座等价，\(\theta_0\) 在 TTT 中冻结。

当前 value head 为

\[
u_{\psi,\phi}(x)=
\sigma\!\left(
W_2\operatorname{SiLU}(W_1h_\psi(x)+b_1)+b_2
\right).
\]

其中 \(W_1\in\mathbb R^{256\times d}\)、\(b_1\in\mathbb R^{256}\)、\(W_2\in\mathbb R^{1\times256}\)、\(b_2\in\mathbb R\) 是 head 参数；\(\operatorname{SiLU}(z)=z\sigma(z)\)；\(\sigma(z)=1/(1+e^{-z})\)。

输出 \(u_{\psi,\phi}(x)\in(0,1)\) 是折扣回报坐标，不是命题可证概率。Fresh session 的 head 随机初始化。

代码把它转为正 distance：

\[
d_{\psi,\phi}(x)=1+
\frac{\log(\max(u_{\psi,\phi}(x),\varepsilon))}{\log\gamma},
\]

其中 \(0<\gamma<1\) 是折扣因子，\(0<\varepsilon<1\) 是 value floor。逆变换为

\[
u=\max\left(\varepsilon,
\exp((d-1)\log\gamma)\right).
\]

未触底时 \(u=\gamma^{d-1}\)。例如 \(\gamma=0.99\)、\(d=37\) 时，\(u\approx0.696\)，表示约 37 的距离坐标。

AlphaProof 的 value 已学过大量真实剩余步数；当前 fresh value 的早期排序来自随机 head 与基座隐藏表示的组合。这一训练来源差距已经确定，实际损害大小仍需实验测量。

---

## 5. 第一次扩展：Policy 生成，Lean 验证

根状态为 \(s_0\)，输入为 \(x_0=\operatorname{Obs}(s_0)\)。Policy 采样 \(K\) 个 tactic：

\[
a_1,\ldots,a_K\sim\pi_\theta(\cdot\mid x_0).
\]

每个候选交给 Lean。定义状态转移

\[
\operatorname{Step}:\mathcal S\times\Sigma^*
\longrightarrow\mathcal S\cup\{\bot\}.
\]

若 \(\operatorname{Step}(s_0,a_i)=\bot\)，候选因语法、类型或目标错误被拒绝。若输出 \(s_i'\in\mathcal S\)，树加入真实边

\[
s_0\xrightarrow{a_i}s_i'.
\]

不同 tactic 产生相同规范化状态时会合并后继。重复仍消耗生成和 Lean 执行成本，只是不新增节点。

Value 只能评价通过 Lean 的子状态。所有候选非法时，value 没有分支可比较。围栏、空输出、Lean3 风格 tactic、未 `intro` 就归纳等问题首先属于 policy、prompt 或动作协议层。

当前 OpenCode 条件中，query、action 和读取真实 Lean 错误后的 repair 都应由同一学生 policy session 完成。Provider 只查询固定索引，教师网络不参与在线数学内容。

---

## 6. Value 评估叶子，Backup 更新树

合法后继 \(s_i'\) 尚未终局时，AlphaProof 用 \(\widehat G_{\psi,\phi}(s_i')\) 估计剩余回报。当前实现计算 \(u_{\psi,\phi}(x_i')\)，转换为 distance 后交给 Reap。

MCTS 是 **Monte Carlo Tree Search**，中文为蒙特卡洛树搜索。一次 visit 包含：选择已有边、扩展新候选、评估叶子、把结果回传。

回传称为 backup。它更新路径上的访问次数和累计价值。Backup 只更新搜索树内存，不自动更新神经网络。

当前 Reap 累计负 distance。若节点访问 \(n\) 次、累计为 `value_sum`，平均正 distance 为

\[
\bar d=-\frac{\mathrm{value\_sum}}{n}.
\]

训练需要时解码为

\[
u^*=\max\left(\varepsilon,
\exp((\bar d-1)\log\gamma)\right).
\]

Head 输出 \(u\)、HTTP 正 distance \(d\) 和 Reap 负累计是三个不同量。

某些 9B value 请求会先生成 thought prefix，所以一次 value 调用还包含额外 token 和时间。前后 prefix 不同时，比较的是输入编码与 head 的联合管线。

---

## 7. PUCT 选择下一条搜索边

PUCT 常展开为 **Predictor + Upper Confidence bounds applied to Trees**，可理解为“带策略先验的树上置信界规则”。AlphaProof 选择使下式最大的动作：

\[
\operatorname{Score}(s,a)
=Q(s,a)+
c(s)\pi_\theta(a\mid x)^{1/\tau}
\frac{\sqrt{\sum_bN(s,b)}}{N(s,a)+1}.
\]

其中：

- \(s\) 是当前状态，\(x=\operatorname{Obs}(s)\)；
- \(a\) 是一条合法树边；
- \(Q(s,a)\) 是 value、终局和 backup 形成的长期质量；
- \(\pi_\theta(a\mid x)\) 是 policy 先验；
- \(\tau>0\) 是先验温度；
- \(N(s,a)\) 是该边访问次数；
- \(\sum_bN(s,b)\) 是状态全部出边总访问数；
- \(c(s)>0\) 是探索强度。

AlphaProof 使用

\[
c(s)=c_{\mathrm{init}}+
\log\left(
\frac{N(s)+c_{\mathrm{base}}+1}{c_{\mathrm{base}}}
\right),
\]

其中 \(N(s)=\sum_bN(s,b)\)，\(c_{\mathrm{init}}>0\) 是初始探索强度，\(c_{\mathrm{base}}>0\) 控制增长尺度。

本文把树内聚合的负剩余步数记为 \(\overline G(s,a)\)。AlphaProof 将它变换为

\[
Q(s,a)=\gamma^{-\overline G(s,a)-1}.
\]

若预计还需 \(L\) 步，\(\overline G(s,a)\approx-L\)，所以

\[
Q(s,a)=\gamma^{L-1}.
\]

距离短时 \(Q\) 大；访问少时探索项大。Policy 提供初始先验，value 通过 backup 影响 \(Q\)，PUCT 组合它们决定下一次预算。

---

## 8. 重访、继续采样与多子目标

AlphaProof 使用 progressive sampling，避免第一批坏候选永久锁死状态：

\[
n(s)\le C N(s)^\alpha.
\]

\(n(s)\) 是已采样批次或相应计数，\(N(s)\) 是状态访问次数，\(C>0\) 控制扩宽速度，\(\alpha>0\) 控制增长率。状态反复被 PUCT 选中后，可以再生成一批候选。

本项目旧 C 曾把每个 `(state, policy_version)` 的 `4+2` 当作一生额度，前六次全失败会锁死根状态。C6 恢复后续 visit 的继续采样，并沿原 session RNG 状态推进。旧 C 与 A 的探索机会不同。

一个目标有多种 tactic 可选，是 OR 关系；一个 tactic 产生多个子目标时，全部子目标必须完成，是 AND 关系。若子目标还需 \(L_1,\ldots,L_m\) 步，整体距离为

\[
L_{\mathrm{AND}}=\max_iL_i,
\]

相应负回报为

\[
G_{\mathrm{AND}}=-L_{\mathrm{AND}}=min_i(-L_i).
\]

完整证明树因此是 AND–OR 树。

---

## 9. 搜索结束与 AlphaProof 学习

某条路径关闭全部目标后，系统从根状态独立重放完整 tactic 序列。只有 Lean replay 通过，原始难题或中间课程变体才算成功。

达到 visit、token 或时间上限时，证明实例失败。预算耗尽只说明当前模型和预算没有找到证明，不能把状态标成数学负例。

AlphaProof 主 learner 使用成功 proof/disproof 轨迹。Policy 损失可写为

\[
\mathcal L_{\mathrm{policy}}^{\mathrm{AP}}
=-\sum_t\log\pi_\theta(a_t\mid x_t).
\]

Value 同时使用成功轨迹的真实剩余回报。失败搜索影响 matchmaker、课程和预算，不直接进入 learner。

```text
已训练 policy/value
  → MCTS 搜索
  → Lean 验收成功 proof/disproof
  → 成功轨迹进入 learner
  → 更新 policy/value
```

---

## 10. 当前实现怎样在搜索途中做 TTT

当前实现允许非终局 `search_visit_backup` 更新。

某个 OR 节点有合法候选 \(a_1,\ldots,a_m\)，访问数为 \(n_1,\ldots,n_m\)。定义

\[
w_i=\frac{n_i}{\sum_{k=1}^{m}n_k},
\qquad\sum_iw_i=1.
\]

\(w_i\) 是当前搜索的访问分布。若 \(a_i\) 的 token 为 \((z_{i,1},\ldots,z_{i,L_i})\)，policy 损失为

\[
\mathcal L_{\mathrm{policy}}
=-\sum_iw_i\sum_j
\log p_\theta(z_{i,j}\mid x,z_{i,<j}).
\]

KL 项限制当前 policy 偏离冻结基座：

\[
\mathcal L_{\mathrm{KL}}
=\sum_iw_i\sum_j
D_{\mathrm{KL}}!left(
\pi_\theta(\cdot\mid x,z_{i,<j})
\|\pi_{\theta_0}(\cdot\mid x,z_{i,<j})
\right).
\]

Value 损失为

\[
\mathcal L_{\mathrm{value}}
=\left(u_{\psi,\phi}(x)-u^*\right)^2.
\]

总损失为

\[
\mathcal L
=\mathcal L_{\mathrm{policy}}
+\beta\mathcal L_{\mathrm{KL}}
+\lambda\mathcal L_{\mathrm{value}},
\]

其中 \(\beta\ge0\) 是 KL 系数，\(\lambda\ge0\) 是 value 系数。

一次 optimizer step 更新当前 session 的 LoRA、value head 和 AdamW 状态；基础模型冻结；`policy_version` 增加；同一证明实例随后使用新版本继续搜索。Value loss 也通过共享表示更新 LoRA，所以它是 joint policy/value TTT。

---

## 11. 失败时为什么有非零学习信号

当前日志需要分开四个量：

1. 真实终局 reward：完整根证明验收时为 1，非终局事件为 0。
2. Policy target：访问比例 \(w_i\)。
3. Value target：树 backup 解码得到的 \(u^*\)。
4. 当前预测：随机 head 或已更新 head 输出的 \(u_{\psi,\phi}(x)\)。

所以可以同时出现：

```text
reward = 0
value_target = 0.696
```

它表示没有终局成功，但树内平均 distance 产生了非零自举 target。

```text
当前 value 估计
  → 树选择、访问和 backup
  → 非终局 target
  → value loss
  → 更新后的 value
```

自举能让模型拟合当前搜索判断。Value 起点随机、树中又没有终局锚点时，自举可能把早期随机排序再次教回模型。

失败路径的证据强度依次是：完整 Lean 验收；通向已知终局或有独立剩余证明；真实非重复后继；树访问与 backup；未校准 policy/value 启发式。Lean 接受只保证局部转移正确，不保证最终闭合根目标。

---

## 12. 更新何时保留和继承

合格非终局事件会更新当前 session，并立即影响同一证明实例后续搜索。所有候选非法时，没有合法边和访问分布，通常就是 `0 learn`。

原始难题或中间课程变体最终失败时，题内更新确实影响过本次轨迹，但不会自动发布给其他证明实例。

完整成功后先独立 Lean replay，再执行成功轨迹 finalization。此前还可能有零次或多次 online updates。

只有显式 experience/release 才能把 adapter 与 value head 加载到新证明实例。新 session 重建 optimizer、RNG、buffer 和 online policy version。

因此“最终失败”“题内发生更新”“跨实例继承”是三个独立事实。

---

## 13. 我们是否需要先训练好 Value

### 13.1 结论

若希望 value 稳定承担“在多个合法分支之间分配搜索预算”的职责，需要一个经过训练和验证的 value 起点。

PUCT 会用 value 形成的 \(Q\) 选择分支。随机 value 系统性高估死路时，有限预算会反复进入这些分支，非终局自举还可能巩固偏差。

AlphaProof 用大量成功证明的剩余步数初始化 value，再经过大规模 RL。它没有要求单个原始难题从随机 head 开始，在几次更新内自己学会可靠估值。

### 13.2 “训练好”的最低标准

- 在与训练根题隔离的合法状态上，能把更接近终局的状态排在更远状态之前；
- 在同一父状态的合法竞争后继中，排序优于随机或固定中性值；
- 在完整搜索中，guidance 能重复改善证明成功或预算利用；
- 输出语义、\(\gamma\) 和搜索器的读取方式一致。

### 13.3 建议的训练顺序

1. 从当前 Lean/Mathlib 的成功证明提取状态、下一步 tactic 和真实剩余步数。
2. 按根题和派生祖先隔离训练集与验证集。
3. 先冻结 policy 表示，只训练 value head，形成 head-only warmup。
4. 在 held-out 状态上测配对排序和 AUROC。
5. 在至少两个合法、实质不同后继的证明实例上做 normal/neutral matched search。
6. Head-only 稳定有效后，再考虑 joint policy/value warmup。

12 个简单 sanity 状态适合检查接口，不能训练后继续当验证集；原始难题和派生状态也不能进入 value 训练。

### 13.4 Policy 的先决条件

Value 只能比较合法后继。Policy 持续生成非法、空输出或重复动作时，应先提高 Lean4 单步生成能力。

合理顺序是：

```text
policy 先能产生足够多的合法、不同后继
  → 独立成功轨迹训练并验证 value
  → value 稳定参与 PUCT
  → 再评估 joint TTT 的额外收益
```

Policy SFT 与 value 数据准备可以并行进行；端到端 value 实验必须选择真正存在竞争分支的证明实例。

---

## 14. 当前证据告诉了我们什么

12 状态 sanity 诊断中，7B 的配对排序由 `4/6` 变为 `3/6`，AUROC 由约 `0.778` 变为 `0.583`；9B 由 `3/6` 变为 `4/6`，AUROC 由约 `0.333` 变为 `0.639`。

9B 前后 thought prefix 全部不同，两个模型更新次数也不同。结果测到完整编码与 head 的联合变化，说明少量 joint updates 没有产生跨模型一致改善。

F1 normal/neutral 配对显示 value 会改变轨迹和节点数，但两臂都未完成证明，主要竞争后继又接近假设改名。它证明 guidance 影响搜索，没有证明数学收益。

Fresh A16 中 7B 与 9B 当时均为 `4/8`。P1 两者题内 `0 learn` 即完成，成功后 finalization；P2 中 7B 有 4 次 learn 并继续搜索，9B 为 `0 learn`，两者最终都未闭合。Learn 次数、证明成功和发布需要分别评价。

C6 恢复重访后产生合法动作和 4 次 learn，但 accepted 高度重复，repair 没有把真实 Lean 失败修成新合法后继，模型自主 query 也未形成有效调用。主要瓶颈同时包含候选多样性、查询能力和数学闭合，不能全归因于 value。

这些证据支持准备离线 value 训练和严格验证，也不支持把现有随机 head 当成可靠估值器。

---

## 15. 什么都证明不出来时怎样启动

**所有候选非法时**，没有合法树边，value 没有分支可评估，online TTT 也没有可靠 target。优先修 policy SFT、prompt、动作协议和 Lean 适配。

**有合法边但没有终局时**，可以测搜索深度、重复率、分支多样性和 value 对轨迹的影响。非终局自举适合有限诊断，不能只凭 loss 下降宣称学会证明。

**原始难题失败而中间课程变体可成功时**，使用根题族隔离、Lean 验证的变体产生成功轨迹，训练 policy 和 value，再回到冻结原始难题评测迁移。

AlphaProof 通过预训练、SFT、大规模问题池和 matchmaker 保持 proof/disproof 数据流。长期完全零成功的 success-only RL 没有新的可靠 learner 数据。

---

## 16. 教师课程与学生在线证明

教师或 matchmaker 可以依据训练侧失败摘要选择下一批中间课程变体。设失败摘要空间为 \(\mathcal D\)，课程候选集合为 \(\mathcal C\)：

\[
\operatorname{Teacher}:\mathcal D
\longrightarrow\Delta(\mathcal C).
\]

输入可包括合法动作率、Lean 错误、最大深度、分支多样性和成功率；输出是课程候选或难度分布。

候选要经过当前 Lean 验证、去重、根题族泄漏检查和来源记录。冻结原始难题评测保持题目、预算、seed 与接口固定。

当前 OpenCode 闭环由学生 policy 自主生成 query、tactic 和 repair。教师不参与这些在线动作。课程选择和单个证明实例内部的数学决策是两个层次。

---

## 17. 两套流程完整串联

### 17.1 AlphaProof

```text
大量预训练
  → Mathlib 成功轨迹训练 policy 和剩余步数 value
  → 大规模成功 proof/disproof RL
  → 得到训练好的 generalist policy/value
  → 创建证明实例
  → policy 生成 K 个 tactic
  → Lean 删除非法候选并建立后继
  → value 估计未搜索到底的叶子
  → backup 更新树统计
  → PUCT 选择下一条边
  → progressive sampling 在重访状态增加候选
  → 完整 proof/disproof 独立 Lean 验收
  → 成功轨迹进入 learner
  → 更新 policy/value
```

### 17.2 当前实现

```text
创建 fresh session
  → LoRA 与基座等价，value head 随机初始化
  → policy 生成 tactic
  → Lean 建立合法树
  → 随机起点 value 转成 distance 参与 PUCT/backup
  → 合格非终局事件联合更新 LoRA 和 value head
  → 同一 session 用新版本继续搜索
  → 完整成功后独立 Lean replay 和 finalization
  → 只有显式 release 才把 adapter/value 带到新实例
```

两者共享 Lean 状态树、policy 候选、value 引导、MCTS/PUCT 和终局验证骨架。关键差距是 value 训练起点、policy 的 Lean 能力、训练规模和非终局自举语义。

---

## 18. 核心问题的简明答案

### Value 是否负责打分、裁剪和选择分支？

Value 估计合法状态的长期前景，并通过 backup 影响 \(Q\)。PUCT 将 \(Q\)、policy 先验、访问次数和探索项组合，选择下一条访问边。Lean 删除非法动作，预算决定停止。Value 的主要职责是估值和预算引导。

### AlphaProof 是否很依赖离线训练好的 Value？

是。它先用大量 Mathlib 成功轨迹初始化剩余步数 value，再用大规模 RL 更新。TTRL 从训练好的 generalist 出发。

### 我们是否也需要先训练好 Value？

若希望 value 稳定承担搜索引导职责，需要。先做隔离成功轨迹的 head-only 训练、held-out 排序验证和真实竞争分支搜索验证，再考虑 joint warmup。当前随机 head 可做机制实验，不能预设具有 AlphaProof value 的判断力。

### 为什么失败时有非零 value target？

真实 reward 仍为 0。非零 target 来自树 backup，是自举估计；它可能继承随机 value 和早期搜索偏差。

### 什么都没证明出来时应该学习吗？

零合法动作时先修 policy 和接口。有合法树但无终局时可做有限自举诊断。稳定学习需要 SFT、value 初始化和中间课程变体共同建立持续的成功 proof/disproof 数据流。

---

## 19. 延伸阅读与实现依据

- [AlphaProof Nature 论文](https://www.nature.com/articles/s41586-025-09833-y)：proof network、MCTS/PUCT、SFT、main RL 与 TTRL。
- [02_Policy_Value_MCTS_PUCT的分工.md](02_Policy_Value_MCTS_PUCT的分工.md)：各组件的较短复习。
- [03_Value_head_随机初始化与AlphaProof差异.md](03_Value_head_随机初始化与AlphaProof差异.md)：随机 value 风险。
- [04_TTT更新_奖励_失败路径与继承.md](04_TTT更新_奖励_失败路径与继承.md)：当前更新与继承合同。
- [06_教师网络与动态课程.md](06_教师网络与动态课程.md)：动态课程与冻结评测。
- [search_objective.py](../../gpu_runtime/search_objective.py)：当前折扣回报、distance 和 visit target。
- [search_backend.py](../../gpu_runtime/search_backend.py)：当前 joint LoRA/value TTT。
- [real_backend.py](../../gpu_runtime/real_backend.py)：session、LoRA、value head 和 optimizer。
