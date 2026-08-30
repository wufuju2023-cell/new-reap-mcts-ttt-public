接下来把 CPU 侧固定为一个黑盒搜索器，而把 GPU 侧完全展开。核心是：GPU 并不是直接“证明”，而是在给定 Lean proof state 的条件下，同时学习两个不同但耦合的量：

$$
\boxed{
\pi_\theta(a\mid s)
}

$$

负责回答“下一步应该尝试什么 tactic”，以及

$$
\boxed{
V_\phi(s)
}

$$

负责回答“从这个 state 出发，证明大概还有多远”。

然后再讨论 **parameter update** 和你特别点出的 **TTT（test-time training / test-time update）**。

---

# 1. GPU 侧的总体数学结构

把 CPU 侧提供给 GPU 的接口固定为：

$$
s\in\mathcal S
\longmapsto
x=\operatorname{Enc}(s).

$$

其中：

* \(s\) 是真正的 Lean proof state；
* \(x\) 是 GPU 能处理的 token sequence / structured representation。

GPU 模型定义为：

$$
f_{\Theta}(x)
=
\bigl(
\pi_\theta(\cdot\mid x),
V_\phi(x)
\bigr).

$$

如果采用共享 backbone，那么：

$$
\Theta=(\omega,\theta,\phi)

$$

其中：

* \(\omega\)：Transformer/LLM backbone；
* \(\theta\)：policy head；
* \(\phi\)：value head。

因此：

$$
h=\operatorname{Transformer}_\omega(x)

$$

然后：

$$
\pi_\theta(a\mid s)
=
\operatorname{PolicyHead}_\theta(h),

$$

$$
V_\phi(s)
=
\operatorname{ValueHead}_\phi(h).

$$

所以 GPU 本质上是：

$$
\boxed{
\text{shared representation}
+
\text{policy prediction}
+
\text{value prediction}
}

$$

---

# 2. 这里的“state”到底输入什么？

这是 theorem proving GPU 模型中最重要的语义问题之一。

Lean state 可以写：

$$
s=(\Gamma,L,G,M,\ldots)

$$

但不能直接把内部 C++/Lean runtime 对象送进 Transformer。

因此定义：

$$
x=\operatorname{Serialize}(s).

$$

例如一个 state：

```text
a b c : Nat
h1 : a < b
h2 : b < c
⊢ a < c
```

会被序列化成 token：

$$
x=(x_1,\ldots,x_n).

$$

例如抽象写成：

$$
x=
[
\texttt{context},
a,b,c,
\texttt{Nat},
h_1,
\texttt{a<b},
h_2,
\texttt{b<c},
\texttt{goal},
\texttt{a<c}
].

$$

这里有一个非常重要的概念：

$$
\boxed{
\text{GPU 通常看到的是 } \operatorname{Obs}(s)，
\text{而不是完整 Lean runtime state }s
}

$$

所以在概率建模上，更严格地说是：

$$
\pi_\theta(a\mid \operatorname{Obs}(s)).

$$

如果 serialization 丢失了某些影响 tactic validity 的信息，那么神经网络看到的是一个 **partial observation**。

---

# 3. Policy network 的数学定义

策略网络学习：

$$
\pi_\theta(a\mid s)

$$

也就是给定证明状态 \(s\)，下一步 tactic \(a\) 的条件概率。

如果 action 是一串 token：

$$
a=(y_1,\ldots,y_m),

$$

那么 autoregressive LLM 将其分解：

$$
\pi_\theta(a\mid s)
=
\prod_{j=1}^{m}
\pi_\theta(y_j\mid s,y_{<j}).

$$

因此 log-probability：

$$
\log \pi_\theta(a\mid s)
=
\sum_{j=1}^{m}
\log \pi_\theta(y_j\mid s,y_{<j}).

$$

这是非常关键的，因为 MCTS 所需要的是**完整 tactic action 的 prior**，而 LLM 本质上是 token-level distribution。

于是：

$$
\boxed{
\text{LLM token distribution}
\rightarrow
\text{tactic-level action prior}
}

$$

中间必须存在一个 action sampling / completion 过程。

---

# 4. 为什么不能直接把 token probability 当成 PUCT prior？

例如：

```text
apply Nat.lt_trans
```

其概率是：

$$
P(
\texttt{apply Nat.lt\_trans}
\mid s
)

