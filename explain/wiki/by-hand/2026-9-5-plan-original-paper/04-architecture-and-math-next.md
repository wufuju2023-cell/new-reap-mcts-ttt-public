# 04 — V1 架构与数学合同：保留、验证、扩展

V1 的 value contract 已经存在；下一步是冻结并验证它，不是把它替换成旧 scalar prototype。

## 1. 必须保持的 V1 合同

对任一 V1 categorical artifact：

$$
d\in\{1,\ldots,D\},\qquad
y=\mathrm{return}=-d,\qquad
k=d-1.
$$

head 输出 logits $z\in\mathbb{R}^{8}$：

$$
p_\phi(d\mid s)=\mathrm{softmax}(z)_d,\qquad
\hat d(s)=\sum_{d=1}^{D}d\,p_\phi(d\mid s).
$$

value endpoint 的数是正 expected distance；Lean / search 一侧把它映射到：

$$
V(s)=-\hat d(s).
$$

AND state 的语义是：

$$
V(s_{\mathrm{AND}})=\min_i V(s_i)
=-\max_i \hat d(s_i).
$$

这是 remaining critical-path distance。任何更换 head shape、support、decoder、Tanh/sigmoid/scalar 形式或 checkpoint schema 的修改，都是新的 artifact contract，不能静默兼容另一个 V1 snapshot。

## 2. 现有 V1 protocol 要测，不要假定

V1 runtime 已经具备 token-logprob、categorical value、LoRA/value joint update、snapshot / release 和 recovery 路径。下一轮应把这些已有能力做成可重复的 fixture：

| fixture | 必须验证 |
| --- | --- |
| policy token scoring | tactic 的 token 序列、EOS 边界、总 logprob 与 teacher-forced scoring 一致 |
| value decoding | 固定 logits 的 expected distance 与 Lean 侧负号相同 |
| trajectory target | terminal、OR action、AND split 的 return / class 正确 |
| release loading | adapter、head、base contract、support 与 tokenizer 都一致 |
| isolation | 新 session 使用 release，旧 session 不被新 learner update 改写 |

这些是 compatibility tests，不是另起一套模型设计。

## 3. 当前 support 的真实风险

uploaded full-v3 support 是 $1,\ldots,64$；本地 R2 support 是 $1,\ldots,8$，且最近两批只观察到距离 $1,\ldots,4$。因此最先要测的是：

1. predicted distribution 是否在 seen classes 外无意义地饱和；
2. 距离超过 8 的真实 trajectory 如何被明确拒绝、统计和报告；
3. 扩大 support 是否会改变 checkpoint shape、class mapping、loss 与 search decoder。

若要扩至 $D>8$，应发布新的 V1-compatible-next contract：

- 新 head shape；
- 新 dataset support / overflow rule；
- 新 checkpoint schema / migration decision；
- uploaded full-v3 与 R2 baseline 都保留不变；
- 统一 holdout 下的 $D=64$、$D=8$ 与新 artifact 的 ablation。

不能只改一个 max-distance 参数，然后把旧 artifact 当成新 head 加载。

## 4. 模型共享的边界

“value 和 policy 共享 7B”并不意味着所有参数都以相同方式更新：

| 参数组 | V1 状态 |
| --- | --- |
| REAL-Prover 7B base | 冻结 |
| LoRA adapter | policy loss、KL 与 joint learner update 会改变 |
| categorical value head | categorical CE 会改变 |
| optimizer / RNG / buffer | learner 私有，不随 release 直接继承到新 search session |

这给了 V1 一个清晰的实验单位：release 是 adapter + head，base 是固定环境。任何 future result 都应标明这三者的 identity。

## 5. 与 AlphaProof 的数学对齐

AlphaProof 论文的关键不是“必须用某个 bin 数”，而是：

- value 是剩余 proof work 的分类分布；
- AND backup 对应 hardest subgoal；
- value 和 policy 共同引导 search；
- 训练标签由 formal verifier grounding。

V1 已满足这些语义骨架。下一步的数学问题是估计误差、support coverage 和 search usefulness，而不是重新命名 value。
