# 01. Eff 通道（Verifier-Grounded Tool Use）与效应系统

> 目标：把"利用外部世界知识"作为**类型化、可追溯、不奖励**的效应，并满足 8-v2 §1.1-1.3 的
> 垂直接地（verifier-grounded）要求。

## 1.1 效应原语注册表

定义效应签名（世界层原语）：

$$\mathrm{EffSpec} := (\sigma_{\mathrm{in}},\ \sigma_{\mathrm{out}},\ \mathrm{pre}:\mathrm{St}\to \mathrm{Bool},\ \mathrm{post}:\mathrm{Obs}\to \mathrm{Bool})$$

即：$\mathrm{run\_effect} : \mathrm{EffSpec} \to \mathrm{Eff}\ (\mathrm{Obs} \times \mathrm{Trace})$，其中

- $\mathrm{Obs}$ = 观测值（数值/模式/检索候选），**只进特征，不进奖励**；
- $\mathrm{Trace}$ = 可追索性记录（调用栈/参数/耗时，供审计与 B 指标）。

**$\mathrm{Eff}$ 单子的语义**：效应执行是纯函数式副作用（$s \mapsto s'$），
$$\mathrm{mono}\{\mathrm{Eff}\} : s \xrightarrow{\tau} s'[H_{\mathrm{obs}}\cup\{o\}] \quad \text{(状态单调扩展)}$$

## 1.2 工具接地定理（Verifier-Grounded Tool Use）

> **定理（Indirect Supervision only）**。对任意效应 $\tau\in\mathcal{T}$，设事实 $\mathrm{Fact}_\tau$ 可被一个
> 独立决定程序裁决（如：数值试验可复算），则训练信号 $\nabla_\theta \mathcal{L}$ 中 $\tau$ 的偏导
> $$\nabla_\theta \mathcal{R}\cdot \nabla_\theta \pi(\tau) = 0 \quad (\text{除非 } \tau \ \text{链末端抵达终局})$$
> 即：**工具质量只通过其选择如何影响形式搜索的成功率而被改进**——与 8-v2 §1.1 的"间接监督"一致。

## 1.3 特征化（不进奖励进状态）

对于数值实验输出 $x_{\mathrm{exp}}$，定义嵌入
$$\phi(s):= \mathrm{enc}\big(\Gamma, L, \mathrm{top-}k\ \mathrm{obs}, d(\Gamma)\big) \in \mathbb{R}^{n}$$
价值网络输入含 $\phi$：$V_\phi(s) = \mathrm{MLP}(\phi(s))$。
因此**工具影响的是 $\mathrm{Existence-of-Solution}$ 估计（可证性状），而非奖励本身**。

## 1.4 与 Lean 的接口（同像性条件）

$\mathrm{run\_effect}$ 的**描述与观测**都以 Lean 字符串/对象表达（$\mathcal{A}\cong\mathcal{O}$），
实现为子进程/FFI 调用的**白名单原语**（不可由 agent 动态注册；满足 $\mathcal{I}_{\mathrm{sep}}$ 的工具侧面）。

## 1.5 可判定范畴（诚实声明）

本 spec 只把效应分为两类：
1. **$\mathrm{DeterministicE}$**：结果被过程验证（数值检验、检索、公式化简）——强接地；
2. **$\mathrm{ExistentialE}$**（如猜测性核配方）：仅在"其结论事后再由终局验证"下给出信号——弱接地。
V2 默认启用第 1 类、抑制第 2 类（防止"实验噪声作为证据"的奖励替换）。

## 1.6 形式规格交付（实现侧要求）

```
Registry (immutable, code-verified):
  effect spec: name, in/out types, pre/post, verifier-bool
  categories: DETERMINISTIC | EXISTENTIAL
Runtime contract:
  run_effect(spec, args) -> (obs, trace)
  obs must satisfy  spec.post  (否则抛 infra_error，不计入任何 reward)
```
