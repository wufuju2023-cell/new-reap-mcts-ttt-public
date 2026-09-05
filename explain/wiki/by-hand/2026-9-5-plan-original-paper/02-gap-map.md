# 02 — AlphaProof 与当前 Reap：差异、冲突与未知项

本页按影响排序。它避免把“不同的合理实现选择”与“尚未可比的缺失”混为一谈。

## A. 已对齐的搜索核心

**[仓库]** 上游 Reap 搜索路径已经有值得保留的 AlphaProof-style 核心：

| 论文要求 | 当前公开搜索路径 | 结论 |
| --- | --- | --- |
| 每次 attempt 持续一棵 tree | StateT 中持续维护 tree | 基本对齐 |
| AND/OR 多子目标 | OR 任一解；AND 全部解；min backup | 基本对齐 |
| PUCT + progressive sampling | 已实现选择公式和增量采样 | 基本对齐 |
| Lean tactic validation | 合法执行、terminal 判断 | 基本对齐 |
| final proof verification | 重建／replay 后再做 final checkProof | 基本对齐 |

这些判断针对 Lean 搜索核心，不自动覆盖公开 GPU server、训练管线或实验 backend。

## B. 已经确认的高优先级差异

| 项 | AlphaProof 原文 | 当前公开 Reap 快照 | 影响 | 下一步 |
| --- | --- | --- | --- | --- |
| policy prior | MCTS 使用模型的 $\pi(a\mid s)$ 与 temperature | Lean 请求 token logprob，但公开 app 的 OpenAI 响应没有返回它；缺失时 Lean 侧会退化为 $0$ logprob | 有效 action 的 PUCT prior 近似一致，policy 无法指导 tree policy | 先修复并 golden-test token-level logprob 的序列边界与总和 |
| value 形态 | encoder value head 的 categorical return distribution | 可执行公开 app 是 scalar MLP，Tanh，范围 $[-1,1]$ | 长 horizon 被压缩；与 $Q=\gamma^{-V-1}$、关键路径 distance 的单位不天然一致 | 建立一个唯一的 value contract，再训练／加载任何 head |
| value 文档 | 论文的负剩余关键路径 return | 同一公开仓库的 wiki 又描述 64-bin categorical distance head 和大量训练 state | 文档、代码、历史实验之间不能互换 checkpoint 或指标 | 将每个版本的 head type、target、decoder 和 checkpoint schema 写入 metadata |
| state merge | 语义等价 successor 合并 | 以 pretty-printed goals JSON 做 textual key，局部 sibling merge / ancestor cycle suppression | 不能声称有论文级 alpha-renaming、hypothesis-order canonicalization 或全局 transposition table | 报告为 local duplicate merge，并对 canonicalization 单独设计测试 |
| prove / disprove | matchmaker 对称安排，两种成功轨迹回流 learner | 公开 executable search 路径只报告 solution / exhausted，未发现可执行 certified-disproof pipeline | auto-formalization 的“错误 formalization 仍有用”闭环尚未对齐 | 把 proof 和 disproof 的目标、验收、replay schema 分开实现 |
| actor / learner | 分布式 matchmaker、actors、central learner | 公开 V1 driver 按 workers 参数仍串行跑；RolloutSink / schema 未接入实际 upstream MCTS；SFT 程序标为 skeleton | 还没有公开可执行的 main-RL actor-learner loop | 先接通单 actor 的 end-to-end verified replay，再扩并发 |
| target adaptation | 变体课程后运行 focused RL | 当前小题内在线更新通常只有 0–少数 steps，课程由少量手工桥题组成 | 小规模 adaptation 不能解释为论文级 TTRL | 改称 micro-TTT，直到有 variant curriculum + replay + on/off eval |

### 公开 policy prior 的具体断点

**[仓库]** Lean generator 请求并消费 token logprobs，而公开 policy server 仅返回一个未用于搜索的平均字段，未返回 choice 的 token logprob 列表。缺失值会让 valid tactics 在 prior 上失去差别。这一问题仅针对公开 app 路径；历史 Pell 实验的另一个 GPU backend 有实际 token-logprob schema，不能把两者混为一谈。

在修复之前，增加 MCTS simulations 主要是在更均匀的候选集合上搜索；它不是论文所描述的 policy-guided scaling。

## C. 已经确认的“多版本冲突”

审计到至少三种不兼容的 value 描述：

| 位置 | 声称或实现的 head / target |
| --- | --- |
| 公开 app 的 VALUE_HEAD 与实现 | Linear–SiLU–Linear–Tanh scalar；归一化 return / proof depth 的 MSE 或 Huber |
| 公开 wiki 的模型页 | 64-bin categorical distance head，且写有训练 state 数 |
| 2026-08-28 REAL-Prover 7B Pell 结果包 | success receipt / 文档称 sigmoid search-visit backup；对应 backend 代码构造 Tanh scalar；另一个 categorical backend 也存在但没有证明服务于 Pell run |

这不是小的术语差异。sigmoid、Tanh scalar 与 categorical distribution 的输出域、校准方法、loss、backup 解码和 checkpoint 结构不同。任何“已经训练 value head”的结论都必须附带：**哪一种 head、哪一种标签、哪一个 base revision、哪一个 artifact hash、由哪个 server 消费**。

## D. 与论文不同但并非自动错误的选择

| 项 | 论文 | Reap 可接受的替代 | 必须补的证据 |
| --- | --- | --- | --- |
| backbone | 3B encoder-decoder | 7B decoder-only REAL-Prover + attached critic | prompt/hidden-state contract、policy prior、critic calibration 与端到端 search 增益 |
| compute | 大规模 TPU actors | 单卡／小集群渐进实验 | 每阶段的 attempts、states、tokens、GPU-hours、solve@budget 曲线 |
| variants | Gemini + programmatic generation | 开源 generator + deterministic Lean mutators | 语法通过率、去重率、距 target 的关系、是否泄漏 eval |
| curriculum | 80M start positions | 更小但分层、持续增长的公开课程 | 按 theorem 的 train/dev/test 隔离，而非只报步骤数 |

不同不是问题；不记录语义、规模和验证方法才是问题。

## E. 结论

最短路径不是先把已有的小 TTT 反复跑大，而是：

1. 给 policy prior 和 value semantics 建立可测试的统一合同；
2. 接通可执行的 verified trace 到 replay / learner 最小闭环；
3. 先证明 critic 和 prior 让固定预算 search 更好，再扩大 curriculum；
4. 最后再做 target variant 的 focused RL。

这样每一个增益都有可归因的前提，不会把数据泄漏、uniform PUCT、随机 critic 或手工课程收益误归因为“AlphaProof 式 TTRL”。
