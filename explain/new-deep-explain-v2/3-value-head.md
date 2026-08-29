是的，这三个问题其实应该放在一起回答，因为它们对应一个完整的设计决策：

$$
\boxed{
\text{Value 怎么学}
\;\rightarrow\;
\text{AlphaProof 怎么整体学}
\;\rightarrow\;
\text{我们能不能拿现成模型直接初始化 Value}
}
$$

先给结论：

1. **Value network 最直接的训练方法不是“从零学一个神秘的 value function”，而是把 Lean proof trajectory 转成 supervised regression。** AlphaProof 官方公开的训练描述也是从 Mathlib proof 中初始化 value head，使它预测“剩余 proof steps”，然后在 RL 中继续学习。([Nature][1])
2. **如果复刻 AlphaProof，最重要的不是复刻它的 300B token pretraining，而是复刻“Lean + search + policy/value + self-generated RL”这个闭环。** 官方论文明确给出的 pipeline 是：大规模预训练 → Mathlib SFT → auto-formalization → Lean 中的 RL/search → replay/training → test-time RL。([Nature][1])
3. **目前公开生态里，我没有找到一个明确公开、专门针对 Lean proof-state 训练、可以直接拿来当 AlphaProof-style scalar value function 的成熟 pretrained checkpoint。** 有一些非常接近的模型和项目，但多数是 policy/retriever/prover，而不是 value head。比如 LeanCopilot 提供 tactic-generation/retrieval 模型，DeepSeek-Prover/STP 是 policy/prover 路线，Stanford Lean EBM 则明确提出“用 pretrained math LLM + 新增 scalar energy/value head”的路线。([GitHub][2])
4. **所以如果你的目标是实际复刻，我最推荐的路线不是从零训练 value model，而是：数学/Lean pretrained LLM → 冻结或半冻结 backbone → 新增 scalar value head → 用 Mathlib proof trajectories 做 value SFT → 再用 MCTS-generated data 做 RL/TTT。**

下面详细拆开。

---

# 一、首先严格定义：我们到底要训练什么 Value？

前面我们定义了：

$$
r_t=-1
$$

如果一条 proof trajectory 是

$$
s_0
\xrightarrow{a_0}
s_1
\xrightarrow{a_1}
\cdots
\xrightarrow{a_{T-1}}
s_T,
$$

且：

$$
s_T=\text{Solved},
$$

那么从 \(s_t\) 开始的 return：

$$
G_t
=
\sum_{k=t}^{T-1}r_k
=
-(T-t).
$$

因此最理想的 value function 是：

$$
\boxed{
V^*(s_t)=-d^*(s_t)
}
$$

其中：

$$
d^*(s)
=
\text{从 }s\text{ 到一个 solved state 所需的最优剩余步数}.
$$

如果考虑 stochastic policy，则：

$$
V^\pi(s)
=
\mathbb E_\pi
\left[
\sum_{k=t}^{T-1}r_k
\mid s_t=s
\right].
$$

所以 AlphaProof-style value head 本质上是在学习：

$$
\boxed{
s
\longmapsto
\text{expected negative remaining proof length}
}
$$

而不是一个模糊的：

> “这个 theorem 看起来难不难？”

这是一个非常重要的区别。

---

# 二、Value network 有哪些训练方法？

至少有 **六类**，而且可以组合。

---

## 方法 1：直接 supervised regression

这是我认为复刻 AlphaProof 时最应该首先做的。

从已有正确 Lean proof：

$$
s_0,a_0,s_1,a_1,\ldots,s_T
$$

直接构造：

$$
(s_t,z_t)
$$

其中：

$$
z_t=-(T-t).
$$

于是数据：

$$
D_V=
\{
(s_t,-(T-t))
\}.
$$

loss：

$$
\boxed{
L_V
=
\frac1N
\sum_i
\left(
V_\phi(s_i)-z_i
\right)^2
}
$$

或者：

$$
L_V=
\frac1N
\sum_i
|V_\phi(s_i)-z_i|.
$$

也可以用 Huber loss：

$$
L_V=
\operatorname{Huber}(V_\phi(s)-z).
$$

### 优点

极其简单：

* 不需要 RL；
* 不需要 MCTS；
* 不需要 reward propagation；
* Lean proof 本身就是 ground truth；
* 一个 proof 可以产生很多 training examples。

例如 100-step proof：

$$
100
$$

个 state 基本上就产生：

$$
100
$$

个 value labels。

而 AlphaProof 的公开训练描述明确说，SFT 阶段就用 Mathlib proof structure 来初始化 value head，使其预测剩余 proof steps。([Nature][1])

