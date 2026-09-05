# 06 — V1 执行顺序与计分卡

## 0. 固定 artifact identity

Hugging Face artifact 可读后，先生成不可变 identity record：

| 字段 | 必填 |
| --- | --- |
| V1 source archive / code hash | 是 |
| REAL-Prover base revision 与 tokenizer hash | 是 |
| adapter + categorical head tensor digest | 是 |
| head shape 与 support | 是 |
| return / class / overflow contract | 是 |
| release / checkpoint metadata | 是 |
| full-v3 发布名 | 仅作 distribution label，不作能力解释 |

如果 uploaded artifact 与任一已有 V1 contract 不匹配，应创建新的 run identity，不能覆盖任何历史 release 的记录。

## 1. 只读加载与 protocol smoke test

不需要重新训练，也不需要编译 Lean：

1. 在 V1 runtime 中加载 fixed REAL-Prover base + adapter + head；
2. 验证 head tensor names、shapes、dtypes 和 digest；
3. 对 golden prompt 获取 policy token logprobs；
4. 对 golden state 获取 categorical value / expected distance；
5. 验证 snapshot / release load 到 fresh session；
6. 验证 base parameters 没有改变。

成功后，artifact 才可称为“当前可加载 V1 release”。

## 2. 先评估 value，后扩大训练

| 消融 | 不变条件 | 结果 |
| --- | --- | --- |
| value-on / value-off | same release、theorems、candidates、budget | critic 的 search contribution |
| real-prior / uniform-prior | same release、budget | policy prior contribution |
| uploaded full-v3 / R2 / frozen-base | same search configuration | 各 artifact 的 joint training net effect |
| observed-distance strata | same budget | 对 $d=1..4$ 与未见 bucket 的行为 |

所有结果都应以独立 Lean final check 为准。

## 3. V1 release gate

只有同时满足以下条件，才发布下一 release：

- no artifact/schema mismatch；
- no base-model mutation；
- verified replay dataset 可重放；
- holdout search 不回归，或有预先注册的接受理由；
- distance support / overflow 分布已报告；
- release、adapter、head 和 dataset hashes 全部保存。

## 4. 扩容 gate

| 想增加什么 | 前置证据 |
| --- | --- |
| 更多 replay rows | uploaded full-v3 load 与 critic ablation 已完成 |
| 更大 support | class coverage、shape migration、uploaded full-v3 与 R2 baselines 已保留 |
| 更多 actor / learner updates | fixed-budget heldout 不回归 |
| target variants | generalist baseline 和 target paired matrix 已建立 |

## 5. 每个结果的最小报告

    source / base / adapter / head identities
    categorical support and label histogram
    policy and value update counts
    replay / Mathlib source counts
    search candidates, priors, simulations, wall-clock
    independent Lean verification outcomes
    value-on/off and prior-on/uniform ablations
    known limitations

最重要的一句话应始终是：**V1 value head 是否在相同预算下提升 verified proof search。**
