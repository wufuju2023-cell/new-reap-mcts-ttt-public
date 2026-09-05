# 06 — 执行顺序、验收门与结果计分卡

以下顺序刻意把“可复现的系统事实”放在“扩大计算”之前。每一关失败都应留下 trace 和结论，不以重跑掩盖。

## 0. 冻结基线

**产物：**

- 一个 immutable base / adapter / head manifest，或明确的 fresh-base manifest；
- 固定 prompt、tokenizer、Lean / Mathlib / Reap revisions；
- theorem-level train/dev/test splits 和一组永不训练的 hard holdout；
- search budget 定义：candidate count、token cap、simulations、wall clock、memory cap。

**通过条件：** 同一 manifest 在新会话可以识别“权重可用”或“权重不可用”，不允许静默随机初始化。

## 1. 修复并测试 policy/value 合同

**产物：**

- token logprob golden tests；
- value schema / decoder / backup unit tests；
- AND/OR 小树 hand calculations；
- missing-logprob、head-schema-mismatch、prompt-hash-mismatch 的 hard failure tests。

**通过条件：** PUCT prior、$Q$、value response 和 checkpoint metadata 全部可复算。

## 2. 建立 verified replay 数据集

**产物：**

- 每条样本的 theorem ID、state/action hashes、Lean verdict、branch target、policy version；
- final independent proof receipt；
- dataset manifest、dedup report、split report；
- 只读 replay reader。

**通过条件：** 任取样本能 replay；train 中没有 holdout theorem 或其变体泄漏；timeout 不作为伪标签进入监督。

## 3. 先评估 critic，再评估 policy 更新

| 实验 | 对照 | 首要指标 |
| --- | --- | --- |
| critic calibration | random / scalar legacy critic | NLL / MAE、pairwise ranking、calibration |
| fixed-policy MCTS | value-off / uniform prior | solve@N、nodes-to-proof、time-to-proof |
| policy-prior ablation | real logprobs / uniform prior | first-choice quality、tree efficiency、solve@N |
| replay policy update | frozen baseline | held-out tactic NLL 与 fixed-budget proof search |

**通过条件：** 至少一个 held-out、预算固定的端到端指标改善，且不以训练题的单次成功作为证据。

## 4. 运行小 generalist loop

从小 curriculum 开始，但每代都写入：

    start positions attempted
    prove / disprove assignment
    search budgets and wall time
    valid tactics, verified successes, timeouts
    replay rows accepted / rejected
    policy and value losses
    KL to frozen reference
    held-out solve@N and efficiency

**停止条件：**

- holdout solve@N 连续两个 checkpoint 下降；
- value calibration 恶化或出现 saturation；
- replay 被单一 theorem family 占据；
- server / Lean trace 不能重放；
- policy prior 缺失或输出分布异常。

出现任一项时，保留 artifact、停止扩容、做消融；不要把失败样本直接加大权重。

## 5. 仅在 generalist 有效后启用 target specialist

每个 target run 应有：

1. frozen generalist identity；
2. checked variant manifest；
3. A/B/C/D paired experiment matrix；
4. per-target adapter isolation；
5. target proof 的独立 Lean final check；
6. 清晰的“是否允许回流 generalist”决定。

**通过条件：** C（相关 variants 的 focused RL）在相同预算下稳定超过 A（search-only）和 B（target-only micro-TTT），并且 D（无关 variants）不能产生相同效果。

## 统一发布报告模板

每一个未来 release 至少写出下表；这比单独报一条成功 proof 更能说明系统是否向 AlphaProof 的结构推进。

| 类别 | 必填 |
| --- | --- |
| identity | code revision、base revision、adapter/head artifact hash、prompt/tokenizer hash |
| data | theorem counts、state counts、prove/disprove、source、split、variant stats |
| training | steps、tokens、GPU-hours、LR、KL、loss、replay:SFT ratio |
| search | candidates、logprob mode、simulations、progressive sampling、AND/OR trace |
| outcome | Lean-verified solve@N、time/nodes-to-proof、proof length、failure taxonomy |
| ablation | prior on/off、value on/off、search-only/micro-TTT/TTRL |
| integrity | final-check receipts、leakage audit、known limitations |

## Immediate next action

Do not start another large TTT run yet. First produce one small, fully reproducible benchmark in which:

1. real token logprobs reach Lean;
2. one unambiguous critic schema is loaded;
3. verified trajectory labels replay;
4. value-on / value-off and prior-on / uniform are compared under the same budget.

If that experiment is clean, its data and measurements decide whether the next dollar of compute should go to critic data, broad generalist replay, or target-variant TTRL.