---

# 三、方法 2：Monte Carlo return regression

这比上面的 supervised value training 更一般。

你不要求 trajectory 是最优 proof。

只要 trajectory 最终成功：

$$
s_t\rightarrow\cdots\rightarrow s_T,
$$

就定义：

$$
z_t=-\left(T-t\right).
$$

然后：

$$
V_\phi(s_t)\approx z_t.
$$

这其实就是：

$$
\boxed{\text{Monte Carlo value estimation}}
$$

即：

$$
V^\pi(s)
=
\mathbb E_\pi[G_t\mid s].
$$

如果 trajectory 来自当前 policy：

$$
\pi_\theta,
$$

那么训练的是：

$$
V^{\pi_\theta}.
$$

这与“optimal value”

$$
V^*
$$

有区别。

---

# 四、方法 3：TD learning

可以不用等整条 proof 结束。

定义：

$$
r_t=-1.
$$

Bellman equation：

$$
V^\pi(s_t)
=
r_t+
\gamma V^\pi(s_{t+1}).
$$

于是 TD target：

$$
y_t
=
-1+
\gamma V_{\phi^-}(s_{t+1}),
$$

loss：

$$
\boxed{
L_{\mathrm{TD}}
=
\left(
V_\phi(s_t)
-
[-1+\gamma V_{\phi^-}(s_{t+1})]
\right)^2
}
$$

其中 \(\phi^-\) 可以是 target network 参数。

如果：

$$
\gamma=1,
$$

则：

$$
V(s_t)\approx -1+V(s_{t+1}).
$$

这与：

$$
V(s_t)=-d(s_t)
$$

完全一致，因为：

$$
-d(s_t)
=
-1-d(s_{t+1}).
$$

### 优点

不需要完整 proof。

### 缺点

误差会 bootstrap：

$$
\text{error}(V(s_{t+1}))
\rightarrow
\text{error}(V(s_t)).
$$

对于 theorem proving 这种长 horizon 问题，这一点非常重要。

---

# 五、方法 4：MCTS value target

这才是 AlphaZero/AlphaProof 风格最关键的方法。

假设 CPU MCTS 对：

$$
s
$$

进行了大量 search。

得到：

$$
Q_{\mathrm{MCTS}}(s,a)
$$

以及 root/search value：

$$
V_{\mathrm{MCTS}}(s).
$$

那么可以把：

$$
\boxed{
V_{\mathrm{MCTS}}(s)
}
$$

作为训练 target：

$$
L_V
=
\left(
V_\phi(s)
-
V_{\mathrm{MCTS}}(s)
\right)^2.
$$

于是：

$$
\boxed{
\text{network value}
\rightarrow
\text{MCTS}
\rightarrow
\text{better value estimate}
\rightarrow
\text{train value network}
}
$$

这比简单模仿人类 proof 更强，因为 MCTS 发现的是：

$$
\text{search-improved value}.
$$

---

# 六、方法 5：pairwise / ranking value learning

其实对于 MCTS，value 的绝对数值并不一定比排序更重要。

假设：

$$
s_1
$$

最终需要：

$$
3
$$

步；

$$
s_2
$$

最终需要：

$$
15
$$

步。

我们至少知道：

$$
V(s_1)>V(s_2).
$$

于是可以做 ranking loss：

$$
L_{\mathrm{rank}}
=
\log
\left[
1+
\exp
\left(
-(V(s_1)-V(s_2))
\right)
\right].
$$

或者 margin loss：

$$
L_{\mathrm{margin}}
=
\max
\left(
0,
m-V(s_1)+V(s_2)
\right).
$$

这对于 MCTS 很有意义，因为 selection 主要需要：

$$
Q(s,a_1)>Q(s,a_2).
$$

而不一定需要：

$$
Q(s,a)=\text{完美校准的概率}.
$$

---

# 七、方法 6：成功概率 value，而不是 remaining steps

这是一个非常值得考虑的替代设计。

不要定义：

$$
V(s)=-\mathbb E[\text{steps}].
$$

而定义：

$$
V(s)
=
P(\text{eventual proof success}\mid s).
$$

于是：

$$
V(s)\in[0,1].
$$

loss：

$$
L_V
=
-\left[
y\log V(s)
+
(1-y)\log(1-V(s))
\right].
$$

其中：

$$
y=
\begin{cases}
1 & \text{最终成功}\\
0 & \text{最终失败}.
\end{cases}
$$

这在工程上其实很有吸引力。

---

# 八、但 AlphaProof 的 value 为什么不直接用 success probability？

