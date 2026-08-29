# V2 spec：Reap.Agent — 数学驱动的元层证明智能体（reap-mcts-lean-v2）

> 依据：`explain/7-reap-v1-v2.md`（V2 定义）与 `explain/8-v2-math-drive.md`（数学驱动训练主纲）。
> 定位：**同一台机器的更高档位**——V2 不是"更强的 V1"，而是把问题类从"证明给定命题"
> 扩张到"在可计算效应世界中执行任意元级任务"，并保持"数学终局裁判"这一奖励锚点。

## 0. 形式化总览

**对象**（层叠关系）：$\mathrm{V2} = \mathrm{V1} \uplus \{\mathrm{Eff},\ \mathrm{MetaState},\ \mathrm{MetaActions},\ \mathrm{Tower}\}$，
即 V2 在 V1 坐标系（验证器/MCTS/RTTT）**之上**扩展四个新语义组件，不改动 V1 核心算法。

**四不变量（red lines，必须为定理而非约定）**：

| 记号 | 不变量 | 形式 |
|---|---|---|
| $\mathcal{I}_{\mathrm{sep}}$ | 自指切开 | learner 与 evaluator 的**语法层级严格分离**：agent 生成代码不可触碰学习器自身（§5） |
| $\mathcal{I}_{\mathrm{probe}}$ | 证明 ≠ 计算 | 奖励函数对时间效应封闭：$\mathcal{R} = \mathbb{1}\{\mathrm{kernel}\}$（§2/§5） |
| $\mathcal{I}_{\mathrm{tower}}$ | 塔上升验证门 | 仅当 $\mathrm{gate}(t)=\mathrm{ok}$（kernel 验证）时 $L_{t+1}=L_t\cup\{t\}$ 才被允许（§4） |
| $\mathcal{I}_{\mathrm{type}}$ | 动作合法性 | 一切元动作先经过 Lean 类型检查；类型检查通过 ⟺ 动作合法（§3） |

## 1. 与 V1 的层叠结构

$$
\mathrm{V1} := \langle \text{验证器 } \mathrm{Ver}, \text{ 搜索 } \mathrm{MCTS}, \text{ 协议 } \mathrm{Gen}, \text{ RTTT},\ \text{BatchSolver} \rangle
$$

$$
\mathrm{V2} := \mathrm{V1} \oplus \langle \mathrm{Eff}, \mathrm{MetaState}, \mathrm{MetaActions}, \mathrm{Tower} \rangle
$$

共享面（复用零改动）：`Step.lean`（$\mathrm{Ver}$）、`TreeSearch/*`（$\mathrm{MCTS}$）、`Generator.lean`（$\mathrm{Gen}$）、RTTT 协议、`v1_run.py`/`v1_sink.py`。
V2 唯一替换的是**目标谓词与动作语义**：目标谓词从"$\Gamma \vdash Q$"泛化为"$\mathrm{MetaGoal}$"（§3 定义）。

## 2. 奖励锚定（Reward Anchoring）

$$\mathcal{R}_{\mathrm{V2}}(s,a) := \mathbb{1}\{\mathrm{checkProof}_{\mathrm{Lean}}(s,a) = \mathrm{ok}\} \lor \mathbb{1}\{\mathrm{refutation}(s,a)\ \text{被独立确认}\}$$

**工具值不产生奖励定理**（v2-math-drive §1.1 的形式化）：

