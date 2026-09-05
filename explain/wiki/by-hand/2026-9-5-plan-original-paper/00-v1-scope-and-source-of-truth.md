# 00 — V1 范围与 source of truth

## 唯一讨论对象

V1 的 authoritative evidence 是以下两类材料的交集：

1. V1 release-time GPU / CPU 源码；
2. 使用该源码产生的 immutable training、publication、recovery 和 service-consumption 回执。

审计时以 value-head repository 中的 v1-result/reproduction/code/src、v1-result/source/current 与 v1-result/evidence/current 为准。release 的内嵌 code archive 与本地 V1 源码逐文件 hash 对齐，因此这里不是根据讲义或 spec 反推实现。

以下材料不裁决 V1 当前状态：

- 旧的连续 scalar head 实验；
- V2 或不同分支；
- public snapshot 中未接入 V1 runtime 的 app prototype；
- 没有真实训练或服务回执的计划、规格和讲义。

## V1 的实际架构

V1 使用一个冻结的 REAL-Prover 7B causal language model，hidden size 为 3584。

同一模型对象承担两件事：

1. policy 从 active LoRA adapter 的 7B model 生成 tactic，并提供 token logprobs；
2. value 从同一 active model 的最后层 hidden state 读取表示。

value head 是：

$$
h_{7B}(s)\in\mathbb{R}^{3584}
\longrightarrow
\mathrm{Linear}(3584,256)
\longrightarrow
\mathrm{SiLU}
\longrightarrow
\mathrm{Linear}(256,D).
$$

输出为 $D$ 个 categorical logits。support 必须随 artifact identity 读取，不能从另一个 V1 run 推断。

当前上传的 full-v3 snapshot 明确为 $D=64$；本地曾恢复消费的 R2 release 为 $D=8$。二者都是 V1 family 的真实 artifact，但 shape、support、weights 和 provenance 不可互换。本系列将 uploaded full-v3 作为待评测 artifact，而把 R2 只当作 V1 runtime / recovery 的历史证据。

这里“共享同一基座”有精确含义：policy 和 critic 共用冻结 7B 表示与 active LoRA policy representation；value head 本身仍是独立的 4 个可训练 tensors。它不是全基座 full fine-tuning。

## V1 的训练对象

一次 V1 learner update 同时优化：

$$
\mathcal{L}
=
\mathcal{L}_{\mathrm{policy\;NLL}}
+\beta\mathcal{L}_{\mathrm{KL\;to\;frozen\;base}}
+\lambda\mathcal{L}_{\mathrm{categorical\;CE}}.
$$

训练回执显示 392 个 LoRA tensors 和 4 个 value-head tensors 都实际变化，且冻结 7B base 的指纹在训练前后保持一致。

## V1 value 的精确定义

V1 的 code name 是：

$$
\texttt{verified\_negative\_longest\_branch\_categorical.v1}.
$$

对已验证 replay row，令 $d$ 为记录的成功 proof 中剩余 generated actions 的 critical-path distance：

$$
\mathrm{return}=-d,\qquad
\mathrm{class}=d-1,\qquad
d\in\{1,\ldots,D\}.
$$

单链时 $d$ 就是剩余步骤数。AND node 时 value 是负 return 的最小值，因此正距离是未完成子目标中的最长分支：

$$
\min_i(-d_i)=-\max_i d_i.
$$

这常被口语化为“最小剩余步骤 value”，但更精确的说法是：它学习**记录的成功 proof 的剩余 critical-path action distance**。OR path 使用记录的 solved child，并没有在所有可能 proof 中计算全局 shortest proof。

server 从 categorical distribution 得到正的 expected distance：

$$
\hat d(s)=\sum_{d=1}^{D}d\,p_\phi(d\mid s).
$$

Lean / MCTS consumer 将其取负，恢复 negative-return 约定。

## 真实结果与能力结论必须分开

| 可以说 | 不能说 |
| --- | --- |
| V1 shared-backbone critic 已训练、发布、恢复并被服务消费 | 它已经是好 critic 或强泛化模型 |
| 本地 V1 R2 的 policy/value endpoint 实际运行 | uploaded full-v3 已在 heldout 上优于 baseline |
| V1 有 categorical remaining-action target | 它已经复现 AlphaProof 规模 |
| full-v3 是 artifact 的实验编号 | full-v3 本身说明模型能力 |

后续所有页面仅在这个 V1 合同上讨论下一步。
