# AlphaProof 原论文对齐与 Reap 推进计划

审计日期：2026-09-05。

这组页面把三件容易混在一起的事情分开：

1. AlphaProof 论文实际报告了什么；
2. 公开 Reap 快照、7B REAL-Prover 实验记录实际证明了什么；
3. 下一轮工作应先补哪一个可验证的缺口。

它不是把 AlphaProof 的论文结果移植到 Reap 的声明，也不是一次新的训练运行。此次审计没有安装、升级、编译或改动 Lean。

## 先读这个结论

- 论文中的 AlphaProof 是 3B encoder-decoder 的联合 policy/value 网络、全证明树 MCTS、海量 auto-formalized curriculum，以及面向目标题的变体课程 RL；不是只在一道题的少数节点做若干梯度步。
- 本地记录能够支持“REAL-Prover 7B 上曾发生过冻结基座的 LoRA + value-head 联合更新，并有 Lean 验证的成功轨迹”。它不能支持“当前公开仓库里已经有可加载、已基准化的训练后 checkpoint”：adapter 和 value-head 张量没有随 Git 保存。
- 当前最紧急的工程问题不是直接扩大训练，而是统一 value 语义和 policy-prior 接口。公开运行代码、公开 wiki 和历史 7B 实验对 value head 的形态与标签含义存在冲突；公开 policy server 也没有把实际 token logprob 交给 Lean 搜索。
- 所谓 TTT 若没有大量、经 Lean 检查且与目标相关的变体课程，以及从搜索回流的已验证 replay，更准确地说是小规模在线适应，不能和论文的 TTRL 等同。

## 阅读顺序

| 页面 | 用途 |
| --- | --- |
| [01 论文基线](01-paper-baseline.md) | 用原文固定术语、算法与数量级 |
| [02 差异地图](02-gap-map.md) | 找出已经确定的偏差、冲突和未知项 |
| [03 7B 训练状态](03-training-status-2026-09-05.md) | 区分历史训练证据、可恢复权重和效果证据 |
| [04 架构与数学下一步](04-architecture-and-math-next.md) | 先修正哪些不变量和接口 |
| [05 训练与 TTRL 规模](05-training-and-ttrl-scale-next.md) | 如何用可承受的阶段接近论文的训练结构 |
| [06 执行顺序与计分卡](06-execution-order-and-scorecard.md) | 以验收门而不是“跑了训练”推进 |
| [07 证据定位表](07-evidence-ledger.md) | 将每个关键结论定位到论文或源码 |

## 证据标记

- **[论文]**：只陈述随附的 Hubert 等人 AlphaProof 论文。文中 AP p. N 是该 PDF 的第 N 页；该文件的 PDF 元数据报告 25 页，因此不以“30 页”的外部显示计数定位。
- **[仓库]**：公开工作树中可阅读的源码或文档。
- **[审计]**：2026-09-05 对给定本地仓库的只读检查。它说明“扫描到什么／没有扫描到什么”，不推断远端或未挂载存储的内容。
- **[建议]**：后续实现门槛，尚未完成。

## 范围和边界

此系列关注 Lean proof search、policy/value 学习、replay、curriculum 与 TTRL。它不声称复现 AlphaProof 的专有数据、基础预训练、TPU 集群或 auto-formalizer；也不把一次已验证证明误写成泛化基准结果。

权重不应提交到本公共仓库。若要恢复历史 7B 训练状态，应从原始受控 artifact store 取回 adapter/value 张量，按 manifest 校验后另行运行；仅有 Git 中的 metadata、hash 与证明回执不足以加载模型。
