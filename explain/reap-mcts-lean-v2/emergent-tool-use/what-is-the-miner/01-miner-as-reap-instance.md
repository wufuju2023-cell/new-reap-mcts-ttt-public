# 01. Miner = reap-MCTS 的"规律档"实例（同机重载）

## 1.1 同构映射

| Reap 组件 | 证明档位 | 规律档位 ($\mathrm{Mine}$) |
|---|---|---|
| 动作 $\mathcal{A}$ | 证明动作（tactic/填充） | $\mathrm{fit}$（参数族选择/插值）$\cdot\mathrm{select}$（O 子集/实验设计）$\cdot\mathrm{refute}$（反例搜索） |
| 策略 $\pi_\theta$ | $a\mid s$ | $(\mathrm{candidate},\mathrm{design})\mid s_m$ |
| 价值 $V_\phi$ | 可证性 | **可提升性** $\mathbb{P}[c\in\mathcal{F}_k\,\vert\,O]$ |
| MCTS | 证明树 | 规律-实验-塔树 |
| TTT | verdict→梯度步 | gate/refute verdict→梯度步（同一事件协议） |
| 验证器 | $\mathrm{checkProof}$ | $\mathrm{gate}\circ(\mathrm{F_k}\text{-判定})\circ\mathrm{Refute}$ |
| 塔奖励 | 引理入塔 | 已验证候选入塔（$\Delta\tau_g$） |

**命题（类型同构）**．引擎（TreeSearch/State/RTTT/sink）在两类任务间是类型同构：
仅替换 $\mathcal{A}$、判定谓词与状态特征 $H_{\mathrm{obs}}$（统计矩/符号特征）。
⇒ miner 无需任何新引擎，即"同一台机器换个档位"。

## 1.2 共享 backbone 双任务联合

$$h_\theta: 7\mathrm{B}\ \mathrm{backbone},\qquad \pi=(\pi_p,\pi_m),\quad V_p=\mathrm{MLP}_p(h_\theta(s_p)),\quad V_m=\mathrm{MLP}_m(h_\theta(s_m))$$

$$
\mathcal{L}_{\mathrm{joint}} := \alpha_g\,\mathcal{L}_{\mathrm{prove}}(\theta,\phi_p) + (1-\alpha_g)\,\mathcal{L}_{\mathrm{mine}}(\theta,\phi_m) + \beta\,\mathrm{KL}[\pi\,\|\,\pi_{\mathrm{ref}}]

$$

课程：$\alpha_g$ 随代际递减（先证明、后挖掘渗透）。

## 1.3 正反馈回路

$$
\mathrm{miner}(O)\Rightarrow c\in\mathcal{F}_k \Rightarrow L\uparrow \Rightarrow \mathrm{prove}(t\mid L)\ \text{步数}\downarrow
\Rightarrow \mathcal{L}_{\mathrm{prove}}\downarrow \Rightarrow (\text{教师}) \text{新课程} \Rightarrow \ldots

$$

对应指标 TowerDelta（§5）因果链的正向版本：$\rho(\Delta\tau_g,\mathbb{1}[c\ \mathrm{in\ tower}])>0$。

## 1.4 双防（与全局四红线的挖掘层落实）

1. **判定层不动**：gate/Refute/F_k 判定不训练、不随梯度变化（学习者仅作用于候选生成与价值估计）；
2. **F_c 不入梯度**：OpenConjectures/score 只写文件，不参与任何训练信号。

## 1.5 极限（与 Claim 3 一致）

即使 $M^\ast$ 的命中率显著提升，$\mathcal{F}_k$ 边界不动（可判定性边界未被扩大）：
未证命题输出与 $\mathrm{score}$ 永久保留——这是"涌现"与"计算极限"的分界。