$$

而不是简单：

$$
P(\texttt{apply}\mid s).

$$

完整 action 概率应该是：

$$
P(a\mid s)
=
P(y_1\mid s)
P(y_2\mid s,y_1)
\cdots
P(y_m\mid s,y_{<m}).

$$

因此 GPU 端必须先生成完整 tactic candidate：

$$
a_1,\ldots,a_K

$$

再把这些 candidate 连同概率交给 CPU。

这就是：

$$
\boxed{
\text{token-level generation}
\rightarrow
\text{action-level prior}
}

$$

---

# 5. Candidate generation 是 GPU 与 CPU 的第一道边界

假设 GPU 输出：

$$
\{(a_i,p_i)\}_{i=1}^K

$$

其中：

$$
p_i=\pi_\theta(a_i\mid s).

$$

CPU 接收到后执行：

$$
T(s,a_i).

$$

注意：

$$
p_i>0

$$

绝不等价于：

$$
T(s,a_i)\neq\bot.

$$

即：

$$
\boxed{
\pi_\theta
\text{ 是 proposal mechanism，不是 verifier}
}

$$

这是整个系统设计上的核心原则。

---

# 6. Value network 是另一个完全不同的任务

policy：

$$
\pi_\theta(a\mid s)

$$

是在 action space 上的 probability distribution。

value：

$$
V_\phi(s)\in\mathbb R

$$

是在 state space 上的 scalar prediction。

二者语义完全不同。

policy 回答：

> 哪条边最值得搜索？

value 回答：

> 从这个节点往下搜索，预计会得到多大的 return？

在 AlphaProof 式 reward：

$$
r_t=-1

$$

下，可以令：

$$
G_t
=
\sum_{k=t}^{T-1}r_k
=
-(T-t).

$$

因此理想 value：

$$
V^*(s_t)
=
\mathbb E[G_t\mid s_t].

$$

如果 deterministic 且固定 optimal proof：

$$
V^*(s)
\approx
-d^*(s).

$$

---

# 7. 为什么 value head 必须是“可微”的？

你特别提到：

> 可微 value head

这里需要非常精确地区分两件事。

MCTS 的 **search update**：

$$
N,Q,V_{\text{search}}

$$

本身不是神经网络 gradient update。

而 value head：

$$
V_\phi(s)

$$

必须是参数 \(\phi\) 的可微函数，使我们能够计算：

$$
\nabla_\phi L_V.

$$

即：

$$
\boxed{
\text{MCTS update}
\neq
\text{gradient descent}
}

$$

MCTS 在 CPU 上改的是 search statistics；训练在 GPU 上改的是 neural parameters。

---

# 8. Value loss

如果一条搜索 trajectory 得到真实 return：

$$
z_t=G_t,

$$

那么最基本的 value regression：

$$
L_V(\phi)
=
\frac12
\left(
V_\phi(s_t)-z_t
\right)^2.

$$

梯度：

$$
\nabla_\phi L_V
=
\left(
V_\phi(s_t)-z_t
\right)
\nabla_\phi V_\phi(s_t).

$$

然后：

$$
\phi
\leftarrow
\phi-\eta_V\nabla_\phi L_V.

$$

因此 value head 学的是：

$$
s\mapsto \mathbb E[G\mid s].

$$

---

# 9. 但 theorem proving 的 value target 有一个特殊优势

因为 reward 极其干净：

$$
r_t=-1.

$$

所以完整 trajectory：

$$
s_0,a_0,s_1,a_1,\ldots,s_T

$$

如果 \(s_T\) solved，那么：

$$
z_t=-(T-t).

$$

因此每个 trajectory 天然给了大量 supervised targets：

$$
z_0=-T,

$$

$$
z_1=-(T-1),

$$

$$
\cdots

$$

$$
z_{T-1}=-1,

$$

$$
z_T=0.

$$

于是一个 proof：

$$
L=100

$$

本身就可以产生 101 个 value training examples。

这使得 proof search trajectory 非常适合做 value regression。

---

# 10. Policy 的训练目标是什么？

假设搜索最终产生一条实际 tactic：

$$
a_t^*.

$$

那么最直接的 imitation objective 是：

$$
L_\pi
=
-\log\pi_\theta(a_t^*\mid s_t).

$$

整个 trajectory：

