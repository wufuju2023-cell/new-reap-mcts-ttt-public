下面只讨论 **CPU 侧**。我把 GPU 端完全抽象掉，假定 CPU 可以调用一个确定接口

$$
\mathsf{Net}(s)\to (\pi_\theta(\cdot\mid s),V_\phi(s))

$$

其中策略网络和价值网络如何计算、如何训练，暂时全部视为黑盒；CPU 的任务是维护 Lean 证明环境、定义搜索空间、验证动作、维护 AND–OR 搜索树，并通过 MCTS 把神经网络给出的局部信息转化为全局证明搜索。

严格地说，AlphaProof 的实际系统不是“普通 MCTS + 一个 Lean checker”这么简单，而是一个**带形式验证环境的单人序贯决策问题 + AND–OR 搜索 + PUCT + progressive sampling**。DeepMind/Nature 对其正式描述也明确采用这一结构。([Nature][1])

---

# 1. 先建立 CPU 侧的数学对象

整个 CPU 系统最重要的是把 Lean 证明过程形式化成一个状态转换系统。

定义一个证明问题为

$$
\mathcal P=(\Gamma_0,\Delta_0)

$$

其中：

* \(\Gamma_0\) 是环境中已经可用的全局声明、定理、定义、类型类实例等；
* \(\Delta_0\) 是需要证明的目标集合。

更抽象一点，可以把 Lean 的证明状态写成

$$
s=(E,C,G)

$$

其中

$$
E=\text{Environment}

$$

表示当前 Lean 环境，

$$
C=\text{local context}

$$

表示局部变量、假设及其类型，

$$
G=(g_1,\ldots,g_m)

$$

表示当前尚未解决的 goals。

在实际 Lean 中，一个 tactic state 本质上是“一组局部上下文 + 待证明目标”；tactic 对 proof state 进行变换，并最终生成 proof term，而 proof term 再由 kernel 做类型检查。([Lean Language][2])

所以：

$$
\boxed{\text{CPU 搜索的节点不是“文本”，而是 Lean 的逻辑状态 }s}

$$

这是整个系统最关键的一点。

---

# 2. Lean 为什么天然适合作为 RL environment

对于普通语言模型来说，可以把生成 token 看成状态转移：

$$
x_t\xrightarrow{a_t}x_{t+1}.

$$

但这种状态没有严格语义保证。

Lean 不一样。

给定当前 proof state \(s_t\)，如果 CPU 选择一个 tactic \(a_t\)，Lean environment 执行：

$$
s_{t+1}
=
T(s_t,a_t).

$$

但是这个 \(T\) 不是普通函数，因为 tactic 可能失败。

所以更准确地写成一个偏函数：

$$
T:S\times A\rightharpoonup S.

$$

即

$$
T(s,a)=
\begin{cases}
s' & \text{if }a\text{ is a valid tactic in }s,\\
\bot & \text{otherwise}.
\end{cases}

$$

这里的 \(\bot\) 就是：

> tactic 在当前 Lean 状态下无法执行。

例如：

```lean
example (a b c : Nat) (h1 : a < b) (h2 : b < c) : a < c := by
  exact Nat.lt_trans h1 h2
```

在初始状态

$$
s_0=
\{a,b,c:\mathbb N,\;h_1:a<b,\;h_2:b<c\}
\vdash a<c

$$

执行

```lean
exact Nat.lt_trans h1 h2
```

后变成

$$
G=\varnothing

$$

因此到达终止状态：

$$
s_{\mathrm{terminal}}.

$$

而若执行：

```lean
exact h1
```

Lean 会直接拒绝：

$$
T(s_0,\texttt{exact h1})=\bot.

$$

这就是 AlphaProof 环境极其重要的性质：

$$
\boxed{\text{reward/verifier 不需要“猜”一个中间步骤是否正确}}

$$

因为 Lean 本身就是 evaluator/verifier。Nature 对 AlphaProof 环境的定义也是：动作是文本形式的 Lean tactic，环境尝试执行它，并根据结果进入新的 proof state；最终证明必须经过 Lean kernel 验证。([Nature][1])

---

# 3. Lean 内部其实有三个层次

CPU 侧最好把 Lean 看成三个不同层次，而不要把它们混为一谈。

## 3.1 Syntax

例如：

```lean
exact Nat.lt_trans h1 h2
```

这是字符串 / syntax tree。

记为

$$
a\in A_{\text{syntax}}.

$$

---

## 3.2 Elaboration

Lean 需要将这个 tactic/text 解释为具体项。

大致是

$$
\text{Syntax}
\longrightarrow
\text{Elaborated term}.

$$

例如：

```lean
Nat.lt_trans h1 h2
```

需要确定：

* `Nat.lt_trans` 对应哪个常量；
* `h1` 和 `h2` 的类型；
* implicit arguments；
* universe；
* metavariables；
* coercions；
* typeclass instances。

Lean 的 elaborator 最终把用户面对的语法转换到更加简单的 core type theory。([Lean Language][3])

---

## 3.3 Kernel checking

最后 kernel 检查 proof term：

$$
\Gamma\vdash t:P.

$$

如果成立，证明才真正成立。

所以从系统观点：

$$
\boxed{
\text{LLM proposes syntax}
\rightarrow
\text{Lean elaborates}
\rightarrow
\text{kernel checks proof term}
}

