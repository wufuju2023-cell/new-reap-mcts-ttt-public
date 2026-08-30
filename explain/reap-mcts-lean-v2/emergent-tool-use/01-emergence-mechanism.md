# 01. 涌现机制（为何工具使用会被学出来）

## 1.1 直接梯度为零（工具无直接奖励）

V2 spec 已给：

$$
\nabla_\theta \mathcal{R}\cdot\nabla_\theta \pi(\tau) = 0 \quad(\text{除非 } \tau\ \text{链末端抵终局})
$$

因此"工具使用"**不会**因"执行得好"被奖励；任何正向涌现必须经由**状态/塔变化**的间接路径。

## 1.2 塔奖赏梯度（二阶激励）

设一次实验 $\tau$ 后，规则挖掘器产出候选 $c$，且 $c$ 经 $\mathrm{gate}$ 入塔（$t_c\in L$）；则该动作的**期望效用增量**为：

$$
\Delta U(\tau) := \mathbb{E}_{\pi}\big[\mathrm{score}(s', L')-\mathrm{score}(s, L) \,\big|\ a=\tau\big]
            \ \propto\ \mathbb{P}\big[c \in \mathcal{F}_k \wedge \mathrm{gate}(c)=\mathrm{ok}\big]
$$

策略梯度项对此的贡献：

$$
\nabla_\theta J = \mathbb{E}\Big[\sum_{t} \gamma^{T-t} \Delta U(\tau_t)\,\nabla_\theta \log\pi_\theta(\tau_t\mid s_t)\Big]
$$

**推论（涌现的收敛条件）**：
1. $\mathbb{P}[\mathrm{Mine}(O)\in \mathcal{F}_k] > 0$（可提炼安全类出现概率非零）——两参数：候选空间校准；
2. $\mathrm{gate}$ 为**确定性布尔**（$\mathcal{I}_{\mathrm{tower}}$）⇒ 效用信号无方差污染（与 8-v2 §2.4 一致）；
3. $\gamma\in(0,1)$ 与塔高度增长兼容：$t_c$ 在后续题中被引用（$d(t)\uparrow$）⇒ 目标 $\Delta U$ 随代际放大 → **"先实验"成为稳定高价值策略**。

**结论（涌现判据）**：工具使用的涌现 **不是自由现象**，而是"实验→$\mathcal{F}_k$ 类规律→塔"这条**有奖上坡路径**的收敛结果；若挖掘器从不产出可证明规律，则 $U(\tau)\approx0$，工具使用退化回零梯度、策略保持随机——**因此实现 mined 的"可证明性校准"是涌现的前提**。

## 1.3 与教师/课程的关系

难度驱动课程（spec 03.2）保证 $\mathrm{Diff}_g\uparrow$ ⇒ 探索工具的需求密度上升；
该密度的提升把 $\Delta U(\tau)$ 分母缩小、分子（$\mathcal{F}_k$ 命中）不变 → 涌现速率 $\varnothing$ 随代际递增（超线性放大）。

## 1.4 因果审计

每轮记录 $(\tau, O, c, \mathrm{gate}, \Delta\tau_g)$；用相关系数检验

$$
\rho(\Delta\tau_g,\ \mathbb{1}[c\ \text{入塔}]) \quad \text{（§5 的 TowerDelta 指标）}
$$

作为"涌现源于塔奖赏而非噪声"的统计证据。