因为它的 reward 定义：

$$
r=-1
$$

天然让 value 表示：

$$
-\text{remaining proof steps}.
$$

这同时编码：

1. 能不能成功；
2. 大概多远；
3. 更短的 proof 更好。

例如两个状态：

$$
s_1:\quad P_{\mathrm{success}}=0.9,\quad L=100
$$

$$
s_2:\quad P_{\mathrm{success}}=0.9,\quad L=10.
$$

如果只预测 success probability：

$$
V(s_1)=V(s_2)=0.9.
$$

无法区分。

而 negative-step value：

$$
V(s_1)\approx -100
$$

$$
V(s_2)\approx -10.
$$

搜索就能明显偏好：

$$
s_2.
$$

所以对于 AlphaProof 这种**最短/快速找到 proof** 的搜索系统，我认为：

$$
\boxed{
V=-\text{remaining steps}
}
$$

是更自然的第一版。

---

# 九、AlphaProof 到底是怎么训练的？

现在回答第二个问题。

根据 Nature 论文公开的训练描述，AlphaProof 的 pipeline 可以概括成：

$$
\boxed{
\text{Pretraining}
\rightarrow
\text{SFT}
\rightarrow
\text{Autoformalization}
\rightarrow
\text{RL/Search}
\rightarrow
\text{Test-time RL}
}
$$

官方披露的信息非常具体。([Nature][1])

---

# 十、Stage 1：大规模 pretraining

AlphaProof 的 proof network 首先进行了非常大规模的预训练：

$$
\sim300\text{ billion tokens}
$$

来源包括：

* public code；
* mathematical text。

目标主要是：

$$
\boxed{
\text{next-token prediction}
}
$$

并结合 masked span reconstruction 等正则化。

论文报告 encoder 处理约 12T tokens，decoder reconstruction 约 3T tokens。([Nature][1])

这个阶段的目标不是：

> 学会证明 Lean theorem。

而是让模型拥有：

$$
\text{programming}
+
\text{formal syntax}
+
\text{mathematics}
+
\text{language}
$$

的基础 representation。

---

# 十一、Stage 2：Mathlib SFT

然后是非常重要的一步。

从 Mathlib 的人工 proof 中提取：

$$
(s,a)
$$

即：

$$
\boxed{
\text{Lean proof state}
\rightarrow
\text{human tactic}
}
$$

论文报告大约：

$$
300,000
$$

个 state–tactic pairs，总计约 5M tactic tokens。([Nature][1])

policy loss：

$$
L_\pi
=
-\log\pi_\theta(a^*\mid s).
$$

---

# 十二、关键：SFT 阶段同时初始化 value head

这正好回答你的第一个问题。

AlphaProof 并不是：

$$
\text{random value head}
\rightarrow
\text{直接 RL}.
$$

而是使用 Mathlib proofs 的结构：

$$
s_t\rightarrow\cdots\rightarrow s_T
$$

构造 remaining-step target：

$$
z_t=-(T-t).
$$

然后训练 value head：

$$
V_\phi(s_t)\approx z_t.
$$

官方 Nature 论文明确这样描述：SFT 阶段除了让 policy 学 Lean tactic generation，也初始化 value head，使其估计 proof 剩余步骤。([Nature][1])

这其实是整个系统中非常聪明的一步。

---

# 十三、为什么这一步如此重要？

如果 value head 从随机初始化：

$$
V_{\phi_0}(s)\sim\text{random},
$$

那么初始 MCTS：

$$
Q(s,a)
$$

几乎没有意义。

搜索只能依赖：

$$
\pi_\theta.
$$

而 policy 又只是 SFT 后的模仿模型。

于是 RL 初期会非常低效。

但是如果先训练：

$$
V_\phi(s)\approx-\text{remaining steps},
$$

那么从第一轮 RL 开始：

$$
\boxed{
\text{MCTS already has a meaningful heuristic}
}
$$

这对复刻非常重要。

---

# 十四、Stage 3：Autoformalization

问题是：

Mathlib 只有大约有限规模的人工 theorem/proof corpus。

AlphaProof 需要远远更多的 RL experience。

所以它先把大量自然语言数学问题自动形式化为 Lean：

$$
x_{\mathrm{NL}}
\rightarrow
p_{\mathrm{Lean}}.
$$

官方报告从约：

$$
1\text{ million}
$$

自然语言数学 statements 生成约：

$$
80\text{ million}
$$

Lean problems。([Nature][1])

这一步非常关键：

$$
\boxed{
\text{formal theorem generation}
}
$$

