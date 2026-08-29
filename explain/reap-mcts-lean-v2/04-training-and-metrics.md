# 04. 训练目标、指标与验收（A–D 的严格定义）

## 4.1 目标函数（ref. 8-v2 §2.0）

$$\mathcal{L}_{\theta,\phi} =
\underbrace{\mathcal{L}_{\mathrm{RL}}\big(\mathcal{R}_{\mathrm{V2}}\big)}_{\text{策略：自然终局}}
+ \lambda_v\ \underbrace{\mathcal{L}_{V}\big(\mathrm{provability-estimate};\ \phi(s)\big)}_{\text{价值：含工具特征}}$$

其中
$$\mathcal{R}_{\mathrm{V2}}(s,a) := \mathbb{1}\{\mathrm{kernel}(s,a)=\mathrm{ok}\} \lor \mathbb{1}\{\mathrm{refutationVerified}(s,a)\}$$

工具梯度：仅经 $V$(价值) 与策略链（$a$ 链的选择）间接回传（定理 1.2）。

## 4.2 指标定义与验收线

| 记号 | 定义 | 验收线 | 备注 |
|---|---|---|---|
| A. 迁移率 | $\mathrm{transfer} = \frac{\mathrm{task@}B|_{\mathrm{agent}}}{\mathrm{solve@}B|_{\mathrm{math}}}$ | $\ge 0.5$ | 跨 API/编码域保持率（8-v2 §1.3：接口同构要求） |
| B. 接地率 | $r_{\mathrm{vg}} = \frac{\#\mathrm{actions\ grounded\ by\ verification}}{\#\mathrm{actions}}$ | $\ge 0.8$ | v-grounded tool use 的实证 |
| C. 抽象深度 | $\tau_g$（§3.1） | 单调不减 | 技能涌现度量 |
| D. 奖励-路径比 | $\rho = \frac{\#\mathrm{rewards}}{\#\mathrm{actions}}$ | 不降且 $\mathrm{Var}[\rho]$ 收窄 | 长链奖励方差（8-v2 §2.4） |

## 4.3 回归要求

V2 的实现必须**先通过 V1 验收**（00-overview 0.3：solve@B、verdict-dist、kernel-only success），
即 $\mathrm{V2} \supseteq \mathrm{V1}$ 若成立；V2 新增的验收仅对"效应相关分子"计分，不并入 V1 指标。

## 4.4 停止条件与安全（递归框架）

- 每代（$g$）后运行 $\mathrm{KL}(\pi_g\|\pi_{g-1})\le\kappa$；
- 若 $\mathrm{transfer}<\theta_A$（指标 A 不达标）→ 回退到纯数学训练（可判定性修复）。

## 4.5 泄漏与隔离（与 V1/官方的联邦约束）

- 教师、eval、库 $L$ 三者命名空间隔离（不允许 agent 在 eval 期间改 $L$ 或以 eval 目标作 teacher 输入）；
- V2 的不变量（§00 的四红线）均以**代码内强制**（不是约定）。
