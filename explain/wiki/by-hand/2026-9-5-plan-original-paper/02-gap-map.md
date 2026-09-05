# 02 — V1 与 AlphaProof：差异地图

## 已对齐的核心结构

| AlphaProof 论文结构 | V1 实际状态 |
| --- | --- |
| Lean-verified proof trajectories | V1 replay 先独立验证、逐步重放，再允许训练 |
| joint policy/value model | 同一 REAL-Prover 7B backbone 的 LoRA policy + categorical critic 联合更新 |
| value 是剩余证明长度语义 | V1 是 verified remaining critical-path action distance |
| AND node 使用最难子目标 | V1 labels 对 AND 取 negative return 的最小值，即最长正距离分支 |
| policy prior | V1 runtime 产生 token logprobs，供 tactic policy / search 使用 |
| immutable release / new-session consumption | V1 有 checkpoint、release、预约、恢复与独立新服务消费回执 |

这意味着 V1 不需要从“是否共享 backbone”或“value 是否分类化”重新设计。

## V1 与论文仍有的关键差异

| 项 | AlphaProof | V1 | 研究含义 |
| --- | --- | --- |
| base architecture | 3B encoder-decoder | frozen REAL-Prover 7B causal LM + LoRA + external categorical head | 合理替代，但必须用 benchmark 证明 search 效果 |
| categorical support | 论文正文未公开精确 support | 当前 R2 为距离 1..8，overflow reject | 远距离 proof 的表达能力尚未测量 |
| autoformalization curriculum | 约 80M formal problems | V1 真实训练是小型 verified replay / Mathlib mixed batches | 最大差距是数据与 curriculum，不是 head 是否存在 |
| main RL | 约 1M steps、actors、matchmaker、learner | V1 已有 learner/release/consumer 机制，但真实更新数很少 | 需要先评估，再逐步扩 actor/replay |
| prove / disprove | 论文把两者纳入大课程 | V1 有 proof / refutation collector evidence，但尚未形成大规模对称 curriculum | 需要明确 per-objective stats 和 heldout |
| TTRL | target + 数十万相关 variants + focused RL | V1 没有 AlphaProof-scale variant curriculum 或 paired target result | 当前不能把 V1 叫论文级 TTRL |

## 不再作为 V1 缺口的旧问题

以下问题属于被排除的旧 snapshot / prototype，不应成为 V1 的状态判断：

- public scalar head 的 Tanh schema；
- 未接入 V1 runtime 的 server response；
- V2 或旧计划中的 target definitions；
- 没有 training receipt 的说明性文档。

如果需要 public repository 完整复现 V1，正确动作是移植 / 发布 V1 release-time runtime 和 artifact contract，而不是修补旧 prototype 后把它称为 V1。

## 最短的下一条研究路径

1. 对已上传的 V1 artifact 做 identity / schema / tensor hash 检查；
2. 在固定 theorem-level holdout 上做 critic calibration 与 value-on/off search ablation；
3. 在相同预算下测 real policy prior 与 uniform-prior；
4. 只有这些基线清楚后，扩大 verified replay、curriculum 和 target variants。

这能把“V1 确实训练过”与“V1 已被证实有用”严格分开。