本质上是 RL environment 的 curriculum generator。

---

# 十五、Stage 4：Main RL

现在：

$$
P_1,\ldots,P_N
$$

都是 Lean theorem。

CPU actor：

$$
\text{MCTS}
$$

尝试证明。

每次：

$$
s
\rightarrow
a
\rightarrow
s'
$$

Lean 验证。

成功：

$$
\text{proof found}.
$$

失败：

$$
\text{no proof under budget}.
$$

于是得到新的：

$$
D_{\mathrm{RL}}.
$$

然后训练：

$$
\pi_\theta
$$

和：

$$
V_\phi.
$$

论文明确说 AlphaProof 在 RL 阶段的 proof 是**系统自己与 Lean environment 交互生成的**，而不是人工逐条提供。([PubMed Central (PMC)][3])

---

# 十六、这就是 AlphaProof 真正的“self-play”

严格说它不是棋类意义的：

$$
\text{player A vs player B}.
$$

而是：

$$
\boxed{
\text{model}
\leftrightarrow
\text{formal environment}
}
$$

不断生成：

$$
\text{experience}.
$$

因此更准确地说：

$$
\boxed{
\text{self-generated formal proof experience}
}
$$

---

# 十七、AlphaProof 的 RL curriculum 也很重要

不是：

$$
\text{所有 theorem 同时给最大搜索预算}.
$$

而是动态增加：

$$
B_1<B_2<B_3<\cdots
$$

的 search budget。

早期：

$$
\text{small budget}.
$$

容易问题迅速解决。

随着模型变强：

$$
\text{larger budget}.
$$

开始挑战难题。

AlphaProof 的公开描述明确提到这种逐渐增加 search compute 的训练策略。([朱利安][4])

---

# 十八、AlphaProof 还会重复尝试已经解决的问题

这一点也很有意思。

如果 theorem：

$$
P
$$

已经找到 proof：

$$
L=100,
$$

不会简单：

$$
\text{delete}(P).
$$

因为后来模型可能找到：

$$
L=30.
$$

而 reward：

$$
r=-1
$$

意味着：

$$
-30>-100.
$$

所以 theorem 可以成为：

$$
\boxed{\text{持续的 curriculum}}
$$

直到找到更好的 proof。

官方方法说明也明确描述了这一策略。([朱利安][4])

---

# 十九、如果我们要复刻 AlphaProof，有三条路线

我会把它分成：

### Route A：Faithful reproduction

尽量模仿 AlphaProof：

$$
\text{LLM}
\rightarrow
\text{Lean SFT}
\rightarrow
\text{MCTS}
\rightarrow
\text{RL}
\rightarrow
\text{TTT}.
$$

### Route B：Practical reproduction

不复制 300B pretraining：

$$
\boxed{
\text{existing math LLM}
\rightarrow
\text{Lean SFT}
\rightarrow
\text{value head}
\rightarrow
\text{MCTS}
\rightarrow
\text{RL}
}
$$

我认为这是你真正应该做的。

### Route C：Minimal research prototype

甚至可以：

$$
\text{7B/14B math model}
\rightarrow
\text{Lean state/tactic SFT}
\rightarrow
\text{scalar value head}
\rightarrow
\text{MCTS}.
$$

然后只在后面增加 RL/TTT。

---

# 二十、我最推荐 Route B

因为你真正想复刻的是：

$$
\boxed{\text{AlphaProof 的算法结构}}
$$

而不是：

$$
\boxed{\text{AlphaProof 的 pretraining bill}}
$$

后者几乎不现实。

你可以直接使用已有数学 LLM 作为：

$$
f_\omega.
$$

然后新增：

$$
W_V\in\mathbb R^{d\times1}
$$

和：

$$
b_V\in\mathbb R.
$$

例如：

$$
h_{\mathrm{EOS}}\in\mathbb R^d
$$

然后：

$$
\boxed{
V_\phi(s)
=
w_V^\top h_{\mathrm{EOS}}+b_V
}
$$

这就是一个最简单的可微 value head。

---

# 二十一、你的第三个问题：有没有现成 Value model？

这里需要非常谨慎。

截至目前公开资料，我没有看到一个像：

> `DeepSeek-Prover-Value-7B`

这样已经成熟、广泛公开、专门训练成 AlphaProof-style：

$$
V(s)=\text{remaining proof value}
$$

的标准 checkpoint。

公开生态明显更偏：

$$
\boxed{\text{policy models}}
$$

而不是：

$$
\boxed{\text{value models}}.
$$

