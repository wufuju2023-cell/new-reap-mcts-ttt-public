# 02. Δ→Π 桥：实验证据何时成为数学定理

## 2.1 归纳不完全性（为何不能自动提升）

对任意有限观测集 $O\subset\mathbb{N}^d$、$\varphi$，存在 $\varphi'$ 与 $O$ 一致但 $\exists x_0>|O|:\neg\varphi'(x_0)$。
故$\forall$-型命题的**有限证据不是证明**；除非把命题限制在如下"决定性类"。

## 2.2 $\mathcal{F}_k$ 有限决定性检验类

**定义（$\mathcal{F}_k$）**。$P$ 属于 $\mathcal{F}_k$，若存在决定程序 $\mathrm{check}$ 与常数 $N_k$，使

$$
P \ \text{成立} \iff \mathrm{check}\big(P;\ o_1,\ldots,o_{N_k}\big) = \mathrm{accept}

$$

**Claim 2（Δ→Π 桥）**．若 $P\in\mathcal{F}_k$，则有限实验证据 **可提升为可构造证明**：
给定 $O$（$|O|\ge N_k$），存在 Lean 脚本 $\mathrm{script}(O)$，且

$$
\mathrm{kernel}\big(\mathrm{script}(O)\big)=\mathrm{ok} \iff \mathrm{check}(P;O)=\mathrm{accept}

$$

**安全类目录**（本 V2 采用的 4 类）：

| 类 | $N_k$ | 支架证明 |
|---|---|---|
| 多项式/有理函数恒等 | $N_k=\deg P+1$ | 插值/系数比较定理（范德蒙德非奇异 ⇒ 系数唯一） |
| 有限群/环恒等 | $N_k=|G|^{O(1)}$ | 有限模型论（BCI/群表模型检查） |
| 线性递推/母函数闭式 | 前 $k$ 项（$k=\text{阶数}+C$） | 线性代数 + 唯一性（特征多项式） |
| 组合恒等式/双计数 | $N_k$ 由分解数决定 | 双计数消元/有限对称化 |

## 2.3 $\mathrm{Mine}\to\mathrm{Ver}\to\mathrm{Prove}$ 的三态流水线

$$
\mathrm{Mine}(O) \to \mathrm{Candidates}
\quad \xrightarrow{\mathrm{Refute}} \quad \mathrm{Survivors}
\quad \xrightarrow{\mathcal{F}_k\text{-判定}} \quad
\begin{cases}
\mathrm{Prove} \to \text{Theorem} & (\text{安全类})\\
\mathrm{OpenConjecture} + \mathrm{score} & (\text{非安全类})
\end{cases}

$$

其中 $\mathrm{Refute}(c; m)$：构造性反例搜索器，在 $|O|+1\sim|O|+m$ 穷举/随机搜索
（有限域化 + 相邻不动点 + 对称约化）。

## 2.4 Claim 3（半可判定性边界与诚实输出）

**Claim 3（不可自动化的类）**．存在闭类 $\mathcal{F}^c$（如包含 $\exp$、模算术未分解类、$\mathbb{Z}$ 上二次型三元问题），其
"$\mathrm{survive}\Rightarrow\mathrm{theorem}$" 判定等价于**半可判定集**；对这类命题，系统仅应输出：

$$
\mathrm{Output}(c) = \big(\ c,\ \mathrm{score}(c; O)\ \big),\qquad
\mathrm{score}(c;O) := \underbrace{\rho_{\mathrm{feas}}}_{\text{约化覆盖系数}}\cdot\underbrace{\big(1-\hat p_{\mathrm{refute}}\big)}_{\text{反例率估计}}

$$

$$
\hat p_{\mathrm{refute}} = \frac{\#\{\neg\ c\ \text{在 } |O|+1..|O|+m \}}{m}

$$

> 诚实性原则（与 V2 $\mathcal{I}_{\mathrm{sep}}$ 配套）：自动生成定理仅限 $\mathcal{F}_k$；
> $\mathcal{F}^c$ 输出的"未证命题"必须是**证据分数标注**，不允许隐含地当作定理进入塔。

## 2.5 定理输出与塔耦合

$\mathrm{gate}$ 只对**已证明** $t$ 开放（$\mathcal{F}_k$ 类）；未证命题作为"OpenConjectures 清单"另外维护，
在后续难度课程中作为 $\mathrm{MetaGoal}$ 再投入（成环：实验 → 规律 → 命题 → 证明 → 塔）。
