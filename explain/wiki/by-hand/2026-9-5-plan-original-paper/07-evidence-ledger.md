# 07 — 证据定位表与断言边界

本页让读者能区分“论文事实”“公开源码事实”“历史实验记录”，而不必相信叙述性总结。

## 论文定位

| 断言 | 随附 PDF 定位 |
| --- | --- |
| 3B encoder-decoder，policy + categorical value | AP pp. 3、9 |
| $-1$ reward、AND state 用最小 return / 最长分支 | AP pp. 2–3、9 |
| PUCT、$Q=\gamma^{-V-1}$、progressive sampling、AND selection | AP pp. 9–10 |
| 单次 attempt 持续一棵 tree | AP p. 10 |
| 300B pretrain、300k Lean SFT pairs、80M formal curriculum | AP pp. 3、10–11 |
| 90% replay / 10% Mathlib、约 1M main-RL steps | AP p. 11 |
| TTRL 变体生成、最多 15 次演化、数十万 variants | AP pp. 11–12 |
| SFT / autoformalization / main-RL compute 数量级 | AP p. 11 |

PDF 中引用但未附带的 Supplementary Tables 不能用来声称精确 bin 数、optimizer 或 search hyperparameters。

## 公开 Reap 源码定位

| 断言 | 公开工作树的定位 |
| --- | --- |
| 持续 per-attempt tree、最终 replay / checkProof | new-v1-gather-source-code-cpu/reap-upstream/Reap/Tactic/TreeSearch.lean |
| AND/OR、focused subgoals、min backup、PUCT、progressive sampling | 同一 TreeSearch.lean |
| state key 是 pretty-printed goals 的 textual JSON；局部 merge | Reap/Tactic/State.lean 与 TreeSearch.lean |
| Lean generator 请求并消费 token logprob | Reap/Tactic/Generator.lean |
| 公开 server 未返回 OpenAI token logprobs，且可在无 checkpoint 下启动随机 scalar head | app/policy_server.py |
| executable public head 是 Tanh scalar | app/value_head.py |
| public wiki 声称 64-bin categorical head 与训练 state 数 | explain/wiki/07-model-and-value.md |
| V1 driver 串行执行，sink 未接入 upstream MCTS | app/v1_run.py、app/v1_sink.py、lean-v1/Reap/Training/RolloutSink.lean |
| public SFT 程序是 skeleton | app/train_sft.py |

源码定位说明当前公开 snapshot 的行为；不能反向证明历史 GPU 实验使用了同一条 server 或同一版本的 head。

## 历史 REAL-Prover 7B 记录定位

| 断言 | 审计到的证据类别 |
| --- | --- |
| Pell 课程与最终 target 有独立 Lean 验收 | 2026-08-28 REAL-Prover Pell result package 的 README、proof receipt |
| final target 在题内 online update 前完成 | 该 package 的 search online-result 和 results narrative |
| LoRA + value 参数发生过改变 | success-learn receipts、release metadata |
| 约 21 条 trajectory rows / 9 finalization receipts | 历史 receipts 汇总 |
| categorical mixed / continual / central-learner 轨道存在 | evidence/current 的 release contract 与 training reports |
| tensors 没有随 Git 导出 | weights index、evidence README、公开 VALUE_HEAD 文档 |

这类记录适合证明“曾经发生过的受控实验”，不适合在没有 tensor artifact 的情况下执行当前 checkpoint load。

## 断言规则

发布或论文中每一个强断言应至少满足对应的证据门：

| 想说的话 | 最低证据 |
| --- | --- |
| 已训练 critic | checkpoint artifact + schema + training manifest + holdout critic evaluation |
| search 使用 policy prior | server token-logprob golden test + Lean trace 的 non-uniform priors |
| 已实现 main RL | actor→verified replay→learner→new actor 的端到端 trace，及持续 curriculum statistics |
| TTRL 有收益 | 同预算 A/B/C/D paired experiment，target variants 的 manifest 与 leakage audit |
| 模型解出 theorem | final independent Lean check receipt 和完整 proof |

若证据只达到较低一层，应降低措辞。例如，有 receipt 可以说“参数更新被记录”；没有 holdout 不应说“模型更强”。