例如 LeanCopilot 提供 Lean tactic generation 和 premise retrieval 模型；其公开模型包括 ByT5 系列的 tactic generator/retriever，但它们不是 scalar value networks。([GitHub][2])

---

# 二十二、DeepSeek-Prover/STP 也不是你要的 Value Model

例如 STP 是基于 DeepSeek-Prover-V1.5 的 self-play theorem proving 路线。

它公开了：

* model；
* dataset；
* self-play generated proofs。

最终模型在 miniF2F 上报告 pass@3200 65.0%。([GitHub][5])

但是它本质上仍然是：

$$
\boxed{\text{proof-generation policy}}
$$

而不是：

$$
\boxed{
s\mapsto V(s)
}
$$

的 scalar value model。

---

# 二十三、但是有一个项目与你的想法非常接近

我特别建议你关注：

**Stanford Lean Club 的 `lean-ebm`。**

它的 README 直接提出：

> 用 pretrained math LLM，加一个 scalar energy/value head。

它甚至明确把当前 theorem proving architecture 概括为：

$$
\text{policy LLM}
+
\text{value LLM}
$$

并提出：

$$
\text{pretrained math model}
\rightarrow
\text{projection/scalar head}
$$

作为 energy/value model 的路线。([GitHub][6])

不过要注意：

$$
\boxed{
\text{这是研究项目/方向，不是一个已经成熟的 AlphaProof value checkpoint}
}
$$

所以它更适合作为**架构参考**，而不是直接下载一个成熟 value model。

---

# 二十四、实际上我认为“不需要找现成 value model”

这是这里最重要的工程判断。

因为：

$$
V(s)
$$

的训练数据非常容易构造。

假设 Mathlib 有：

$$
300,000
$$

个 state-tactic pairs。

更重要的是每个完整 proof trajectory：

$$
s_0,\ldots,s_T.
$$

你直接得到：

$$
(s_0,-T),
$$

$$
(s_1,-(T-1)),
$$

$$
\ldots
$$

$$
(s_T,0).
$$

因此 value pretraining dataset 可以比 policy SFT dataset **自然地大很多**。

你根本不需要：

$$
\text{100B-token value pretraining}.
$$

---

# 二十五、最简单的 value initialization

我建议：

$$
\boxed{
\text{Math LLM backbone}
+
\text{random scalar value head}
}
$$

然后冻结：

$$
\omega
$$

先训练：

$$
\phi.
$$

即：

$$
V_\phi(s)
=
w^\top h_{\mathrm{EOS}}+b.
$$

训练：

$$
L_V
=
\left(
w^\top h_{\mathrm{EOS}}+b
+
(T-t)
\right)^2.
$$

因为：

$$
z_t=-(T-t).
$$

---

# 二十六、第一阶段甚至可以只训练最后一个 linear head

这是我非常推荐的 baseline。

令：

$$
h_s=f_{\omega_0}(s)
$$

冻结：

$$
\omega_0.
$$

只优化：

$$
w,b.
$$

那么：

$$
V(s)=w^\top h_s+b.
$$

优化：

$$
\min_{w,b}
\sum_i
\left(
w^\top h_i+b-z_i
\right)^2.
$$

这是一个标准 linear regression。

甚至可以闭式求解：

$$
\hat\beta
=
(X^\top X+\lambda I)^{-1}X^\top z.
$$

这里：

$$
\beta=
\begin{bmatrix}
w\\b
\end{bmatrix}.
$$

这意味着：

$$
\boxed{
\text{value initialization 可以极其便宜}
}
$$

---

# 二十七、然后再逐渐解冻 backbone

第一阶段：

$$
\omega=\text{frozen}.
$$

第二阶段：

$$
\text{last }k\text{ transformer blocks}
$$

解冻。

第三阶段：

$$
\text{LoRA/adapters}.
$$

第四阶段才考虑 full fine-tuning。

因此：

$$
\boxed{
\text{linear head}
\rightarrow
\text{partial fine-tuning}
\rightarrow
\text{RL value improvement}
}
$$

---

# 二十八、我甚至建议同时训练两个 Value Head

这是一个比单一 value 更稳健的设计。

定义：

$$
V_{\mathrm{len}}(s)
$$

预测：

$$
-\text{remaining steps}.
$$

同时：

$$
V_{\mathrm{succ}}(s)
$$

预测：

$$
P(\text{eventual success}\mid s).
$$

于是：

$$
V_{\mathrm{len}}\in\mathbb R
$$

而：

$$
V_{\mathrm{succ}}\in[0,1].
$$

GPU 输出：

