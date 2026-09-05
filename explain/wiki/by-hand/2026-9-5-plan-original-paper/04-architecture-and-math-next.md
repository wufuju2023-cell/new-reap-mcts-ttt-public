# 04 — 下一步：先统一架构与数学不变量

这一页是实现顺序，不是“再加一个 loss”的清单。前两项没有完成前，不应扩大训练。

## P0 — 定义唯一的 policy/value/search 合同

建议采用与 AlphaProof 对齐、但可由 decoder-only 7B 实现的合同：

$$
p_\phi(d\mid s),\qquad d\in\{0,\ldots,D_{\max}\}\cup\{\text{overflow}\}.
$$

令 $d$ 是完成 state 的最长剩余分支 tactic 数，终态为 $d=0$。从 critic 解码：

$$
\bar D(s)=\mathbb{E}_{p_\phi}[d],\qquad
V(s)=-\bar D(s),\qquad
Q(s,a)=\gamma^{-V(s,a)-1}.
$$

对 AND state：

$$
D(s_{\mathrm{AND}})=\max_i D(s_i),\qquad
V(s_{\mathrm{AND}})=\min_i V(s_i).
$$

这里的 64 只能作为 Reap 的候选 $D_{\max}$，不是论文正文确认的 AlphaProof bin 数。必须为 overflow / timeout 另写策略，不能静默 clamp 后伪装成已完成的短 proof。

**验收：**

- 同一个 state 在 generator、trainer、replay exporter、MCTS 和 HTTP response 中具有同一符号、单位和 decoder。
- checkpoint metadata 强制包含 base revision、head kind、support、target version、prompt hash 和 tokenizer hash。
- scalar legacy checkpoint 不允许在 categorical server 中静默加载；反之亦然。
- 用人工小树测试 OR backup、AND backup、terminal、overflow 和 $\gamma$ 的数值。

## P1 — 让 MCTS 获得真实 policy prior

公开路径要返回每个 completion 对应的生成 token IDs、token logprobs 与精确序列总和：

$$
\log\pi(a\mid s)=\sum_{t\in a\,+\,\mathrm{EOS}}\log\pi(a_t\mid s,a_{<t}).
$$

不要用 token average 代替 action probability，也不要把 prompt token、thinking prefix、被截断的 tactic 或第二个 EOS 算进 action。Lean consumer 和 GPU server 对同一条 canonical tactic 必须得到相同 logprob。

**验收：**

1. golden prompt + tactic fixture 给出精确 token 边界；
2. server 输出与本地 teacher-forced forward 的总 logprob 在容差内相等；
3. 两个不同概率的 valid tactics 在 PUCT first selection 产生不同 prior；
4. 缺失 logprob 是 hard error 或显式 uniform-baseline mode，绝不是悄悄回退。

这一步通常比增加 simulation budget 更有价值：否则 PUCT 没有使用 policy 的强弱。

## P2 — 把搜索语义固定成可回放工件

每次 search 应产出不可变 trace，至少包括：

| 字段 | 为什么需要 |
| --- | --- |
| canonical state / state hash | dedup、训练数据去重、复放 |
| tactic 原文与 canonical action | 策略标签与 token-logprob 绑定 |
| Lean verdict / successor hashes | 只让 verifier 决定合法转移 |
| root-to-node AND/OR path | 正确计算 longest-branch target |
| visit counts、prior、version、budget | 解释 PUCT 选择和做 imitation / replay |
| final proof、independent check receipt | 训练准入与安全边界 |

随后逐项验证：持续单树、invalid discard、local duplicate merge、progressive sampling、AND-node min backup、final independent Lean check。无法 replay 的 trace 不进入训练。

要把“局部 textual merge”与“全局语义 canonicalization”分开测量；不要因为两条 sibling tactic 的 pretty-print 相同，就宣称已经有完整 transposition table。

## P3 — 重新划分“失败”的用途

论文的主要 learner 从成功 proof/disproof 提取 pairs；timeout / 无解会影响 matchmaker 的优先级和预算。Reap 第一版也应分开：

| 事件 | 用于 policy/value supervised replay | 用于 scheduler / diagnostics |
| --- | --- | --- |
| 最终独立 Lean 验证的 proof / disproof | 是 | 是 |
| tactic parse / execution error | 否 | 是 |
| timeout / budget exhausted | 否 | 是 |
| 不完整但合法的中间 state | 仅作为已验证成功轨迹的一部分 | 是 |

这避免把“这次预算不足”错误地标成“这个 action 语义上很差”。

公开树目前没有 executable certified-disproof pipeline。因此短期 P0 可以只训练 verified proofs，但 replay schema 必须预留 objective / verdict 字段；实现 disproof 后再把它接入对称的训练与调度逻辑。

## P4 — generalist 和 target specialist 分层

建议把参数角色显式写入版本名：

    base → sft/generalist → main-rl-generalist → target-specialist(T, variant-set)

- generalist 的 replay 只能来自训练 curriculum；
- target-specialist 从冻结 generalist clone，训练数据明确标为 target / variant；
- target-specialist 不回写 generalist，除非通过独立、去泄漏的 generalization gate；
- evaluation 时报告 fresh-generalist、search-only、specialist 各自的结果。

这是防止“在测试题上训练过”与“test-time adaptation”叙述混淆的最小结构。

## P5 — matchmaker 的最小可用版

不必一开始复制论文的 TPU 集群，但应该先有一致的逻辑：

1. start positions 有 stable ID、source、split、prove/disprove objective；
2. scheduler 优先新题、低尝试数题和近期成败混合的题；
3. 连续失败提高 search budget 到 cap；连续掌握降低优先级；
4. actor 只回传 verifier artifacts；learner 从 immutable replay buffer 采样；
5. learner 固定保留一部分 Mathlib SFT replay，防止窄 self-play 退化。

当前公开 V1 driver 是串行脚本，且 RolloutSink 尚未接入实际 upstream MCTS；先接通单 actor 的 end-to-end verified replay，再扩并发。完成 P0–P2 后再实现 P5，才能知道 scheduler 放大的究竟是有意义的 search 还是 uniform-prior noise。
