# AlphaProof V1：原论文对齐与下一步计划

审计日期：2026-09-05。

## 范围先行

本系列只讨论 **V1 的真实代码、真实训练回执和真实服务消费结果**：

- REAL-Prover 7B 的冻结共享 backbone；
- 同一 active policy LoRA 表示上的 categorical value head；
- V1 verified replay / mixed learner / release / recovery 证据；
- 与 AlphaProof 原论文的结构和规模比较。

不把早期 value-head 试验、V2、公开化快照中的 prototype，或没有对应代码和训练结果的 spec，当作当前 V1 状态。

## 当前结论

V1 已经有一个真实训练、发布并被独立 7B 服务恢复消费过的 policy/value release：

- policy 和 critic 都通过同一个冻结 REAL-Prover 7B backbone 计算；
- active LoRA policy adapter 与 value head 一起训练，基座参数冻结；
- critic 是 categorical head，不是 scalar prototype；
- 训练标签是已验证 proof trajectory 的剩余 action distance；
- R2 恢复实验实际创建新会话、生成 policy candidates、估计 value，并通过 8 个真实 GPU recovery gates。

因此，下一步不是重新选择 value 语义或从随机 head 重启；而是固定 V1 release 身份，验证已上传 artifact 的兼容性，然后测量这个已定义 critic 在 holdout 和固定 search budget 下是否有用。

## 重要限制

V1 的 release / recovery 证据证明了训练、发布、恢复和服务消费；它**不**证明 value head 已经好、已经校准、已经泛化，或已经达到 AlphaProof 的 main-RL / TTRL 规模。

当前可见的 V1 混合训练 release 是两次联合更新、每次 9 条 verified replay action 加 1 条 Mathlib action。这是有效的机制级训练，不是大规模能力结论。

模型发布名称中的 full-v3 只是当时实验编号，不是架构版本或性能等级。上传到 Hugging Face 后仍应以 checkpoint / release / weights manifest 校验，而不是根据名称判断质量。

## 阅读顺序

| 页面 | 用途 |
| --- | --- |
| [00 V1 范围与 source of truth](00-v1-scope-and-source-of-truth.md) | 明确哪些源码和回执有裁决权 |
| [01 AlphaProof 论文基线](01-paper-baseline.md) | 固定论文的算法、训练和 TTRL 定义 |
| [02 V1 与论文的差异地图](02-gap-map.md) | 保留已对齐点，列出真正未完成项 |
| [03 V1 训练状态](03-training-status-2026-09-05.md) | 已训练 / 已服务 / 未证实能力的边界 |
| [04 V1 架构与数学合同](04-architecture-and-math-next.md) | 保持现有 categorical contract 的不变量 |
| [05 V1 训练与 TTRL 规模](05-training-and-ttrl-scale-next.md) | 从当前机制级训练扩展到可测规模 |
| [06 V1 执行顺序与计分卡](06-execution-order-and-scorecard.md) | artifact 验证、评估和扩容的 gates |
| [07 V1 证据定位表](07-evidence-ledger.md) | 将结论定位到 release-time source 和真实回执 |

## 不做的事

本次文档修订不安装、升级、编译或改动 Lean；不重新训练模型；不从旧文档推断 V1 行为。