$$
\boxed{
(\pi,V_{\mathrm{len}},V_{\mathrm{succ}})
}
$$

然后 MCTS 可以综合：

$$
Q
=
\alpha V_{\mathrm{len}}
+
\beta V_{\mathrm{succ}}.
$$

或者更严格地：

$$
Q
=
V_{\mathrm{len}}
$$

作为主 reward，

$$
V_{\mathrm{succ}}
$$

作为 risk estimator。

---

# 二十九、为什么双 value 很有用？

考虑：

### State A

$$
P_{\mathrm{success}}=0.95,
$$

$$
E[L\mid success]=100.
$$

### State B

$$
P_{\mathrm{success}}=0.60,
$$

$$
E[L\mid success]=5.
$$

如果只有：

$$
V_{\mathrm{len}},
$$

可能认为 B 极好。

如果只有：

$$
V_{\mathrm{succ}},
$$

可能认为 A 极好。

但实际 search allocation 需要同时知道：

$$
\boxed{
\text{success probability}
+
\text{cost-to-success}
}
$$

所以双 head 是一个非常合理的 research direction。

---

# 三十、如果你要真正复刻，我建议的数据 pipeline

我会把整个工程分成 **5 个阶段**。

---

## Phase 0：Lean environment

先实现：

$$
\mathsf{Step}(s,a)
$$

以及：

$$
\mathsf{Solved}(s).
$$

用 Lean 4 + Mathlib。

---

## Phase 1：Policy SFT

选择一个数学 LLM：

$$
f_\omega.
$$

构造：

$$
(s,a^*)
$$

数据。

训练：

$$
L_\pi=-\log\pi_\theta(a^*|s).
$$

目标：

> 先让模型会基本 Lean。

---

## Phase 2：Value pretraining

同一批 proof trajectory：

$$
s_0,\ldots,s_T.
$$

构造：

$$
z_t=-(T-t).
$$

训练：

$$
L_V
=
(V_\phi(s_t)-z_t)^2.
$$

这个阶段甚至不需要 RL。

---

## Phase 3：CPU MCTS

GPU 固定：

$$
(\pi_\theta,V_\phi).
$$

CPU：

$$
\text{MCTS}
+
\text{Lean}.
$$

开始生成：

$$
D_{\mathrm{search}}.
$$

---

## Phase 4：Search-improvement training

从 MCTS 得：

$$
\hat\pi_{\mathrm{MCTS}}
$$

和：

$$
z_{\mathrm{MCTS}}.
$$

训练：

$$
L
=
\lambda_\pi
\operatorname{CE}
(\hat\pi_{\mathrm{MCTS}},\pi_\theta)
+
\lambda_V
(V_\phi-z)^2.
$$

然后：

$$
\Theta_{k+1}
=
\operatorname{Optimizer}(\Theta_k,D_k).
$$

---

## Phase 5：TTT

对于新 theorem \(P\)：

$$
\Theta_0
$$

开始。

运行：

$$
\text{MCTS}_{\Theta_0}(P).
$$

得到：

$$
D_0.
$$

然后：

$$
\Theta_1
=
\Theta_0-\eta\nabla L(D_0).
$$

再：

$$
\text{MCTS}_{\Theta_1}(P).
$$

如此循环：

$$
\boxed{
\Theta_0
\rightarrow D_0
\rightarrow\Theta_1
\rightarrow D_1
\rightarrow\Theta_2
\rightarrow\cdots
}
$$

直到找到 proof。

---

# 三十一、如果资源有限，我不会训练一个独立的 7B Value LLM

这是一个非常重要的架构建议。

不要：

$$
\text{7B policy}
+
\text{7B value}
$$

一开始就搞两个完整模型。

这会导致：

$$
\text{GPU memory}\times2
$$

以及 inference throughput 大幅下降。

我更推荐：

$$
\boxed{
\text{one shared backbone}
+
\text{policy head}
+
\text{scalar value head}
}
$$

即：

$$
h=f_\omega(s)
$$

然后：

$$
\pi=\operatorname{softmax}(W_\pi h)
$$

以及：

$$
V=W_Vh+b_V.
$$

---

# 三十二、甚至 Value Head 可以非常小

如果：

$$
d=4096
$$

那么：

$$
W_V\in\mathbb R^{1\times4096}.
$$

参数只有：

$$
4096+1.
$$

也就是说：

$$
\boxed{
\text{value head 本身几乎不需要计算资源}
}
$$

真正昂贵的是：

$$
f_\omega(s).
$$

所以“找一个现成的 pretrained value model”从工程上未必是最佳目标。