$$

这也是为什么 AlphaProof 的“奖励”可以特别干净：关键最终事件是**形式证明成功**，不是语言模型自己的评分。Lean 官方文档明确强调，每个 tactic 最终构造 proof term，而 proof term 要经过 kernel 检查。([Lean Language][2])

---

# 4. CPU 侧真正的 action 是什么？

这里有一个非常容易产生误解的地方：

$$
a_t\neq\text{token}.

$$

在 AlphaProof 这种系统里，搜索树的一条边对应的是一个 **Lean tactic/action**，它通常以文本字符串表示。Nature 明确把动作定义成 Lean tactic text string。([Nature][1])

因此：

$$
A(s)=\{a:
a\text{ 是可以尝试施加到 }s\text{ 的 tactic}\}.

$$

理论上：

$$
|A(s)|=\infty

$$

或者至少极其巨大。

例如：

```lean
intro h
exact ...
apply ...
rw [...]
simp
constructor
cases ...
induction ...
omega
linarith
nlinarith
aesop
ring
norm_num
...
```

而且 lemma 名字可以是 Mathlib 中几乎无穷多种组合。

因此不能像 Go 那样拥有一个固定 action set：

$$
A=\{1,\ldots,361\}.

$$

这就是 AlphaProof CPU 搜索和标准 AlphaZero 之间的重要差别。

---

# 5. 为什么不能简单做一个普通 MCTS？

假设当前状态：

$$
s

$$

如果 action 数量极其巨大，那么完整枚举：

$$
\forall a\in A(s)

$$

是不可能的。

因此 CPU 必须使用 GPU 网络提供的 proposal distribution

$$
\pi_\theta(a\mid s)

$$

把无限/巨大 action space 压缩成一个有限候选集：

$$
\{a_1,\ldots,a_K\}.

$$

于是 CPU 实际做：

$$
a_1,\ldots,a_K
\sim
\pi_\theta(\cdot\mid s).

$$

然后逐个交给 Lean：

$$
s'
=
T(s,a_i).

$$

这就变成：

$$
\boxed{
\text{LLM负责“提出可能有用的 tactic”，Lean负责“决定它是否真的合法”}
}

$$

---

# 6. CPU 中的 Lean environment interface

工程上，我建议把 CPU 端抽象成下面这个接口：

