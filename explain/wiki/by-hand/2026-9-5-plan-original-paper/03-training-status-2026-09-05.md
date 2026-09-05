# 03 — 2026-09-05：V1 训练状态

## 结论

V1 不是随机 head，也不是只有设计文档的计划。它有 receipt-backed 的 shared-backbone categorical policy/value training、publication、recovery 和真实 HTTP service consumption；当前又有一个可读取的 uploaded full-v3 snapshot。

本机 Git 包不携带大型 checkpoint tensor，不等于 V1 没有训练后模型。训练后的 adapter + value head 原本保留在持久 artifact store；uploaded full-v3 现已提供其 snapshot、manifest 与 acceptance session。full-v3 只是实验编号，仍须按自身 contract 评测，不能借用另一个 V1 release 的结果。

## 已被真实回执支持的事项

| 项 | V1 证据 |
| --- | --- |
| 7B base | REAL-Prover 7B，base 在训练前后保持冻结和一致 |
| shared representation | policy 与 value 都调用同一个 active 7B model；value 读最后层 hidden state |
| trainable parameters | 392 个 LoRA tensors + 4 个 categorical head tensors |
| training objective | policy NLL、对 frozen base 的 KL、categorical value CE |
| uploaded artifact | full-v3：3584 → 256 → 64 categorical head；adapter + value head 一起 transfer；independent Lean acceptance passed |
| local V1 release | R2 receipt 使用 verified return $-d$，support 为 $d=1,\ldots,8$，并完成 fresh-service recovery |
| mixed learner | 两次真实联合更新，每批 9 条 verified replay + 1 条 Mathlib action，共 20 sampled rows |
| publication | 每次更新后有 checkpoint / release receipt，并记录 adapter + value-head transfer |
| consumption | 后续 recovery 实验将已发布 R2 放入新的 REAL-Prover 7B HTTP session，实际生成 policy candidate 并估计 value；8 项 recovery gates 通过。这证明 V1 runtime，而不是 full-v3 的质量。 |

release-time source archive 与本地 V1 source 的 hashes 对齐，因此上述架构和回执属于同一实现，不是从另一个 prototype 借来的描述。

## 这个训练状态没有证明什么

V1 当前没有下列证据：

- theorem-level heldout critic calibration；
- value-on 对 value-off 的固定 budget proof-search 增益；
- real policy prior 对 uniform prior 的端到端消融；
- 多 seed、多 checkpoint 的稳定 solve@N 改善；
- AlphaProof-scale main RL curriculum；
- target variants 上的 paired TTRL result。

因此最准确的状态是：

> V1 是一个已经训练、发布和服务过的 categorical policy/value artifact；其训练规模仍是机制级，质量和泛化仍待评估。

## Artifact 发布后的兼容性检查

模型 artifact 可读取后，按顺序核对：

1. REAL-Prover base revision 与 tokenizer / base hash；
2. V1 categorical head shape：3584 → 256 → $D$；
3. support、return semantics、overflow policy、value decoder；
4. adapter + head tensors 与 release manifest 的 digest；
5. policy token-logprob 和 value endpoint golden fixtures；
6. fresh V1 session 对 artifact 的加载、candidate generation 和 expected-distance response。

任何一项不匹配，都应标为另一个 artifact / run，而不是通过名称、bin 数或“V1”标签猜测兼容性。

## 当前最重要的科学问题

artifact 可加载后，最优先的问题不是“还能不能训练”，而是：

$$
\text{Does V1 value guidance improve fixed-budget verified proof search?}
$$

这需要 same-theorem、same-prompt、same-policy release、same candidate count、same simulation budget 的 paired ablation，而不是查看训练 loss 或单题 proof。