更好的目标是：

$$
\boxed{
\text{找一个好的 pretrained mathematical/Lean backbone}
}
$$

然后自己训练：

$$
V_\phi.
$$

---

# 三十三、那么应该找什么 pretrained backbone？

这才是第三个问题真正值得优化的地方。

目前公开生态中，可以考虑：

### 1. DeepSeek-Prover 系列

它本身就是 Lean theorem proving policy 路线，特别适合作为 policy/backbone 起点；STP 也直接基于 DeepSeek-Prover-V1.5-SFT 做 self-play。([GitHub][5])

### 2. LeanDojo / LeanCopilot 生态

这里已经有针对 Lean tactic generation 和 premise retrieval 的模型与工具链，非常适合构建你的第一版 Lean-specific policy pipeline。([GitHub][2])

### 3. 普通数学 LLM

如果目标是研究：

$$
\text{value representation}
$$

甚至可以直接从一个数学能力很强的 general math LLM 开始，再进行 Lean SFT。

---

# 三十四、一个很有意思的替代方案：用 policy LLM 自己当 value model

不一定需要额外训练一个独立模型。

可以定义：

$$
V(s)
=
g_\phi(
\operatorname{LLM}(s)
)
$$

其中：

$$
g_\phi
$$

只是 scalar projection。

即：

```text id="3a9vmu"
Lean state
    ↓
Math LLM
    ↓
hidden representation h
    ↓
linear / MLP head
    ↓
scalar V(s)
```

这其实就是我认为**最值得先做的实验**。

---

# 三十五、然后做一个非常强的 ablation

你可以测试：

$$
\text{Value quality}
$$

到底来自哪里。

分别训练：

### A

$$
\text{random backbone}
+
\text{value head}
$$

### B

$$
\text{math pretrained backbone}
+
\text{value head}
$$

### C

$$
\text{Lean SFT backbone}
+
\text{value head}
$$

### D

$$
\text{Lean SFT + MCTS-trained backbone}
+
\text{value head}.
$$

然后测：

$$
\operatorname{Corr}
(
V(s),
-d^*(s)
)
$$

以及：

$$
\text{MCTS proof success@budget}.
$$

我预计真正有意义的是：

$$
\boxed{
\text{C}\gg\text{B}\gg\text{A}
}
$$

而 D 再进一步提高。

---

# 三十六、比 MSE 更重要的一个指标

如果你的 value 最终只服务于 MCTS，那么不要只看：

$$
\operatorname{MSE}(V,z).
$$

更应该看：

$$
\boxed{
\operatorname{RankCorr}(V(s_i),V(s_j))
}
$$

因为 MCTS 更关心：

$$
V(s_i)>V(s_j)
$$

是否正确。

例如：

真实：

$$
V(s_1)=-5,\quad V(s_2)=-20.
$$

模型：

$$
V_\phi(s_1)=-2,\quad V_\phi(s_2)=-100.
$$

MSE 可能不漂亮，但排序：

$$
s_1>s_2
$$

完全正确。

MCTS 仍然可能非常有效。

---

# 三十七、所以我会把 Value training 做成三阶段

最终我推荐：

$$
\boxed{
\text{Stage A: supervised distance}
}
$$

$$
V(s)\approx-\text{remaining proof steps}.
$$

↓

$$
\boxed{
\text{Stage B: search value distillation}
}
$$

$$
V(s)\approx V_{\mathrm{MCTS}}(s).
$$

↓

$$
\boxed{
\text{Stage C: test-time adaptation}
}
$$

$$
V_{\phi_{k+1}}
\leftarrow
V_{\phi_k}
-
\eta\nabla_\phi
L_{\mathrm{TTT}}.
$$

这比直接从零 RL 学 value 稳定得多。

---

# 三十八、最后回答你的三个问题

## 1. 价值网络怎么训练？

主要有：