$$
L_\pi
=
-\sum_t
\log\pi_\theta(a_t^*\mid s_t).

$$

这其实就是：

$$
\boxed{\text{behavior cloning / supervised policy learning}}

$$

---

# 11. 但是 AlphaZero 风格训练通常更有意思

MCTS 比单条最终 proof 提供了更多信息。

例如 root 上经过大量 search 后：

$$
N(s,a_1)=500

$$

$$
N(s,a_2)=20

$$

$$
N(s,a_3)=3.

$$

可以定义 search-improved policy：

$$
\hat\pi_{\mathrm{MCTS}}(a\mid s)
=
\frac{N(s,a)^{1/\tau}}
{\sum_b N(s,b)^{1/\tau}}.

$$

然后训练：

$$
L_\pi
=
-
\sum_a
\hat\pi_{\mathrm{MCTS}}(a\mid s)
\log\pi_\theta(a\mid s).

$$

即：

$$
\boxed{
\text{train network to imitate its own improved search policy}
}

$$

这是 AlphaZero 系思想的核心。

---

# 12. 为什么这比直接模仿“最终 proof action”更好？

因为最终 proof 只告诉你：

$$
a^*=\text{one successful action}.

$$

但 MCTS 告诉你：

$$
a_1:
\text{非常有希望}

$$

$$
a_2:
\text{偶尔成功}

$$

$$
a_3:
\text{明显差}

$$

等更丰富的信息。

所以：

$$
\hat\pi_{\mathrm{search}}

$$

包含了搜索器对 action space 的 posterior-like refinement。

于是：

