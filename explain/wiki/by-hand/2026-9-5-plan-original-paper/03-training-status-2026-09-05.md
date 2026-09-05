# 03 — 2026-09-05：REAL-Prover 7B 训练状态审计

## 总结

**已发生的历史训练，不等于当前可部署的训练状态。**

在给定目录的只读审计中，最新可见的 7B 实验记录日期是 2026-08-28 至 2026-08-29。它们记录了真实 GPU 上冻结 REAL-Prover 基座、LoRA 与 value 参数更新，并有独立 Lean proof 检查。扫描到的仓库中没有可加载的 adapter、value-head tensor、optimizer tensor 或完整 checkpoint 文件；记录明确说明这些张量保留在 Git 之外。

因此当前状态应写成：

> 有可追溯的历史训练 lineage 和 Lean-verified trajectories；没有随本地 Git 工作树提供的可恢复训练后模型；没有足以证明泛化或 TTRL 收益的 paired benchmark。

这只是对所给本地路径截至 2026-09-05 的结论，不排除其他未挂载的 artifact store 或之后的远端运行。

审计时也没有发现正在运行的训练、policy server 或 REAL-Prover 进程；本地 output 中能看到的近期日志是 2026-08-26 的 HTTP 404 失败片段，而不是 training metrics。某个历史 latest-release GPU 阶段本身标记为失败，不能误写成已完成的当前部署。

## 已验证的 7B 证据

| 证据阶段 | 已记录的事实 | 不能推出什么 |
| --- | --- | --- |
| Pell 课程链，2026-08-28 | REAL-Prover 7B、冻结基座、LoRA + value 更新；多个课程 proof 经 Lean 验收；最终原 target 有独立 Lean 验收 | 不证明从未训练 base 能直接解 target，也不证明稳定 pass rate |
| 最终 Pell target | target 在题内在线更新前已解出；随后发生一次成功轨迹 finalization update 并发布 | 不能把这道 target 的成功归因为“更新后继续搜索”或 TTRL |
| verified replay | 3 份模型成功证明抽出 11 个逐步验证的训练样本，做过一次真实联合更新 | 没有新的解题效果对照 |
| central learner | 已训练版本产生新证明，独立检查后 2 个生成步骤进入第二次训练并发布新版本 | 数据量很小，不能当作 main RL 已建立 |
| mixed learner | 4 份生成 proof 的 13 steps 与 3 份 Mathlib proof 的 7 steps，按 9:1 step ratio 进行两次真实训练 | 没有用新参数跑出 paired proof-search gain |
| continual mixed | 继承已发布参数，又加入 2 个独立验证的反证 steps，进行了两次真实训练 | 未验收针对单一 target 的专门学习或泛化提升 |

历史 Pell 配置还记录：base revision 固定、LoRA rank 16 / alpha 32 / dropout 0，hidden size 3584，policy LR $10^{-4}$，value LR $3\times10^{-4}$，$\gamma=0.99$，KL coefficient 0.02。它是一个有价值的可复现训练机制证据，不是 AlphaProof 主训练的规模证据。

## 已审计的量级

Pell 历史链的 9 个 success-finalization receipts 合计只有约 21 条 trajectory state/action rows；每次通常改变 392 个 LoRA tensors 与 4 个 value-head tensors。9 个课程 search 中记录的题内 online optimizer updates 也只有个位数。最终原 Pell target 在 online update 前已经完成，之后的 success finalization 只训练了 1 条真实 action。

所以“7B head 确实被训练过”成立，但“它已由大量、平衡的剩余证明深度样本校准”不成立。所有成功、极少量动作、单题课程的样本分布尤其不适合直接推断 general critic 质量。

## 权重可用性

历史 release lineage 含多个 metadata entry，记录 adapter + value-head 传递与 checksum，但其本身声明 backend tensors 不在 Git。公开 app 文档也明确不随源码提供已经训练好的 REAL-Prover value-head binary。

在把这个状态用于任何新实验前，先完成以下二选一：

1. **精确恢复。** 从原 artifact store 获取特定 release 的 adapter、value head 与 metadata，逐项核对 base revision、tensor hashes、head schema、prompt/tokenizer 和 value decoder。
2. **明确 fresh start。** 固定 REAL-Prover base，重新建立 head 与 dataset；报告为 fresh-base 新实验，不把它称为历史训练链的继续。

不要只根据一个 JSON manifest 或“有 checkpoint hash”启动服务；那会把随机初始化 head 误当成已训练 critic。

另外，公开 app 的 head-only offline trainer 产出的是另一种 checkpoint schema，不能直接加载历史 REAL-Prover backend snapshot。恢复历史 artifact 前，需要一个只读 verifier / exporter，而不是用新 schema 强行读取旧 metadata。

## 训练状态的三个缺口

### 1. artifact 缺口

现在不能执行 checkpoint load、parameter diff 或 inference comparison。恢复权重是可行性门，不是可选优化。

### 2. semantic 缺口

历史记录、公开 wiki 和公开 executable app 对 value 的 output type 不一致。训练前必须把每个 release 明确标为 scalar-Tanh、scalar-sigmoid 或 categorical，并固定：

$$
\text{target definition},\quad
\text{loss},\quad
\text{decoder},\quad
\text{MCTS backup},\quad
\text{server response schema}.
$$

否则“继续训练旧 value head”没有明确数学对象。

截至本次审计，可见的组合包括：公开 executable app 的 continuous Tanh + MSE/Huber；Pell 文档／receipt 的 scalar-sigmoid 表述与其 backend Tanh 实现之间的冲突；以及另一条 mixed / continual / central-learner lineage 的 categorical negative-distance contract。它们不能隐式互相恢复或比较。

### 3. evaluation 缺口

历史证据强在完整性、隔离、回放与 Lean 验收；弱在规模与因果效果。尚缺：

- 固定 theorem-level holdout 上的 critic calibration / ranking；
- 相同 seed、budget、prompt、retrieval 下的 value-on vs value-off；
- 相同 budget 下 policy-prior-on vs uniform-prior；
- train / dev / test 严格分离的 solve@N 曲线；
- TTRL-on vs TTRL-off 的目标题 paired comparison。

在有这些对照前，训练 loss 下降、参数改变或单题成功都不能当作 AlphaProof 式能力增长。

## 当前最诚实的命名

| 名称 | 是否适合当前证据 |
| --- | --- |
| 已验证 proof-search / replay / release mechanism | 是 |
| REAL-Prover 7B 上的历史 LoRA + critic 更新 | 是 |
| 可加载的公开训练 checkpoint | 否 |
| 大规模 main RL | 否 |
| 论文级 TTRL | 否 |
| 一个可扩展的研究原型 | 是，但必须先过后续页面的合同和评估门 |

## Nanoproof 的位置

本地 nanoproof checkout 是源码与数据 loader，不含已下载 training shard、checkpoint 或本地运行记录。它的 README 所述 20B math pretraining tokens、约 65M Lean-code midtraining tokens、约 260k LeanTree transitions 等是上游 pipeline 目标，不能作为本地 Reap 已完成训练的证据。