$$
\boxed{
\begin{array}{ll}
\text{Supervised return regression}
& V(s)\rightarrow-\text{remaining steps}\\[2mm]
\text{Monte Carlo RL}
& V(s)\rightarrow G_t\\[2mm]
\text{TD learning}
& V(s)\rightarrow r+\gamma V(s')\\[2mm]
\text{MCTS distillation}
& V(s)\rightarrow V_{\mathrm{search}}(s)\\[2mm]
\text{Ranking loss}
& V(s_1)>V(s_2)\\[2mm]
\text{Success-probability modeling}
& V(s)\rightarrow P(\text{proof success})
\end{array}}
$$

**复刻 AlphaProof，我首选：**

$$
\boxed{
\text{Mathlib trajectory regression}
\rightarrow
\text{MCTS value distillation}
\rightarrow
\text{RL/TTT}
}
$$

---

## 2. AlphaProof 怎么训练？

公开资料给出的主干是：

$$
\boxed{
300B\text{-token pretraining}
}
$$

↓

$$
\boxed{
\text{Mathlib SFT}
}
$$

↓

$$
\boxed{
\text{value initialization}
}
$$

↓

$$
\boxed{
\sim80M\text{ auto-formalized Lean problems}
}
$$

↓

$$
\boxed{
\text{Lean + MCTS + RL}
}
$$

↓

$$
\boxed{
\text{self-generated proof experience}
}
$$

↓

$$
\boxed{
\text{repeated training/search}
}
$$

↓

$$
\boxed{
\text{test-time RL}
}
$$

这些关键数字和阶段来自 Nature 的公开方法。([Nature][1])

---

## 3. 有没有现成的 pretrained Value Network？

**目前没有看到一个公开、成熟、标准化、可以直接替代 AlphaProof value network 的 checkpoint。**

但是这反而不是坏事。

因为 Value head 极小，而且训练数据天然容易构造。

所以最合理的方案是：

$$
\boxed{
\text{现成数学/Lean LLM}
+
\text{自己训练 scalar value head}
}
$$

而不是：

$$
\text{寻找一个现成的 value LLM}.
$$

特别值得参考的是 Stanford Lean Club 的 `lean-ebm`，其公开设计正是“pretrained math LLM + scalar energy/value head”，但目前应把它视为研究方向/原型，而不是成熟的 AlphaProof value checkpoint。([GitHub][6])

---

# 三十九、如果是我来复刻，我会采用这个具体方案

最终架构：

$$
\boxed{
\begin{array}{c}
\text{DeepSeek-Prover / strong math LLM}\\
\downarrow\\
\text{Lean SFT}\\
\downarrow\\
h=f_\omega(s)\\
\begin{cases}
\text{Policy head} &\rightarrow \pi_\theta(a|s)\\
\text{Value head} &\rightarrow V_\phi(s)
\end{cases}\\
\downarrow\\
\text{CPU MCTS + Lean}\\
\downarrow\\
\text{verified search trajectories}\\
\downarrow\\
\text{policy/value training}\\
\downarrow\\
\text{new }\Theta\\
\downarrow\\
\text{MCTS again}
\end{array}}
$$

而且**第一版完全不需要 TTT**。

先做到：

$$
\boxed{
\text{SFT policy}
+
\text{SFT value}
+
\text{MCTS}
}
$$

确认 MCTS 确实比单纯 best-of-\(N\) / sampling 有优势。

然后：

$$
\boxed{
+\text{search-generated training}
}
$$

最后才加：

$$
\boxed{
+\text{TTT}
}
$$

否则三个变量同时变化，很难知道性能提升到底来自：

$$
\text{policy}
$$

还是：

$$
\text{value}
$$

还是：

$$
\text{MCTS}
$$

还是：

$$
\text{TTT}.
$$

**如果你下一步是准备真正实现这个系统，我建议下一轮直接进入最实用的层次：我可以给你设计一套“可实际跑起来的 AlphaProof-mini”训练方案，包括具体模型选择、Mathlib 数据如何抽取成 \((s,a,z)\)、value head 的 PyTorch 结构、MCTS 与 GPU batch inference 的接口、loss、replay buffer，以及第一版应该用多少 GPU/CPU 才能跑。**

[1]: https://www.nature.com/articles/s41586-025-09833-y?utm_source=chatgpt.com "Olympiad-level formal mathematical reasoning with reinforcement learning | Nature"
[2]: https://github.com/lean-dojo/LeanCopilot?utm_source=chatgpt.com "GitHub - lean-dojo/LeanCopilot: LLMs as Copilots for Theorem Proving in Lean · GitHub"
[3]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12999475/?utm_source=chatgpt.com "Olympiad-level formal mathematical reasoning with reinforcement learning - PMC"
[4]: https://www.julian.ac/blog/2025/11/13/alphaproof-paper/?utm_source=chatgpt.com "AlphaProof Paper"
[5]: https://github.com/kfdong/stp?utm_source=chatgpt.com "GitHub - kfdong/STP: The official implementation of \"Self-play LLM Theorem Provers with Iterative Conjecturing and Proving\" · GitHub"
[6]: https://github.com/StanfordLeanClub/lean-ebm?utm_source=chatgpt.com "GitHub - StanfordLeanClub/lean-ebm · GitHub"
