# 涌现工具使用与"实验 → 规律 → 定理"（emergent-tool-use）

> 论题：V2（Reap.Agent = MCTS × policy/value/TTT × Eff × Tower）能否涌现——
> ①工具使用（计算实验）能力；②从实验数据中提炼规律；③把规律提升为数学定理
> （或在不可提升时输出**带证据分数的未证命题**）。
> 本目录是该论题的**详细规格**：形式框架、涌现机制、Δ→Π 桥梁、指标与实现接入。

| 文档 | 内容 |
|---|---|
| [00-formal-framework.md](00-formal-framework.md) | 对象定义、算子链 $\mathrm{Chain}$、$\mathrm{MetaGoal}$、奖励锚定 |
| [01-emergence-mechanism.md](01-emergence-mechanism.md) | Claim 1（间接激励）与塔奖赏梯度；涌现的可收敛条件 |
| [02-delta-pi-bridge.md](02-delta-pi-bridge.md) | Claim 2（Δ→Π 桥与 $\mathcal{F}_k$ 安全类）；Claim 3（可判定性边界与未证命题输出） |
| [03-metrics-implementation.md](03-metrics-implementation.md) | 指标 $\lambda,\sigma,\Delta\tau_g,\mathrm{score}$；`mine.py` 实现规格；smoke 断言；与 v2 代码树接入点 |