$$
\pi_\theta
\longrightarrow
\hat\pi_{\mathrm{search}}
\longrightarrow
\pi_{\theta'}

$$

形成 policy improvement loop。

---

# 13. GPU 和 CPU 的闭环

于是整个系统真正的核心循环是：

$$
\boxed{
\pi_\theta,V_\phi
\rightarrow
\text{MCTS}
\rightarrow
\text{better search statistics}
\rightarrow
\text{training targets}
\rightarrow
\pi_{\theta'},V_{\phi'}
}

$$

即：

$$
\boxed{
\text{learning improves search}
}

$$

以及：

$$
\boxed{
\text{search improves learning}
}

$$

这就是 self-improvement。

---

# 14. 更严格地表示这个 fixed-point loop

定义 search operator：

$$
\mathcal S(f_\Theta)

$$

表示使用当前 neural model \(f_\Theta\) 运行大量 MCTS 后得到的数据分布。

然后 training operator：

$$
\mathcal T(D)

$$

表示在数据集 \(D\) 上优化参数。

于是整个迭代：

$$
\Theta_{k+1}
=
\mathcal T\bigl(
\mathcal S(\Theta_k)
\bigr).

$$

所以理想状态是求某种 fixed point：

$$
\Theta^*
=
\mathcal T(\mathcal S(\Theta^*)).

$$

当然实际系统不会严格收敛到这个数学 fixed point，但这个形式非常有用。

---

# 15. Policy + Value 的共享 backbone

最典型架构：

$$
x
\rightarrow
\operatorname{Transformer}_\omega
\rightarrow
h.

$$

然后：

$$
h
\rightarrow
\text{policy head}
\rightarrow
\pi_\theta

$$

和：

$$
h
\rightarrow
\text{value head}
\rightarrow
V_\phi.

$$

因此：

$$
\Theta=(\omega,\theta,\phi).

$$

总 loss 可以写成：

$$
L(\Theta)
=
\lambda_\pi L_\pi
+
\lambda_V L_V
+
\lambda_R L_{\mathrm{reg}}.

$$

其中：

* \(L_\pi\)：policy loss；
* \(L_V\)：value loss；
* \(L_{\mathrm{reg}}\)：regularization。

---

# 16. 如果只训练 value head，会发生什么？

假设：

$$
\omega,\theta

$$

固定，只更新：

$$
\phi.

$$

那么：

$$
\phi
\leftarrow
\phi-\eta\nabla_\phi L_V.

$$

这样：

$$
V_\phi

$$

逐渐学会判断 theorem state。

但是 policy 不变：

$$
\pi_\theta(a\mid s)

$$

不会改善。

因此：

$$
\boxed{
\text{better value}
\not\Rightarrow
\text{better proposal distribution}
}

$$

---

# 17. 如果只训练 policy 呢？

则：

$$
\theta
\leftarrow
\theta-\eta\nabla_\theta L_\pi.

$$

会让：

$$
\pi_\theta

$$

越来越接近搜索得到的 tactic distribution。

但没有 value，就会损失：

$$
\text{leaf evaluation}

$$

能力。

于是 MCTS 必须更依赖 deeper rollout /更多搜索。

所以 policy 和 value 是互补的：

$$
\boxed{
\pi:\text{breadth prioritization}
}

$$

$$
\boxed{
V:\text{depth estimation}
}

$$

---

# 18. 一个非常有用的几何解释

把证明空间看成一个巨大图：

$$
\mathcal G=(S,E).

$$

policy 给每一个 state 一个方向场：

$$
s
\mapsto
\pi(\cdot|s).

$$

value 给每一个 state 一个标量势函数：

$$
s
\mapsto
V(s).

$$

因此：

* policy 是 vector/distribution-like guidance；
* value 是 scalar heuristic。

MCTS 综合二者：

$$
\text{search}
=
\text{prior}
+
\text{value}
+
\text{actual Lean transitions}.

$$

---

# 19. 训练数据到底从哪里来？

CPU MCTS 最终可以产生：

$$
D=
\{
(s_i,
\hat\pi_i,
z_i,
a_i^*)
\}_{i=1}^N.

$$

其中：

* \(s_i\)：Lean state；
* \(\hat\pi_i\)：MCTS visit-count distribution；
* \(z_i\)：actual return；
* \(a_i^*\)：最终成功 trajectory 上的 action。

于是 GPU dataset 可以写成：

$$
D_{\text{policy}}
=
\{(s_i,\hat\pi_i)\}

$$

以及：

$$
D_{\text{value}}
=
\{(s_i,z_i)\}.

$$

---

# 20. Offline training

最标准的参数更新：

$$
\Theta_{k+1}
=
\operatorname{Optimizer}
\left(
\Theta_k,D
\right).

$$

例如 SGD：

$$
\Theta'
=
\Theta-\eta
\nabla_\Theta
L(D;\Theta).

$$

或 Adam 类 optimizer。

这个过程通常发生在 GPU。

CPU 负责：

$$
D\leftarrow\text{search}

$$

GPU 负责：

$$
D\rightarrow\Theta'.

$$

---

# 21. 为什么必须区别“search-time inference”和“training-time gradient”？

因为它们发生在完全不同的计算图上。

### MCTS：

$$
s
\xrightarrow{\text{network inference}}
(\pi,V)

$$

通常：

$$
\texttt{no\_grad}.

$$

因为只是推理。

### Training：

$$
(s,\hat\pi,z)
\xrightarrow{\text{forward}}
L
\xrightarrow{\text{backward}}
\nabla_\Theta L
\xrightarrow{\text{optimizer}}
\Theta'.

$$

所以：

$$
\boxed{
\text{MCTS inference graph}
\neq
\text{training computation graph}
}

$$

---

# 22. 现在进入你特别关心的 TTT

TTT：

$$
\boxed{\text{Test-Time Training}}

$$

本质上不是：

$$
\text{只推理，不更新参数}.

$$

而是：

$$
\boxed{
\text{在测试/推理阶段，用当前 problem 自己产生的数据，暂时更新模型}
}

$$

因此对于 theorem proving：

$$
\Theta_0
\rightarrow
\Theta_1
\rightarrow
\Theta_2
\rightarrow
\cdots

$$

其中每次：

$$
\Theta_{k+1}
=
\Theta_k-\eta
\nabla_\Theta L_{\mathrm{TTT}}(D_{\mathrm{test}}).

$$

---

# 23. TTT 在 theorem proving 里为什么特别自然？

假设面对新的 theorem：

$$
P_{\mathrm{new}}.

$$

开始时：

$$
\Theta_0

$$

并不知道这个 theorem 的具体结构。

MCTS 开始搜索，产生：

$$
D_0.

$$

其中包含：

* 成功 tactics；
* 失败 tactics；
* useful states；
* proof trajectories；
* value targets；
* search distributions。

这些数据虽然来自同一个 theorem，但它们是非常有价值的 local supervision。

所以可以：

$$
D_0
\rightarrow
\Theta_1

$$

再用：

$$
\Theta_1

$$

继续搜索。

然后：

$$
D_1
\rightarrow
\Theta_2.

$$

形成：

$$
\boxed{
\text{search}
\rightarrow
\text{adapt}
\rightarrow
\text{better search}
\rightarrow
\text{adapt}
}

$$

---

# 24. TTT 不等于简单“拿最终 proof fine-tune 一下”

这是最重要的区别之一。

如果只拿最终 proof：

$$
\tau^*=
(s_0,a_0,s_1,a_1,\ldots)

$$

训练：

$$
L=
-\sum_t\log\pi_\theta(a_t^*|s_t),

$$

那么只是：

$$
\text{test-time imitation}.

$$

真正有价值的 TTT 通常利用搜索本身产生的大量结构化 signals，例如：

$$
\boxed{
\begin{aligned}
&\text{successful trajectories}\\
&\text{MCTS visit distributions}\\
&\text{value targets}\\
&\text{hard negatives}\\
&\text{proof-state transitions}
\end{aligned}
}

$$

---

# 25. 一个自然的 TTT loss

可以定义：

$$
L_{\mathrm{TTT}}
=
\lambda_\pi L_{\pi}^{\mathrm{search}}
+
\lambda_VL_V
+
\lambda_{\mathrm{aux}}L_{\mathrm{aux}}.

$$

其中：

$$
L_{\pi}^{\mathrm{search}}
=
-\sum_a
\hat\pi_{\mathrm{MCTS}}(a|s)
\log\pi_\theta(a|s),

$$

以及：

$$
L_V
=
\frac12(V_\phi(s)-z)^2.

$$

这样每轮 test-time update：

$$
\Theta_{k+1}
=
\Theta_k-
\eta_k\nabla_\Theta
L_{\mathrm{TTT}}.

$$

---

# 26. 但是 TTT 最大的问题是“确认偏差”

假设当前 policy 错误地偏爱：

$$
a_{\mathrm{bad}}.

$$

MCTS 很多时候也会探索：

$$
a_{\mathrm{bad}}.

$$

如果随后把这些 search outcomes 直接用来训练：

$$
\pi_{\theta}

$$

那么：

$$
\text{错误 prior}
\rightarrow
\text{错误 search}
\rightarrow
\text{错误 training data}
\rightarrow
\text{更强错误 prior}.

$$

形成：

$$
\boxed{
\text{self-reinforcing error loop}
}

$$

这是 TTT + search 系统最危险的问题之一。

---

# 27. Lean 为什么恰好可以解决一部分 confirmation bias？

因为 Lean 给了一个非常强的 hard filter。

假设 network 提议：

$$
a_{\mathrm{bad}}

$$

则：

$$
T(s,a_{\mathrm{bad}})=\bot.

$$

它不能作为“成功 proof transition”加入 positive trajectory。

因此：

$$
\boxed{
\text{formal verification suppresses many hallucinated positives}
}

$$

注意不是消除所有错误。

因为：

$$
a_{\mathrm{bad}}

$$

可能**合法但最终走向死路**。

于是：

$$
T(s,a_{\mathrm{bad}})=s'

$$

但：

$$
s'
\not\leadsto
\text{proof}.

$$

这种错误更难检测。

---

# 28. 所以 MCTS 是 TTT 的“数据净化器”

这是一个非常重要的系统级观点。

单纯 LLM：

$$
\pi_\theta

$$

产生 noisy data。

Lean：

$$
T

$$

给出 hard validity。

MCTS：

$$
\mathcal S

$$

再在 valid transitions 上寻找真正有效的 long-horizon structure。

所以：

$$
\boxed{
\text{LLM}
\rightarrow
\text{Lean filter}
\rightarrow
\text{MCTS refinement}
\rightarrow
\text{TTT data}
}

$$

这一层比单纯 supervised fine-tuning 强得多。

---

# 29. TTT 的一个更严格数学框架

对于新 theorem \(P\)，定义：

$$
D_k
=
\mathcal S(P,\Theta_k)

$$

表示在参数：

$$
\Theta_k

$$

下运行搜索产生的数据。

然后：

$$
\Theta_{k+1}
=
\mathcal U(\Theta_k,D_k)

$$

其中：

$$
\mathcal U

$$

是 test-time optimizer。

于是：

$$
\boxed{
D_k=\mathcal S(P,\Theta_k)
}

$$

$$
\boxed{
\Theta_{k+1}
=
\mathcal U(\Theta_k,\mathcal S(P,\Theta_k))
}

$$

这就是 TTT theorem proving 的核心动力系统。

---

# 30. 它实际上是一个双层优化问题

外层目标：

$$
\max
P(\text{prove }P_{\mathrm{test}}
\mid
\Theta)

$$

而内层是：

$$
\Theta'
=
\operatorname{Train}
(
\Theta,D_{\mathrm{search}}(\Theta)
).

$$

因此：

$$
\boxed{
\Theta
\rightarrow
D(\Theta)
\rightarrow
\Theta'
\rightarrow
P(\text{success})
}

$$

这已经接近 meta-learning / bilevel optimization。

---

# 31. 为什么 value head 对 TTT 尤其重要？

假设只用成功 proof 做 policy TTT。

那么你只知道：

$$
a^*

$$

是好的。

但不知道：

$$
a_2,a_3,a_4

$$

到底有多差。

Value head 可以利用失败/部分成功状态学习：

$$
V(s).

$$

例如：

$$
s_1:\quad V=-3

$$

而：

$$
s_2:\quad V=-100.

$$

虽然二者都没有最终 solved，但：

$$
s_1

$$

明显比：

$$
s_2

$$

更 promising。

所以 value 学习为 TTT 提供了**dense-ish structural supervision**。

---

# 32. 可以进一步使用 advantage

对于一个 state \(s\) 和 action \(a\)，定义：

$$
A(s,a)
=
Q(s,a)-V(s).

$$

如果：

$$
A(s,a)>0

$$

说明这个 action 比当前 state 的平均预期更好。

于是 policy update 可以做：

$$
L_\pi
=
-
A(s,a)
\log\pi_\theta(a|s).

$$

这就从单纯 imitation 走向 policy-gradient-like weighting。

不过这里必须小心：AlphaProof-style 系统核心是 MCTS-improved policy/value training，而不是简单套 PPO。两者在数学上相关，但不能混为一谈。

---

# 33. Search statistics 本身就是一种“隐式 advantage”

例如：

$$
N(s,a_1)=100

$$

$$
N(s,a_2)=2.

$$

如果：

$$
Q(s,a_1)>Q(s,a_2),

$$

则 MCTS 已经在告诉 policy：

$$
a_1

$$

应该获得更高 probability mass。

所以：

$$
\hat\pi_{\mathrm{MCTS}}

$$

可以看作一种经过 search computation 后得到的 policy target。

---

# 34. 为什么 policy/value 可以共享 Transformer？

因为 theorem proving 中很多 representation 是共同的。

例如状态：

$$
s:
\quad
\Gamma\vdash g

$$

其中：

$$
\Gamma

$$

里的 hypothesis 与

$$
g

$$

中的 syntactic/semantic pattern 同时决定：

* 哪个 tactic 合适；
* 当前离 proof 还有多远。

所以共享：

$$
h=\operatorname{Transformer}_\omega(s)

$$

然后：

$$
\pi=\pi_\theta(h)

$$

$$
V=V_\phi(h)

$$

是很自然的 multi-task learning。

---

# 35. 但 shared backbone 会产生 gradient interference

总 loss：

$$
L=
\lambda_\pi L_\pi+\lambda_VL_V.

$$

共享参数 \(\omega\) 的梯度：

$$
\nabla_\omega L
=
\lambda_\pi\nabla_\omega L_\pi
+
\lambda_V\nabla_\omega L_V.

$$

可能出现：

$$
\nabla_\omega L_\pi

$$

和：

$$
\nabla_\omega L_V

$$

方向冲突。

例如：

$$
\left\langle
\nabla_\omega L_\pi,
\nabla_\omega L_V
\right\rangle
<0.

$$

这就是典型 multi-task interference。

所以：

$$
\lambda_\pi,\lambda_V

$$

以及 optimizer design 很重要。

---

# 36. GPU batch 化

CPU 端可能同时得到：

$$
s_1,\ldots,s_B.

$$

于是 GPU 不应该：

$$
\text{one state}\rightarrow\text{one kernel launch}.

$$

而应该：

$$
X=
[\operatorname{Enc}(s_1),\ldots,\operatorname{Enc}(s_B)]

$$

一起 forward：

$$
F_\Theta(X).

$$

得到：

$$
\{(\pi_i,V_i)\}_{i=1}^B.

$$

这会显著提高：

$$
\text{GPU utilization}.

$$

因此 CPU/GPU 通信设计本身是 AlphaProof-like system 的性能瓶颈之一。

---

# 37. 所以真正的 runtime architecture 是异步的

理想结构：

```text
CPU search workers
      │
      ├── state batch ──────────► GPU inference queue
      │                              │
      │                              ▼
      │                         Transformer
      │                              │
      │                    ┌─────────┴────────┐
      │                    ▼                  ▼
      │                 Policy             Value
      │                    │                  │
      ◄────────────────────┴──────────────────┘
      │
      ▼
Lean execution
      │
      ▼
MCTS update
```

然后另一条异步 pipeline：

```text
Search trajectories
        │
        ▼
Replay / dataset buffer
        │
        ▼
GPU training
        │
        ▼
new parameters Θ'
        │
        ▼
Inference workers
```

这意味着实际上 GPU 端有两个不同 workload：

$$
\boxed{\text{inference}}

$$

以及

$$
\boxed{\text{training}}

$$

而不是一个统一 workload。

---

# 38. TTT 时最危险的问题：参数版本一致性

假设：

CPU worker 1 使用：

$$
\Theta_0

$$

CPU worker 2 也使用：

$$
\Theta_0.

$$

突然 GPU 更新成：

$$
\Theta_1.

$$

那么 worker 3 使用：

$$
\Theta_1.

$$

此时同一棵 search tree 里的不同节点可能来自：

$$
\Theta_0,\Theta_1.

$$

于是树的 prior/value 不是来自同一个 model。

这叫：

$$
\boxed{\text{model staleness}}

$$

---

# 39. 因此 TTT + MCTS 要决定“何时切换模型”

有两种典型设计。

## Synchronous update

整轮：

$$
\Theta_k

$$

固定。

所有 MCTS 完成：

$$
D_k.

$$

然后：

$$
\Theta_{k+1}.

$$

重新开始下一轮。

这样最干净：

$$
\boxed{
\text{one search epoch}\leftrightarrow
\text{one model version}
}

$$

---

## Asynchronous update

不同 worker 可以使用：

$$
\Theta_k,\Theta_{k+1},\Theta_{k+2}.

$$

吞吐量高，但理论分析更复杂。

因此：

$$
\text{freshness}
\leftrightarrow
\text{throughput}

$$

产生 tradeoff。

---

# 40. 对 theorem proving，TTT 可以非常自然地做成“局部专家化”

假设当前 theorem 属于：

$$
\text{geometry}

$$

但 backbone 训练数据主要是：

$$
\text{number theory}.

$$

第一次搜索可能很差：

$$
\pi_{\Theta_0}.

$$

经过 theorem-local search：

$$
D_0

$$

发现大量 geometry-specific patterns。

然后：

$$
\Theta_1
=
\operatorname{Update}(\Theta_0,D_0).

$$

于是：

$$
\pi_{\Theta_1}

$$

对当前 theorem family 更适配。

所以 TTT 可以被理解为：

$$
\boxed{
\text{global generalist}
\rightarrow
\text{local theorem specialist}
}

$$

---

# 41. 但是不能让 TTT 永久污染全局模型

这是 production system 必须解决的问题。

假设测试 theorem A 导致：

$$
\Theta_A

$$

适配得非常好。

但之后 theorem B 使用：

$$
\Theta_A

$$

可能反而变差。

因此常见设计是：

$$
\Theta_{\mathrm{base}}

$$

保持 frozen。

对于 theorem \(P\)：

$$
\Theta_P
=
\Theta_{\mathrm{base}}+\Delta\Theta_P.

$$

TTT 只更新：

$$
\Delta\Theta_P.

$$

证明完成后：

$$
\Delta\Theta_P

$$

丢弃。

于是：

$$
\boxed{
\text{test-time adaptation is ephemeral}
}

$$

---

# 42. 更进一步：只更新很小一部分参数

例如：

$$
\Theta
=
(\Theta_{\mathrm{backbone}},\Theta_{\mathrm{adapter}})

$$

固定：

$$
\Theta_{\mathrm{backbone}}

$$

只优化：

$$
\Theta_{\mathrm{adapter}}.

$$

则：

$$
\Delta\Theta

$$

很小。

这样：

* TTT 快；
* 显存低；
* 不容易 catastrophic forgetting；
* 多 theorem 可以维护各自 adapter。

这是非常自然的系统设计方向。

---

# 43. TTT 的停止条件

不能无限更新。

定义：

$$
R_k=\text{search success rate at iteration }k.

$$

如果：

$$
R_{k+1}-R_k<\epsilon

$$

持续若干轮，就停止。

也可以看：

$$
\Delta L_{\mathrm{TTT}}

$$

或者：

$$
\Delta V_{\mathrm{root}}

$$

或更直接：

$$
\boxed{
\text{proof found}
}

$$

立刻停止。

---

# 44. TTT 最理想的闭环

完整形式：

$$
\Theta_0

$$

↓

$$
\text{MCTS}_{\Theta_0}

$$

↓

$$
D_0

$$

↓

$$
\text{TTT update}

$$

↓

$$
\Theta_1

$$

↓

$$
\text{MCTS}_{\Theta_1}

$$

↓

$$
D_1

$$

↓

$$
\text{TTT update}

$$

↓

$$
\Theta_2

$$

↓

$$
\cdots

$$

↓

$$
\boxed{\text{Lean-verified proof}}

$$

这可以看作：

$$
\boxed{
\text{Search-Induced Test-Time Learning}
}

$$

---

# 45. CPU/GPU 的最终数学分工

现在把两侧合在一起。

## CPU 定义真实世界

$$
T:S\times A\rightharpoonup S

$$

并维护：

$$
\mathcal T_{\mathrm{MCTS}}.

$$

---

## GPU 学习 heuristic

$$
\pi_\theta(a|s)

$$

和：

$$
V_\phi(s).

$$

---

## MCTS 使用 heuristic

$$
U(s,a)
=
Q(s,a)
+
cP(s,a)
\frac{\sqrt{N(s)}}{1+N(s,a)}.

$$

---

## Search 生成训练信号

$$
D=
\mathcal S(T,\pi_\theta,V_\phi).

$$

---

## GPU 更新

$$
\Theta'
=
\Theta
-
\eta
\nabla_\Theta
L(D;\Theta).

$$

---

## TTT 重复这个过程

$$
\boxed{
\Theta_{k+1}
=
\mathcal U
\left(
\Theta_k,
\mathcal S(T,\Theta_k)
\right)
}

$$

---

# 46. 最核心的一层理解

如果把整个系统抽象到最高层，它其实不是：

$$
\boxed{\text{LLM proves theorem}}

$$

而是：

$$
\boxed{
\text{Lean defines the search space}
}

$$

$$
\boxed{
\text{LLM defines a prior over that space}
}

$$

$$
\boxed{
\text{Value head estimates distance/return in that space}
}

$$

$$
\boxed{
\text{MCTS allocates compute in that space}
}

$$

$$
\boxed{
\text{TTT changes the prior and value model using evidence discovered in that space}
}

$$

因此：

$$
\boxed{
\text{formal environment}
\rightarrow
\text{search}
\rightarrow
\text{data}
\rightarrow
\text{learning}
\rightarrow
\text{better search}
}

$$

才是整个 architecture 的真正核心。

---

# 47. 一个最简洁、但严格的总公式

最终整个 GPU+CPU 系统可以压缩成下面这个闭环：

$$
\boxed{
\begin{aligned}
s
&\xrightarrow{\operatorname{Enc}}
x
\\
&\xrightarrow{f_\Theta}
\bigl(\pi_\theta(\cdot|s),V_\phi(s)\bigr)
\\
&\xrightarrow{\mathrm{MCTS}}
\hat\pi_{\mathrm{search}}
,\;
\hat V_{\mathrm{search}}
\\
&\xrightarrow{\mathrm{Lean}}
D
\\
&\xrightarrow{\nabla_\Theta L}
\Theta'
\end{aligned}}

$$

其中最关键的是：

$$
\boxed{
\text{Lean controls truth;}
\quad
\text{MCTS controls compute;}
\quad
\text{policy/value control search bias;}
\quad
\text{TTT adapts the bias at test time.}
}

$$

这四者之间如果边界设计正确，系统就形成了一个非常强的 **verified neuro-symbolic search loop**。
