# 05 — V1 训练规模与 TTRL：先把已训练 release 测清楚

## 当前 V1 的规模定位

V1 已训练，不等于 V1 已达到 AlphaProof 的训练规模。

| 维度 | AlphaProof 论文 | V1 实际已验证状态 |
| --- | --- | --- |
| base | 3B encoder-decoder，巨量预训练 | frozen REAL-Prover 7B backbone |
| value | categorical remaining return | categorical verified remaining-action distance |
| Lean SFT | 约 300k pairs | R2 混合 batch 中每次 1 条 Mathlib action |
| replay | 大规模 self-generated proof/disproof | R2 两次 batch，共 18 replay + 2 Mathlib action rows |
| main RL | 约 1M learner steps | V1 已有 learner/release/recovery mechanism，真实更新仍很少 |
| TTRL variants | 数十万 target variants | 没有等规模的 V1 variant curriculum / paired target result |

V1 的正确科学定位是：**shared-backbone joint learner 已经真实运行；规模、coverage 和价值质量尚未建立。**

## 先做四个固定基线

在扩数据、扩 GPU 或做 target TTRL 前，使用已上传的同一 V1 artifact 做以下 paired tests：

| 测试 | 固定项 | 要回答的问题 |
| --- | --- | --- |
| critic calibration | theorem-level holdout、同一 prompt | $\hat d$ 是否与 verified remaining distance 有排序 / 校准关系 |
| value ablation | 同 policy、同 candidates、同 simulation budget | value-on 是否比 value-off 更快或更常找到 verified proof |
| prior ablation | 同 release、同 budget | real policy prior 是否比 uniform prior 更有效 |
| release regression | R2 与 frozen base / ancestor release | joint updates 有没有引入净增益或回归 |

主要指标应是 verified solve@budget、nodes-to-proof、wall time、distance ranking、calibration 和 failure taxonomy；不能只报 CE loss。

## 从当前 V1 扩展 replay

下一阶段应扩大的是 **经完整 Lean replay 验证的 action rows**，并保留 current contract：

1. 先把 $d=1,\ldots,8$ 都覆盖，记录 class histogram；
2. theorem-level split，不能让同一证明的相邻 states 跨 train / holdout；
3. 持续混合 verified generated rows 与 Mathlib rows；
4. 每个 release 记录 source mix、base / adapter / head identity、KL、support overflow；
5. 用固定 holdout gate 决定是否发布下一 release。

目标不是任意设一个大数字，而是让每次扩容都有可检验的因果结果。达到稳定 value-on 增益前，不应把更多训练 steps 当作默认进步。

## TTRL 的最低定义

V1 只有同时满足下列条件时，才应称为 AlphaProof-style target TTRL：

1. 从固定 generalist V1 release clone 出 isolated target specialist；
2. 生成并 Lean 检查明确版本化的 target variants；
3. 在 target + variants 上产生新的 verified replay；
4. 使用已有 joint policy/value learner 更新 specialist；
5. 对同一 target 做 search-only、target-only update、variant-focused update 的 paired comparison；
6. target data 不反向污染 generalist holdout。

单题内少量 update 可以继续称为 V1 online adaptation，但不能替代上述 variant curriculum。

## 面向论文规模的务实路线

| 阶段 | V1 目标 | 通过门 |
| --- | --- | --- |
| A | R2 artifact load + endpoint fixtures | identity 和 protocol 全部一致 |
| B | distance coverage + theorem holdout | critic calibration 和 value-on 不劣化 |
| C | 持续 verified replay / mixed learner | 多 release 的 fixed-budget gain |
| D | 小型 deterministic variants | 相比 search-only 的 paired target gain |
| E | 质量审计后的 large variant curriculum | variant quality、compute、gain 三者关系清楚 |

论文的 10k–100k+ variants 可以作为远期量级参照，但现在最有价值的是先用 V1 已存在的 architecture 证明每一步扩容值得。
