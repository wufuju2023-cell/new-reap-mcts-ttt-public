# 00. 形式框架

## 0.1 对象

V2 展开对象为算子链

$$
\mathrm{Chain} := \mathrm{Eff} \circ \mathrm{Mine} \circ \mathrm{Ver} \circ \mathrm{Prove}:
\mathcal{O} \to \mathcal{T}
$$

- $\mathrm{Eff}$（实验/计算）：$\mathrm{EffSpec}\to \mathrm{Eff}(\mathrm{Obs}\times\mathrm{Trace})$，观测 $o\in\mathcal{O}$，仅入状态特征，不入奖励；
- $\mathrm{Mine}$（规律提炼）：$O\subseteq\mathcal{O}\mapsto \mathrm{Candidates}$（猜测簇 $c$）；
- $\mathrm{Ver}$（验证/反例）：$\mathrm{Candidates}\times(\text{搜索空间})\to\{\mathrm{accept},\mathrm{reject},\mathrm{unknown}\}$；
- $\mathrm{Prove}$（形式化）：$\mathrm{Ver}$ 接受者 → Lean kernel 证明脚本。

## 0.2 目标谓词

$$
\mathrm{MetaGoal}(o): \quad \exists c\in\mathrm{Candidates}: \mathrm{kernel}(\mathrm{Prove}(c))=\mathrm{ok} \ \lor\ \mathrm{refutation}(c)\ \text{独立确认}
$$

奖励锚定（与 V2 全局一致，$\mathcal{I}_{\mathrm{probe}}$）：

$$
\mathcal{R}(s,a) := \mathbb{1}\{\mathrm{kernel}(s',\mathrm{script})=\mathrm{ok}\} \lor \mathbb{1}\{\mathrm{refutationVerified}(s,a)\}
$$

## 0.3 状态与塔（沿用 spec 03）

$$
s = (\Gamma, L, H_{\mathrm{obs}}),\qquad L_{t+1} = L_t \cup \{t\} \iff \mathrm{gate}(t)=\mathrm{ok}
$$

塔指标：$\delta(t,L)=\#\{d\in L: d\in \mathrm{proof}(t)\}$，$\tau_g=\max_{t\in L_g}\delta(t,L_g)$（单调）。

## 0.4 两个分类的专家事实

1. **涌现的主体是策略 λ 分布**：$\pi_\theta:\mathcal{S}\to\Delta(\mathcal{A})$，其中 $\mathcal{A}\supseteq\{\mathrm{effect},\mathrm{adddecl},\mathrm{patch},\mathrm{fillhole}\}$；
2. **规律可提升的类**：$\mathcal{F}_k$（有限决定性检验类）与非 $\mathcal{F}_k$ 类是判断"能否给出定理"的分界（见 02）。