> **定理（Reward Independence of Tools）**。设效应算子集 $\mathcal{T}$，任何 $\tau\in\mathcal{T}$ 的执行仅改变状态
> $s\mapsto s'$（$s'$ 含观测特征），而
> $$\frac{\partial \mathcal{R}}{\partial s'}=0 \quad \text{if}\quad \mathrm{s}' \text{ 不满足证明/反证条件}$$
> 则对任何由 $\mathcal{T}$ 组成的长链 $\pi$，$\mathbb{E}[\nabla_\theta\mathcal{R}\mid \pi]$ 完全由**形式终局**决定；
> 因此工具使用仅具**间接监督**（经策略/价值梯度沿推理链传播）。
> *证明（sketch）*：$\mathcal{R}$ 定义为终局指示函数；梯度 $\nabla_\theta\mathcal{R} = \nabla_\theta\mathbb{1}\{\mathrm{gates}\}$ 不含工具变量的偏导 ⇒ 工具的任何"执行好坏"不进入奖励面。

**方差优势定理**（8-v2-math-drive §2.4 的严格版）：

> **定理（Signal Variance Ordering）**。设数学终局验证器 $V_m$ 与代码类判据 $V_c$，记
> $\mathbb{E}[\cdot]$ 为服从同一策略分布的期望；则
> $$\mathrm{Var}\!\big[\hat R_m\big] \le \mathrm{Var}\!\big[\hat R_c\big]$$
> 只要 $V_m$ 是确定性（kernel 接受/拒绝，噪声 $\varepsilon_m=0$）而 $V_c$ 具有测试/集成噪声 $\varepsilon_c>0$。
> 推论：在数学任务上，策略梯度估计量（REINFORCE 型）的方差下界（Rao–Cramér）更紧 ⇒ 对"使用工具"类长链决策的更新更一致。

## 3. 状态与动作空间（MetaState / MetaActions）

### 3.1 元状态

$$s = (\Gamma,\ L,\ H_{\mathrm{obs}}),\qquad H_{\mathrm{obs}} = \{(o_t,\mathrm{meta}_t)\}_{t<T}$$

- $\Gamma$：Lean proof context（与 V1 一致）；
- $L$：库（verified declarations 的聚集，见 §4）；
- $H_{\mathrm{obs}}$：观测历史（数值实验、检索结果、模式挖掘输出）

**同像性**（7-reap-v1-v2 §3）：$\mathcal{A}\cong \mathcal{O}$——动作以 Lean 对象序列化（定理语句 = 动作描述；观测 = Lean 文本结果），保证 $\pi_\theta$ 在单一语言空间上决策。

### 3.2 动作空间

$$
\mathcal{A}_{\mathrm{V2}} = \{\mathrm{fill-hole},\ \mathrm{patch-Expr},\ \mathrm{addDecl},\ \mathrm{run-effect}\}
$$

- $\mathrm{fill-hole}(h,\tau)$：在洞 $h$ 处引入项 $\tau$（类型检查通过即合法）；
- $\mathrm{patch-Expr}(e,\delta)$：符号替换（抽象/特化/对偶化——"课程变体"的机器内表示）；
- $\mathrm{addDecl}(t)$：登记引理（**仅门控通过后进入 $L$**，见 §4）；
- $\mathrm{run-effect}(\sigma)$：效应执行（见 §Eff 通道）

**零非法率定理**：

> **定理（Action Legality via Typechecking）**。定义动作合法性谓词
> $$\mathrm{legal}(a,s) := [\mathrm{typecheck}_{\mathrm{Lean}}(\tau_a \mid s) = \mathrm{accept}]$$
> 若 $\mathcal{A}_{\mathrm{V2}}$ 仅含良构造动作元组，且 $\mathrm{typecheck}$ 完备（Lean 决策程序），则
> $$\mathbb{P}_{a\sim\pi_\theta}[\mathrm{legal}(a,s)] = 1$$
> 对一切 $\theta,s$。自由文本代理的非法率 $\ge \varepsilon>0$；V2 的零非法率是**类型系统给出的构造保证**。

## 4. 塔上升（Tower / Growing Library）

$$L_0 := \emptyset, \qquad L_{t+1} := L_t \cup \{t\} \iff \mathrm{gate}(t) = \mathrm{ok}, \qquad \mathrm{gate} := \mathrm{checkProof}_{\mathrm{Lean}}$$

**塔上升 ⇔ 库增长 命题**：

> **命题（Tower $\cong$ Growth）**。$\mathrm{addDecl}$ 的成功执行 ⟺ 语言"塔"上升一步；定义抽象深度：
> $$d(t) := \#\{d \in L_t : d \text{ 出现于 proof}(t)\}$$
> 则 $d$ 单调不减：$d(t_{k+1}) \ge d(t_k)$（只要 $t_{k}$ 在库中并被后续引用）。于是"智能增长"可由
> $$\tau_g := \max_{t\in L_g} d(t)$$ 无歧义度量——**这就是技能涌现的可测形态**（对应 8-v2 指标 C）。

**验证门语义**：$\mathrm{gate}$ 是唯一能改变 $L$ 的热点；$\mathrm{gate}$ 本身不可被学习器改写（$\mathcal{I}_{\mathrm{sep}}$），
因此不存在"把坏证明塞进塔"的漏洞：$\forall t: \neg\mathrm{gate}(t) \implies t \notin L_{t+1}$。

## 5. 语义与验收指标

### 5.1 不变量形式化

- **自指切开**（$\mathcal{I}_{\mathrm{sep}}$）：设 $\mathrm{Learner}$ 为策略/价值/$L$ 的优化器，$\mathrm{Evaluator}$ 为 $\mathrm{Lean}+\mathrm{Recoder}$ 的集合。
  $$\text{不允许：agent 生成写 } \mathrm{Learner} \text{ 状态；不允许：agent 生成改写 } \mathrm{gate}$$
  （训练器只经 harness（V1 的 Step checker）固化——等价于 Δ 谓词"evaluator 域在语法层级上不可达 learner 域"）
- **证明 ≠ 计算**（$\mathcal{I}_{\mathrm{probe}}$）：$\mathcal{R}$ 闭包于 $\mathrm{prove/refute}$ 两个通道（§2 定理）；数值/实验只进特征。
- **塔上升验证门**（$\mathcal{I}_{\mathrm{tower}}$）：§4 布尔门不可旁路。

### 5.2 验收指标（量化 8-v2 §2.3）

| 指标 | 定义 | 目标 |
|---|---|---|
| A. 迁移 | $\mathrm{transfer} = \big(\mathrm{solve@}B\big|_{\mathrm{math}} \mapsto \mathrm{task@}B\big|_{\mathrm{agent}}\big)$ 的跨域保持率 | $\ge 0.5$ |
| B. 验证接地率 | $r_{\mathrm{vg}}=\frac{\#\{\text{动作：来自验证反馈}\}}{\#\{\text{全部动作}\}}$ | $\ge 0.8$ |
| C. 抽象深度 | $\tau_g$（§4） | 单调不减 |
| D. 奖励-路径比 | $\rho = \frac{\#\{\text{终局奖励}\}}{\#\{\text{动作数}\}}$，入参 ${s \to a \to s'}$ 链的长尾比 | 至少不减 |

### 5.3 与 V1 的可测分界

$$\mathrm{V1} \text{ 验收} = \{\text{solve@}B,\ \text{verdict-dist}\}; \qquad \mathrm{V2} \text{ 验收} = \{\mathrm{A,B,C,D}(\text{见表})\}$$

**层叠性判据**：V2 必须包含 V1 全部 gate（回归）；V2 新指标只作用于效应相关的分子项（非回归）。