$$
\mathsf{Step}:
(S,A)\to
\{\textsf{Invalid}\}
\cup
\{\textsf{Valid}(s',m)\}

$$

其中：

* \(s'\)：新的 Lean proof state；
* \(m\)：额外 metadata，例如执行时间、产生几个 goals、proof term 信息等。

还需要：

$$
\mathsf{Solved}(s)\in\{0,1\}.

$$

定义：

$$
\mathsf{Solved}(s)=1
\iff
G(s)=\varnothing.

$$

以及可能的：

$$
\mathsf{Failed}(s)

$$

用于 timeout / resource exhaustion / irrecoverable failure。

---

# 7. 一个非常重要的问题：为什么多 goal 导致 AND node？

这是 AlphaProof 与普通 AlphaZero 最大的结构性区别之一。

考虑：

```lean
example : P ∧ Q := by
  constructor
```

执行 `constructor` 后：

$$
s_0
\rightarrow
\{P,Q\}.

$$

即一个目标变成两个子目标：

$$
g_1=P,\qquad g_2=Q.

$$

逻辑上：

$$
P\land Q

$$

成立，当且仅当

$$
P\text{ 成立}\quad\land\quad Q\text{ 成立}.

$$

因此这不是普通 OR 分支，而是：

$$
s_{\mathrm{AND}}
=
(g_1,g_2).

$$

整个证明成功的条件为：

$$
\operatorname{Solved}(s_{\mathrm{AND}})
=
\operatorname{Solved}(g_1)
\land
\operatorname{Solved}(g_2).

$$

这就是 AND node。

Nature/AlphaProof 的正式描述明确指出，多 goal tactic 会产生独立 subgoals，搜索树因此需要 AND–OR 结构；所有 subgoals 都必须解决。([t.co][4])

---

# 8. AND node 与 OR node 的区别

在 CPU 搜索树里，可以理解为：

### OR node

当前证明状态：

$$
s

$$

可以选择多个 tactic：

$$
a_1,a_2,\ldots,a_n.

$$

只要存在一个成功：

$$
\exists i,\quad
T(s,a_i)\text{ 可导向证明}.

$$

因此：

$$
V(s)
=
\max_i V(s,a_i)

$$

从逻辑意义说，是：

$$
OR.

$$

---

### AND node

若某个 tactic 将问题拆成：

$$
g_1,\ldots,g_m,

$$

则必须：

$$
\forall i,\quad g_i\text{ solved}.

$$

因此：

$$
V(s_{\mathrm{AND}})
=
\min_iV(g_i)

$$

这就是 AlphaProof 里很关键的：

$$
\boxed{\text{AND aggregation}=\min}

$$

原因不是某种经验技巧，而是其 reward / return 定义本身就是按**最难的证明分支**决定。Nature 明确给出：多 subgoal 情况下 return 使用这些 subgoal returns 的 minimum，而不是 sum。([Nature][1])

---

# 9. Reward 到底是什么？

这点尤其重要。

AlphaProof 并不是简单：

$$
r=
\begin{cases}
+1 & \text{证明成功}\\
-1 & \text{失败}
\end{cases}

$$

它采用的是一种非常特殊但很自然的 shaping：

$$
\boxed{r_t=-1}

$$

对于每一次 tactic application。

因此一条长度为 \(L\) 的完整证明，其 return 是

$$
G=-L.

$$

也就是说：

$$
\boxed{
\text{证明越短，return 越大}
}

$$

例如：

证明 A：

$$
L_A=20

$$

则

$$
G_A=-20.

$$

证明 B：

$$
L_B=40

$$

则

$$
G_B=-40.

$$

因此：

$$
-20>-40

$$

所以系统更偏好 A。

Nature 明确描述 AlphaProof 的奖励为每施加一个 tactic 得到 \(-1\)，并将 return 定义为后续 tactic rewards 的总和。([Nature][1])

---

# 10. 为什么用负步数而不是 terminal +1？

如果定义：

$$
r_t=
\begin{cases}
+1 & \text{成功}\\
0 & \text{其他}
\end{cases}

$$

那么：

20 步成功和 2000 步成功都得到：

$$
G=1.

$$

这对 theorem proving 不理想，因为：

$$
\text{proof length}

$$

本身是非常重要的搜索成本。

而：

$$
r_t=-1

$$

导致：

$$
G_t=-\text{remaining steps}.

$$

所以 value network 的语义可以直接解释为：

$$
V(s)\approx-\text{expected remaining proof steps}.

$$

这也是 AlphaProof 的 value 定义的重要直觉。Nature 给出的定义明确说，\(V\) 的语义对应于解决当前目标还剩多少步的负数。([PubMed Central (PMC)][5])

---

# 11. 一个极其漂亮的性质

假设从状态 \(s\) 出发，有两个证明：

$$
s
\xrightarrow{a}
s_1
\xrightarrow{b}
s_2
\xrightarrow{c}
s_T

$$

一共 3 步。

那么：

$$
G(s)=-3.

$$

而如果：

$$
s
\xrightarrow{d}
s_3
\xrightarrow{e}
s_T

$$

只有 2 步：

$$
G(s)=-2.

$$

所以：

$$
V(s,d)>V(s,a).

$$

因此价值网络其实是在学习一个非常接近：

$$
\boxed{
V(s)=-d^*(s)
}

$$

的函数，其中

$$
d^*(s)
=
\min_{\pi}
\{\text{policy }\pi\text{ 从 }s\text{ 到 proof 的步数}\}.

$$

严格地说，训练中的 value 是 expected return，不一定等于最短证明距离；但搜索与训练不断逼近这个 quantity。

---

# 12. 这时候 MCTS 才有数学意义

我们现在有：

$$
\mathcal M=
(S,A,T,r)

$$

一个 deterministic 单人 sequential decision process。

因为：

$$
T(s,a)

$$

基本是确定性的。

这和 Go / Chess 有一个重要区别：

Go 中：

$$
s_t,a_t\rightarrow s_{t+1}

$$

之后轮到另一个 player。

而 theorem proving 是：

$$
\boxed{\text{single-player deterministic planning}}

$$

不存在对手。

所以搜索不是 minimax game，而是：

$$
\text{proof planning}.

$$

---

# 13. CPU 树节点应该怎么定义？

最简单的定义：

$$
n=(s,N,W,\mathcal E)

$$

其中：

* \(s\)：Lean state；
* \(N\)：访问次数；
* \(\mathcal E\)：当前已经发现的合法 action edges；
* \(W\)：累计 value statistics。

每一条边：

$$
e=(s,a,s')

$$

附带：

$$
N(s,a)

$$

以及 aggregated value：

$$
V(s,a).

$$

AlphaProof 实现里确实对每个 state-action pair 维护 visit count 与 aggregated search value。([PubMed Central (PMC)][5])

---

# 14. MCTS 的四个阶段

每一次 simulation 都做：

$$
\boxed{
Selection
\rightarrow
Expansion
\rightarrow
Evaluation
\rightarrow
Backpropagation
}

$$

其中 AlphaProof 的描述使用 selection / expansion / backpropagation，leaf value 由 proof network 提供。([PubMed Central (PMC)][5])

CPU 端真正应该实现的是：

---

## 14.1 Selection

从 root：

$$
s_0

$$

不断根据某个 UCB/PUCT criterion 选择 action：

$$
a^*
=
\arg\max_a U(s,a).

$$

AlphaProof 使用 PUCT 类公式。其核心结构为：

$$
U(s,a)
=
Q(s,a)
+
c(s)
\frac{\pi(a|s)^{1/\tau}\sqrt{N(s)}}{1+N(s,a)}

$$

其中具体记号在论文中有定义上的变体，但结构就是：

$$
\boxed{
\text{exploitation}+\text{exploration}
}

$$

即：

$$
Q
+
U.

$$

([PubMed Central (PMC)][5])

---

# 15. PUCT 每一项究竟是什么意思？

## 15.1 \(N(s,a)\)

表示：

$$
N(s,a)=\text{过去多少 simulation 选择过 }a.

$$

如果

$$
N(s,a)=0

$$

说明还没有真正搜索过。

---

## 15.2 \(Q(s,a)\)

表示：

$$
Q(s,a)

$$

是当前搜索统计中 action \(a\) 的 exploit value。

AlphaProof 中不是直接把 reward average 简单写成标准 \([0,1]\) Q，而是由其特殊的 value representation 转换而来。论文给出的形式为

$$
Q(s,a)=\gamma^{-V(s,a)-1}

$$

其中 \(V(s,a)\) 是 aggregated search value。([PubMed Central (PMC)][5])

这个设计很值得理解。

---

# 16. 为什么把负步数 value 转成 \(Q\)？

因为：

$$
V(s,a)

$$

大致是：

$$
-\text{remaining steps}.

$$

例如：

$$
V=-3

$$

意味着大约还需要 3 步。

如果：

$$
V=-20

$$

说明离成功更远。

所以我们希望更大的 \(V\) 映射成更好的 \(Q\)。

而论文中的：

$$
Q(s,a)=\gamma^{-V(s,a)-1}

$$

随着 \(V\) 增大而增大。

因此：

$$
V=-3>-20

$$

会对应更有利的 \(Q\)。

这是因为 \(V\) 的量纲本质上是：

$$
\text{negative step count}

$$

而 \(Q\) 被重新参数化成更加适合 PUCT selection 的尺度。([PubMed Central (PMC)][5])

---

# 17. Exploration term 的物理含义

PUCT：

$$
Q(s,a)
+
c(s)
\frac{P(s,a)\sqrt{N(s)}}{1+N(s,a)}

$$

其中

$$
P(s,a)=\pi_\theta(a|s)^{1/\tau}.

$$

如果：

$$
N(s,a)=0

$$

那么 exploration term 很大。

因此：

$$
N(s,a)\uparrow
\Rightarrow
U(s,a)\downarrow.

$$

所以系统不会永远只搜索一个 action。

---

# 18. temperature \(\tau\)

策略网络产生：

$$
\pi_\theta(a|s).

$$

再修改：

$$
P(a|s)
\propto
\pi_\theta(a|s)^{1/\tau}.

$$

当：

$$
\tau<1

$$

分布更尖锐：

$$
\text{high-probability actions得到更多优先级}.

$$

当：

$$
\tau>1

$$

分布更平坦：

$$
\text{鼓励探索更多 action}.

$$

AlphaProof 的 PUCT 中确实对 policy prior 使用了 temperature 修正。([PubMed Central (PMC)][5])

---

# 19. 但是“完整 action space”根本不存在

这是 CPU 实现最难的地方之一。

假设：

$$
\pi_\theta(\cdot|s)

$$

是一个 autoregressive LLM。

理论上：

$$
\pi_\theta(a|s)
=
\prod_{t=1}^{|a|}
\pi_\theta(a_t|s,a_{<t}).

$$

但是 tactic 是字符串：

```text
apply Nat.le_trans
```

或者：

```text
rw [← Finset.sum_range_succ]
```

所以完整 action space 是所有合法 Lean tactic strings。

这几乎是无限的。

因此 CPU 只能做：

$$
\{a_1,\ldots,a_K\}
\sim
\pi_\theta(\cdot|s).

$$

这就是所谓：

$$
\boxed{\text{sampled action expansion}}

$$

AlphaProof 论文明确指出，它针对开放式 tactic space 进行 action sampling。([Nature][1])

---

# 20. Expansion 到底做什么？

假设 selection 进入叶子：

$$
s_L.

$$

CPU 请求：

$$
\mathsf{Net}(s_L)
=
(\pi_\theta,V_\phi).

$$

GPU 给出：

$$
a_1,\ldots,a_K.

$$

CPU 对每一个：

$$
a_i

$$

运行：

$$
T(s_L,a_i).

$$

结果分三种。

### 第一种：invalid

$$
T(s_L,a_i)=\bot.

$$

直接丢弃。

### 第二种：valid，而且得到新的 state

$$
T(s_L,a_i)=s_i.

$$

加入搜索树。

### 第三种：solved

$$
\mathsf{Solved}(s_i)=1.

$$

立即得到完整 proof candidate。

---

# 21. 为什么必须在 CPU 执行 Lean，而不是让网络自己说“我证明了”？

因为：

$$
\pi_\theta

$$

只是一个统计模型。

它输出：

$$
a\sim\pi_\theta

$$

并不能保证：

$$
T(s,a)\neq\bot.

$$

更不能保证最终：

$$
\Gamma\vdash P.

$$

因此必须：

$$
\boxed{
\text{network proposal}
\neq
\text{logical validity}
}

$$

真正决定 proof validity 的是 Lean elaborator + kernel。

Lean 官方文档明确说明 kernel 对 elaborated proof term 做最终 type checking。([Lean Language][6])

---

# 22. 一个很重要的优化：同态状态合并

假设网络产生：

$$
a_1,\quad a_2.

$$

结果却是：

$$
T(s,a_1)=s'

$$

和

$$
T(s,a_2)=s'.

$$

那么从搜索角度：

$$
a_1,a_2

$$

没有必要产生两个完全独立的 state nodes。

可以合并。

AlphaProof 的环境会把导致相同 Lean state 的 tactics 合并，并在若干等价条件下选择成本更低的 tactic。Nature 的 Methods 明确描述了这一点，包括对 hypothesis reorder / renaming 等规范化后状态的合并，以及按 tactic string length 和 execution time 的线性成本进行选择。([PubMed Central (PMC)][5])

这其实意味着严格来说它更接近：

$$
\boxed{\text{tree search over a quotient state graph}}

$$

而不是纯粹数学意义的树。

即把：

$$
s_1\sim s_2

$$

定义为“二者逻辑上/规范化后等价”。

然后搜索：

$$
S/\sim.

$$

这是一个非常关键的工程优化。

---

# 23. 为什么要加入 execution cost？

两个 tactic：

$$
a_1,a_2

$$

可能得到相同 state：

$$
T(s,a_1)=T(s,a_2)=s'.

$$

但：

$$
\operatorname{cost}(a_1)
<
\operatorname{cost}(a_2).

$$

例如：

```lean
exact some_lemma
```

可能比一个长得多、执行更慢的自动化 tactic 更便宜。

因此可以定义：

$$
C(a)
=
\lambda_1\cdot |a|
+
\lambda_2\cdot t_{\mathrm{exec}}(a).

$$

然后保留：

$$
a^*
=
\arg\min_{a:T(s,a)=s'}C(a).

$$

AlphaProof 的实际方法正是用与字符串长度、执行时间线性相关的 cost 来处理这类 duplicate-state tactics。([PubMed Central (PMC)][5])

---

# 24. Leaf evaluation

假设：

$$
s_L

$$

没有成功，也没有明显终止。

CPU 请求 GPU：

$$
V_\phi(s_L).

$$

得到：

$$
\hat V_L.

$$

它可以理解为：

$$
\hat V_L
\approx
\mathbb E[G_t\mid s_L].

$$

由于：

$$
G_t=-\text{remaining steps},

$$

因此：

$$
\hat V_L\approx
-\mathbb E[\text{remaining proof steps}\mid s_L].

$$

例如：

$$
V_\phi(s_L)=-2.7

$$

可以理解成：

> 网络预测从这里完成证明平均还需要大约 2.7 个 tactic。

这不是严格的 shortest-path distance，只是 learned expected return。

---

# 25. Backpropagation

现在我们有一条 path：

$$
s_0
\xrightarrow{a_0}
s_1
\xrightarrow{a_1}
s_2
\rightarrow\cdots\rightarrow s_L.

$$

叶子的估计：

$$
V_L.

$$

然后沿路径反向更新：

$$
(s_{L-1},a_{L-1}),
\dots,
(s_0,a_0).

$$

最基本统计：

$$
N(s,a)\leftarrow N(s,a)+1

$$

以及 value aggregate：

$$
V_{\text{agg}}(s,a)
\leftarrow
\operatorname{Aggregate}
\left(
V_{\text{agg}}(s,a),V_L
\right).

$$

具体 AlphaProof 使用其定义下的 aggregated search value，并在 AND node 上进行特殊聚合。([PubMed Central (PMC)][5])

---

# 26. 为什么 AND node 必须用 min？

假设：

$$
P\land Q.

$$

假设：

$$
V(P)=-2,
\qquad
V(Q)=-10.

$$

整体证明至少需要解决最难的：

$$
Q.

$$

所以：

$$
V(P\land Q)
=
\min(-2,-10)
=
-10.

$$

这完全符合：

$$
G=-\text{longest unresolved proof branch}.

$$

因此在 AND node：

$$
\boxed{
V_{\mathrm{AND}}
=
\min_iV_i
}

$$

而不是：

$$
\sum_iV_i.

$$

Nature 明确指出 AlphaProof 在多 subgoal 情况下使用 minimum，语义对应“最长证明分支”。([Nature][1])

---

# 27. 这比普通 sequence MCTS 更复杂

普通 sequence generation 可以写：

$$
s_0\to s_1\to s_2\to\cdots\to s_T.

$$

但 theorem proving：

$$
s_0
\xrightarrow{a}
\{g_1,g_2,g_3\}.

$$

然后：

$$
g_1
\rightarrow \cdots

$$

同时：

$$
g_2
\rightarrow \cdots

$$

以及：

$$
g_3
\rightarrow \cdots.

$$

因此搜索结构实际上是：

$$
\boxed{
OR\text{ nodes}
+
AND\text{ nodes}
}

$$

这才是完整的 AlphaProof CPU-side tree。

---

# 28. Progressive Sampling 为什么需要？

普通 MCTS 有一个问题：

如果在 root：

$$
\pi(a_1|s)=0.7

$$

而：

$$
\pi(a_2|s)=0.001

$$

那么很可能 search 永远只看：

$$
a_1.

$$

可是：

$$
a_2

$$

可能恰恰是证明问题需要的关键 lemma。

因此不能只固定采样 K 个动作然后永远不扩充。

AlphaProof 使用：

$$
\boxed{\text{progressive sampling}}

$$

根据某个节点被访问的次数动态增加 candidate tactics。

论文描述的原则是，当：

$$
n(s)\le C N(s)^\alpha

$$

时，再从 policy 中采样额外的 \(K\) 个 tactics。([PubMed Central (PMC)][5])

其中：

* \(N(s)\)：该节点总访问次数；
* \(n(s)\)：已经被采样出来的不同 tactic 数；
* \(C,\alpha\)：控制扩展速度的参数。

---

# 29. progressive sampling 的数学意义

如果没有 progressive sampling：

$$
|\mathcal A_s|=K

$$

永远固定。

那么即使：

$$
N(s)\to\infty

$$

你仍然只在：

$$
K

$$

个候选动作里搜索。

因此：

$$
P(a\text{ discovered})=0

$$

对于从未采到的 action。

这意味着模型一旦犯了先验错误，搜索就无法纠正。

progressive sampling 改成：

$$
|\mathcal A_s|
\rightarrow\infty
\quad
\text{as }N(s)\rightarrow\infty.

$$

于是随着计算预算增加：

$$
\boxed{
\text{search breadth gradually increases}
}

$$

这非常接近传统 best-first search 中“把更多计算给真正有希望的 frontier”的思想。

---

# 30. 为什么这里需要把 exploitation/exploration 重新设计？

在普通 AlphaZero 中：

$$
Q\in[0,1].

$$

越大越好。

但这里：

$$
V\le 0

$$

而且：

$$
V\approx-\text{steps}.

$$

因此：

$$
V=-2

$$

比：

$$
V=-20

$$

更好。

Progressive sampling 可以通过修改 selection criterion 来推动“尚未充分采样的高潜力区域”。

Nature 给出的 AlphaProof 特殊设计之一，就是在 progressive sampling 过程中使用相应的 \(1-Q\) 形式来调节选择机制。([PubMed Central (PMC)][5])

---

# 31. CPU 最终到底在优化什么？

从严格数学角度，CPU search 近似解决：

$$
\min_{\pi}
\mathbb E_\pi[L]

$$

subject to

$$
T(s_0,a_0)\to s_1
\to\cdots\to s_T,

$$

并要求：

$$
G(s_T)=\varnothing.

$$

其中：

$$
L=T

$$

是 proof length。

所以 theorem proving 可以写成：

$$
\boxed{
\text{find a valid path from }s_0\text{ to a terminal solved state}
}

$$

并且目标是：

$$
\boxed{
\min \text{ path length}
}

$$

同时受到 action branching factor 极大的限制。

---

# 32. 因此 MCTS 实际上是在近似 shortest-proof search

定义：

$$
d^*(s)
=
\min\{
L:
\exists a_1,\dots,a_L,\;
s\xrightarrow{a_1}\cdots\xrightarrow{a_L}s_T,\;
\mathsf{Solved}(s_T)=1
\}.

$$

则：

$$
V^*(s)=-d^*(s).

$$

如果 state 会产生 AND subgoals，则递归定义：

### OR state

$$
d^*(s)
=
1+
\min_{a}
d^*(T(s,a)).

$$

### AND state

若：

$$
s=(g_1,\ldots,g_k)

$$

则：

$$
d^*(s)
=
\max_i d^*(g_i)

$$

在 AlphaProof 的 return 语义下尤其对应最难 branch 的长度。

于是：

$$
V^*(s)
=
-d^*(s).

$$

这给出了整个 CPU search 一个非常干净的数学解释。

---

# 33. 这也解释为什么 AND-node 是 min，而 OR-node 是 max

因为：

$$
V^*(s)=-d^*(s).

$$

对于 OR：

$$
d^*(s)
=
1+\min_a d^*(s_a).

$$

所以：

$$
V^*(s)
=
-1+
\max_a V^*(s_a).

$$

因此 OR 本质上是：

$$
\max.

$$

对于 AND：

$$
d^*(s)=\max_i d^*(g_i)

$$

所以：

$$
V^*(s)
=
-\max_i d^*(g_i)
=
\min_i V^*(g_i).

$$

所以：

$$
\boxed{
OR\rightarrow \max
}

$$

$$
\boxed{
AND\rightarrow \min
}

$$

不是拍脑袋的 MCTS trick，而是由 reward 定义和逻辑合取直接推出的。

---

# 34. 这时 CPU 侧的完整数据流

可以把整个 CPU 系统画成：

$$
\boxed{
\text{Lean State}
}

$$

↓

$$
\text{PUCT Selection}

$$

↓

$$
(s,a)

$$

↓

$$
\text{Lean tactic execution}

$$

↓

$$
\begin{cases}
\bot & \text{invalid}\\
s' & \text{valid}\\
s_{\mathrm{terminal}} & \text{solved}
\end{cases}

$$

↓

若叶子：

$$
s_L

$$

↓

调用抽象 GPU：

$$
(\pi_\theta,V_\phi)

$$

↓

候选：

$$
a_1,\ldots,a_K

$$

↓

CPU Lean verification：

$$
T(s_L,a_i)

$$

↓

建立新的 OR / AND edges

↓

backprop：

$$
N,\;V

$$

↓

再次 PUCT

↓

直到：

$$
\boxed{\text{proof found}}

$$

或者：

$$
\boxed{\text{simulation budget exhausted}}.

$$

AlphaProof 的实际推理过程也是一个 search attempt 持续保留同一搜索树，而不是每一步都提交一个动作后重启整个搜索；这与单人、确定性 theorem-proving 环境有关。([PubMed Central (PMC)][5])

---

# 35. 为什么 AlphaProof 不需要像棋类那样“执行一步，然后重启树”？

这是一个非常深的区别。

Go：

$$
s_0
\to a_0
\to s_1.

$$

一旦落子：

$$
a_0

$$

实际执行了。

然后 opponent 又行动。

所以根节点发生改变。

但 theorem proving：

$$
s_0

$$

中的多个 candidate tactics 都只是：

$$
\text{hypothetical branches}.

$$

Lean 是 deterministic 的：

$$
T(s,a)

$$

可以重复计算。

因此：

$$
\boxed{
\text{整个证明过程可以共享一棵 search tree}
}

$$

搜索器无需像棋类一样每做出一个最终动作，就把树根移动到该动作之后。

Nature 对 AlphaProof 的描述明确指出，一次 proof attempt 内可以保留并扩展同一棵 search tree，并利用全局计算预算。([PubMed Central (PMC)][5])

---

# 36. CPU 的核心不是“计算神经网络”，而是管理世界状态

因此整个系统可以非常干净地切成：

## CPU

$$
\boxed{
\begin{aligned}
&\text{Lean state}\\
&\text{Tactic execution}\\
&\text{Validity checking}\\
&\text{State canonicalization}\\
&\text{AND/OR tree}\\
&\text{PUCT}\\
&\text{MCTS statistics}\\
&\text{Search scheduling}\\
&\text{Replay / trajectory recording}
\end{aligned}}

$$

## GPU

$$
\boxed{
\begin{aligned}
&s\mapsto\pi_\theta(\cdot|s)\\
&s\mapsto V_\phi(s)\\
&\theta,\phi\text{ update}
\end{aligned}}

$$

这个边界非常重要。

因为：

$$
\boxed{\text{CPU 是 symbolic world model + search controller}}

$$

而：

$$
\boxed{\text{GPU 是 learned heuristic}}

$$

---

# 37. 一个好的 CPU API 应该长什么样？

如果我们真的要实现一个“AlphaProof-like CPU engine”，我会定义以下抽象。

```text
LeanEnv

  initial(problem) -> State

  apply(state, tactic)
      -> Invalid
      | Valid(State, Metadata)

  is_solved(state) -> bool

  split_goals(state)
      -> [Subgoal]

  canonicalize(state)
      -> CanonicalState

  snapshot(state)
      -> Snapshot

  restore(snapshot)
      -> State
```

然后 network wrapper：

```text
ProofNetworkCPUInterface

  infer(state)
      -> PolicyPrior
       + Value
```

其中：

```text
PolicyPrior
    sample(K)
    probability(tactic)
```

然后 MCTS：

```text
MCTS

  search(root_state, budget)
      -> Proof
       | Failure
```

---

# 38. 最核心的数据结构

一个 OR node：

```text
ORNode:
    lean_state
    visits
    value
    children[action] -> Edge
    sampled_actions
```

一个 edge：

```text
Edge:
    tactic
    child_state
    prior
    visits
    aggregate_value
    execution_cost
```

一个 AND node：

```text
ANDNode:
    subgoals[1..k]
    aggregate_value
    solved_mask
```

于是：

$$
\text{ProofTree}

$$

实际上是：

$$
\text{OR nodes}
\leftrightarrow
\text{AND nodes}.

$$

---

# 39. 一个完整的小型例子

假设根状态：

$$
s_0\vdash P\land Q.

$$

policy 给：

$$
\pi(\texttt{constructor}|s_0)=0.8

$$

CPU 执行：

```lean
constructor
```

得到：

$$
s_1=
\operatorname{AND}(P,Q).

$$

搜索树：

```text
          s0  [OR]
             |
        constructor
             |
          s1 [AND]
          /      \
         P        Q
```

假设：

$$
V(P)=-2

$$

$$
V(Q)=-8.

$$

那么：

$$
V(s_1)=\min(-2,-8)=-8.

$$

于是根节点看到：

$$
\texttt{constructor}

$$

对应大约：

$$
V(s_0,\texttt{constructor})
\approx -9

$$

因为还需要执行 `constructor` 本身，然后解决最长分支。

如果另一个 tactic：

$$
a_2

$$

最终需要 15 步，那么：

$$
V(s_0,a_2)\approx -15.

$$

所以：

$$
-9>-15,

$$

search 更偏好：

$$
\texttt{constructor}.

$$

这就是：

$$
\boxed{\text{formal logic structure}+\text{RL return}+\text{MCTS}}

$$

三者真正结合的地方。

---

# 40. 一个容易忽略的事实：Lean state 不是“字符串状态”

网络看到的可能是 pretty-printed state：

```text
a b c : Nat
h1 : a < b
h2 : b < c
⊢ a < c
```

但 CPU 内部不能拿这个字符串当作真正的环境状态。

真正的状态是：

$$
s=(E,C,G,\text{metacontext},\ldots).

$$

字符串只是：

$$
\operatorname{Obs}(s)

$$

即 state observation。

于是可以更严格地写：

$$
\boxed{
s
\xrightarrow{\operatorname{render}}
x
\xrightarrow{\text{GPU}}
(\pi,V)
}

$$

而不是：

$$
\text{string}\xrightarrow{} \text{Lean}.

$$

CPU 保存的必须是真实的 Lean state / 可恢复 snapshot。

AlphaProof 环境特别强调 save/restore/unique identification of Lean tactic states，以便并行 tree search 从任意已访问状态继续。([t.co][4])

---

# 41. 并行化为什么天然发生在 CPU？

假设有：

$$
10^4

$$

个 search simulations。

不同 branch 的：

$$
T(s_i,a_i)

$$

之间大多彼此独立。

因此可以：

$$
\{(s_i,a_i)\}_{i=1}^N

$$

并行执行。

AlphaProof 的环境明确设计成能够：

* 多线程并行执行多个 Lean proof states；
* 保存/恢复 state；
* 批量调用 proof network。([t.co][4])

因此 CPU 层其实是一个：

$$
\boxed{\text{distributed / parallel symbolic search scheduler}}

$$

而不是一个简单的 Python recursive DFS。

---

# 42. CPU 与 GPU 之间最重要的接口不是 tensor，而是“语义接口”

这是架构设计里非常关键的一点。

GPU 不需要知道：

* Lean metavariable 的内部表示；
* kernel declaration environment；
* tactic execution；
* proof snapshots；
* AND-node；
* state deduplication。

它只需要知道：

$$
x=\operatorname{encode}(s)

$$

然后返回：

$$
\pi(a|s)

$$

以及：

$$
V(s).

$$

所以接口可以抽象成：

$$
\boxed{
f_\theta:
\mathcal S
\to
\mathcal P(\mathcal A)
\times
\mathbb R
}

$$

CPU 则负责把：

$$
\mathcal S

$$

真正实现出来。

---

# 43. 从严格数学角度，CPU 其实维护两个图

第一个是：

$$
\mathcal G_{\mathrm{Lean}}
=
(\mathcal S,\mathcal E)

$$

其中：

$$
(s,a,s')\in\mathcal E
\iff
T(s,a)=s'.

$$

这是**真实证明状态图**。

第二个是：

$$
\mathcal G_{\mathrm{search}}
\subseteq
\mathcal G_{\mathrm{Lean}}

$$

这是目前 MCTS 探索过的子图。

所以：

$$
\boxed{
\text{Lean defines the true transition graph}
}

$$

而：

$$
\boxed{
\text{MCTS only explores a tiny adaptive subgraph}
}

$$

而 policy network 决定的是：

$$
\text{which edges are worth examining first}.

$$

value network 决定的是：

$$
\text{which unexplored regions look promising}.

$$

这是理解整个 AlphaProof 类架构最重要的数学视角之一。

---

# 44. 最终把 CPU 部分压缩成一个优化问题

可以把 CPU search 抽象成：

$$
\min_{\text{search allocation}}
\quad
\mathbb E[\text{time to find proof}]

$$

subject to

$$
T(s,a)

$$

必须由 Lean 验证，并且最终：

$$
G(s_T)=\varnothing.

$$

神经网络提供：

$$
\pi_\theta(a|s),
\quad
V_\phi(s),

$$

MCTS 则决定：

$$
\boxed{
\text{在哪些 }(s,a)\text{ 上花 CPU 预算}
}

$$

Lean 决定：

$$
\boxed{
\text{哪些转移是真实存在的}
}

$$

reward 决定：

$$
\boxed{
\text{什么叫“更好的证明路径”}
}

$$

---

# 45. CPU 侧最重要的四个“真相源”

因此，如果你以后要自己实现这个系统，可以记住：

$$
\boxed{
\begin{array}{ll}
\textbf{Lean kernel} & \text{负责最终正确性}\\
\textbf{Lean environment} & \text{负责状态转移}\\
\textbf{MCTS} & \text{负责搜索资源分配}\\
\textbf{policy/value} & \text{负责搜索启发式}
\end{array}}

$$

其中优先级严格是：

$$
\text{Kernel correctness}
>
\text{Environment}
>
\text{Search heuristic}
>
\text{Neural prediction}.

$$

换句话说，即使 GPU 完全错了：

$$
\pi_\theta,\;V_\phi

$$

只会导致：

$$
\text{搜索效率下降}.

$$

但是如果 Lean environment/kernel 错了，则：

$$
\boxed{\text{整个证明系统的语义基础被破坏}}

$$

这也是 formal theorem proving 和一般 LLM reasoning 最大的结构性区别。

---

下一层如果继续往下推，最自然的就是把 **“CPU 的 MCTS + Lean environment”完整写成一个严格的递归算法**：从 `Node/Edge/AND-node` 数据结构开始，精确定义 \(N,Q,P,V\)、selection、progressive sampling、AND-node backprop、terminal proof、timeout，以及整个 search 的伪代码；然后再把它与 GPU 侧的 **policy head、value head、TTRL/test-time training** 接起来。这个层次会直接进入可以实现的算法规格。

[1]: https://www.nature.com/articles/s41586-025-09833-y?utm_source=chatgpt.com "Olympiad-level formal mathematical reasoning with reinforcement learning | Nature"
[2]: https://lean-lang.org/doc/reference/latest/Tactic-Proofs/?utm_source=chatgpt.com "Tactic Proofs"
[3]: https://lean-lang.org/doc/reference/latest/Terms/?utm_source=chatgpt.com "Terms"
[4]: https://t.co/eUGKeVr9eg?utm_source=chatgpt.com "Olympiad-level formal mathematical reasoning with reinforcement learning | Nature"
[5]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12999475/?utm_source=chatgpt.com "Olympiad-level formal mathematical reasoning with reinforcement learning - PMC"
[6]: https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/?utm_source=chatgpt.com "Elaboration and Compilation"
