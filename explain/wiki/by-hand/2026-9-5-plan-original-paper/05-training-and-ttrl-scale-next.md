# 05 — 下一步：训练规模与真正的 TTRL

## 先校正“规模太小”的含义

是的，当前可见的 TTT / replay 实验相对 AlphaProof 原论文非常小；但比较不能只看 7B 大于 3B。

| 维度 | AlphaProof 论文 | 本地已审计 7B 证据 | 结论 |
| --- | --- | --- | --- |
| base | 3B encoder-decoder，巨量 pretraining | REAL-Prover 7B frozen base | 参数更多不替代 RL curriculum |
| Lean SFT | 约 300k pairs | 少量 Mathlib / verified replay steps 的机制性实验 | 还不是 SFT-scale 对齐 |
| RL start positions | 约 80M formal statements | 少量课程题和 target 周边题 | 不具备 broad main-RL coverage |
| main RL | 约 1M learner steps，约 80k TPU-days | 9 个 success-finalization receipt 合计约 21 条 trajectory state/action rows；少数 online updates | 只能验证管线，不验证 scaling |
| target variants | 数十万级；ablation 到 100k | 小型手工课程或少量变体 | 应称 micro-TTT，不是 TTRL |
| target compute | 50–500 TPU-days / target | 单卡、短 search / update | 目标是机制验证，不应做性能等价宣称 |

最终 Pell target 的在线 update 数为 0：它先被搜索解出，之后只有 1 条已验证 action 的 finalization update。整个历史课程搜索中记录的 online optimizer updates 也只有个位数。这足以确认参数确实被更新过，不足以得到一个校准良好的 general critic。

对开源项目的合理目标不是复制 180,000 TPU-days，而是让每一个缩小的阶段仍然保留论文的因果结构：**相关变体 → verified search → replay → joint policy/value update → paired evaluation**。

## 阶段化规模路线

下表给出可停、可测、可扩张的推荐门槛。数字是 Reap 的初始研究目标，不是论文声称，也不是不满足就不准实验的硬件要求。

| 阶段 | 训练对象 | 最低有用规模 | 必须报告 | 进入下一阶段的 gate |
| --- | --- | --- | --- | --- |
| S0：恢复与基线 | historic artifact 或 fresh base | 0 个新训练样本 | artifact status、head contract、固定 eval split | 能加载或明确 fresh-base；无随机 head 冒充已训练 |
| S1：critic 校准 | frozen policy + value head | 至少 10k verified trajectories 或 100k theorem-separated states | CE / MAE、rank accuracy、reliability、长度分布 | value-on 在固定 budget search 不劣于 uniform / value-off |
| S2：small generalist loop | policy + critic | 至少 10k distinct start positions，持续累积 verified proof/disproof replay | attempts、successes、states、proof/disproof 比、GPU-hours、solve@N | 对 held-out theorem split 有可重复的 solve@N 或 efficiency gain |
| S3：growth loop | matchmaker + actors + learner | 逐步扩至 100k+ start positions与百万级 state–tactic pairs | curriculum coverage、replay age、SFT:replay ratio、KL、regression | 多个 seed / checkpoint 的增益稳定，非单题偶然成功 |
| S4：target specialist | cloned generalist + variants | 每 target 先 1k，再 10k；只有质量过关才探索 100k+ | variant acceptance、dedup、distance-to-target、on/off gain | target proof rate 与 compute 曲线优于 search-only |

这里的 states 是经 theorem-level split 后的训练单元，不能把同一 proof 的相邻 100k states 误报为 100k 独立问题。

## 从 micro-TTT 到 TTRL 的定义门

一个 run 只有同时满足下列条件时才应叫 TTRL：

1. 从固定 main-RL generalist 初始化 isolated target specialist；
2. 目标题以外存在显式、版本化、经 Lean syntax / elaboration 检查的相关 variant set；
3. actor 在 target + variants 上产生新的 verified trajectories；
4. learner 对 policy 和 value 以可追溯 replay 更新；
5. 有同 budget 的 search-only、micro-update、variant-TTRL 三路 paired evaluation；
6. target / variant 数据不会悄悄污染 generalist eval。

仅在一个节点上用 REINFORCE、CE 或 TD 做 1–16 次更新仍有研究价值，但应称为 online adaptation 或 micro-TTT。

## variant curriculum 的质量优先于数量

论文的变体生成不是随机改变量名。Reap 应为每个 variant 记录：

| 字段 | 作用 |
| --- | --- |
| parent / target ID 与 mutator | 追溯学习路径 |
| Lean parse / elaboration verdict | 过滤无效对象 |
| transformation family | simplify、generalize、lemma、analogy、decomposition 等 |
| structural distance 与 string similarity | 防止全是近重复或全是无关题 |
| proof / disproof outcome、attempt history | 给 scheduler 使用 |
| split / leakage label | 防止把 eval proof 改写后回流训练 |

建议先实现确定性 mutators 和人工审查的小 variant set，再加入 LLM generator。否则系统会先吞掉大量无关或不可 elaboration 的候选，规模只会放大噪声。

## 每个 target 的实验矩阵

用完全相同的 base、prompt、candidate count、simulation budget、wall-clock cap、retrieval 和 seed bundle 比较：

| 组 | 参数更新 | 训练题 | 目的 |
| --- | --- | --- | --- |
| A | 无 | target | search-only baseline |
| B | 少量 target-only | target | micro-TTT 的净效应 |
| C | focused replay | target + checked variants | TTRL 的净效应 |
| D | 如 C，但随机／无关 variants | 对照 | 证明“相关课程”而非训练次数起作用 |

主要结果是 solve@budget、time-to-first-proof、verified trajectory yield 和最终 proof length；loss 只能作为诊断。若 C 没有比 A/B 稳定好，先检查 variant quality、prior、critic calibration 和 replay，而不是盲目提高学习率或增加 epochs。
