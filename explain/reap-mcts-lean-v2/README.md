# V2 spec：Reap.Agent — 数学驱动的元层证明智能体（reap-mcts-lean-v2）

**一句话**：V2 = V1 之上换档为**元级动作 + 效应世界 + 塔上升**，奖励恒定锚定于形式终局
（kernel 证明 / 独立确认反例）；agentic 技能作为"数学推理链的必要组件"被间接学得。

| 文档 | 内容 |
|---|---|
| [00-overview.md](00-overview.md) | 对象与四红线不变量（自指切开/证明≠计算/验证门/动作合法=类型检查）、与 V1 层叠、奖励锚定定理、方差排序定理 |
| [01-eff-channel.md](01-eff-channel.md) | Eff 通道：效应签名 `run_effect: EffSpec → Eff(Obs,Trace)`、间接监督定理、特征化、可判定范畴（DeterministicE / ExistentialE） |
| [02-action-space.md](02-action-space.md) | 元动作空间（fillhole/patch/adddecl/effect）、动作合法⟺类型检查（零非法率定理）、目标泛化 $\mathrm{MetaGoal}$、同像性 |
| [03-tower.md](03-tower.md) | 塔上升：$L_{t+1}=L_t\cup\{t\}\iff \mathrm{gate}=\mathrm{ok}$；抽象深度 $\delta(t,L)$；塔高单调命题；难度驱动课程；验证门防穿 |
| [04-training-and-metrics.md](04-training-and-metrics.md) | 目标函数（$\mathcal{L}_{\mathrm{RL}}+\lambda_v\mathcal{L}_V$）、A–D 指标严格定义、回归、KL/网络隔离 |

**依据原始文档**：[explain/7-reap-v1-v2.md](../7-reap-v1-v2.md)、[explain/8-v2-math-drive.md](../8-v2-math-drive.md)。
