# Miner 是什么：可训练的规律挖掘器（其本身就是 reap-MCTS 的一个实例）

> 两部分合成：①"挖掘能力应可训练涌现，而非单一确定性方法"（论证）；
> ②"miner = reap-policy+value+TTT 在规律空间的重载（共享 backbone 双任务联合）"（设计）。
> 由此得到"what-is-the-miner"的完整答案：**miner = 与证明同轴的、可训练的、数学诚实受约束的第二个 MCTS 档位**。

| 文档 | 内容 |
|---|---|
| [00-why-not-deterministic.md](00-why-not-deterministic.md) | 描述复杂度论证（Kolmogorov 不可实现）、可训练挖掘器形式化、监督+RL 目标、学习-奖励分离定理 |
| [01-miner-as-reap-instance.md](01-miner-as-reap-instance.md) | 与 Reap 组件的同构映射表、共享 backbone 双任务联合训练、正反馈回路、双防、Claim 3 极限 |
| [02-implementation-slice.md](02-implementation-slice.md) | 下一切片规格：动作/特征/事件协议/验证器/指标（P@k, RefuteRecall, λ）与代码增量 |
