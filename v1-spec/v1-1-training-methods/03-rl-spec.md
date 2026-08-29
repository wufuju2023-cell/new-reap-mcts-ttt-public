# 03 — 阶段 B：GRPO 详细规格

## 3.1 Rollout 数据生成（每代课程池 350 题）

| 参数 | 值 | 备注 |
|---|---|---|
| prompt | teacher 派生 variant `v`（已过闸门） | — |
| group 采样 | G=8 条 MCTS rollout / 题 | 组内同 prompt |
| MCTS 推进 | max_nodes=64, max_steps=64, n=6 | 与 v1-spec:02 一致 |
| 每题保存 | tree 快照 + `rollout.jsonl` | 含 state/tactic/old_logprob/verdict/value |

数据整合为训练 batch：
```
[{"group_id": "FATE-M/xxx#v1",
  "rollouts": [
     {"trajectory": [{"s","ctx","a","old_logp"}...], "reward": 1.0|0.0, "solved": bool, "value_seq": [...]}
  ]}]
```

## 3.2 GRPO 公式（实现细节）

$$ \hat A_g = \frac{r_g - \operatorname{mean}_{g'\in G} r_{g'}}{\operatorname{std}_{g'\in G} r_{g'} + \epsilon} $$

$$ \mathcal{L}_{GRPO} = -\frac{1}{|G|} \sum_{g=1}^{G}\frac{1}{T_g}\sum_{t}\Big[\min \big(\rho_{g,t}\hat A_g,\ \mathrm{clip}(\rho_{g,t},1-\epsilon,1+\epsilon)\hat A_g\big)\Big] + \beta\, \mathrm{KL}[\pi_\theta\|\pi_{\mathrm{ref}}] $$

- `ρ_{g,t} = π_θ(a|s)/π_old(a|s)`——**π_old 取 FastAPI server 返回的 logprob**（`Generator.lean` 语义完全一致）；
- ref：P0 的 adapter（保留完整）；`β=0.02` 固定梯度削减；
- `ε_clip=0.2`; `ε_std=1e-6`; 每 token advantage=group-level reward（稀疏）。

## 3.3 值头训练（与 GRPO 同时/前）

- 目标序列为蒙特卡洛 $\hat G_t$（与搜索同折扣 γ=0.99），用于值头 MSE：

$$ \mathcal{L}_V = \mathbb{E}\big[\tfrac12\,(V_\phi(s_t) - \hat G_t)^2 \big],\quad \phi\text{-LR}=1e-3 $$

- 时间对齐：先将 rollouts 里的 `(state, value_seq)` 与 GRPO batch 关联，按题序分窗口；值头更新每 200 GRPO 步一次（防止 noise）。

## 3.4 训练器

```
python -m trl GRPOConfig(
  model=P0_adapter, ref=base_model,
  rollout_data=<rollout.jsonl 分片>, beta=0.02,
  num_inner_epochs=3, batch=2×10,
  lr=2e-5(schedule cosine), max_grad_norm=1.0,
  eval_strategy=... (holdout-10 per 100 steps)
)
```

- **热重载**：每次训练后 `adapter_id=P1_g<hash>`；vLLM 无 batch 热重载 → 我们只重载 **transformers 单进程**（FastAPI 进程 restart 提供 `--reload` 场景）；训练结束暂停 rollout 1 分钟重载。

## 3.5 大小控制与安全性

- 若某 group 所有 rollout 均无解（reward 全 0），**丢弃该 group**（不产生 0 向量梯度）；
- `logprob` 截断：`log≥log(1e-8)` 前处理；分母极小加 ε；
- 每题 rollout 前 1 次**预热 call** (temperature=0.5，不记录) 用于 KV cache，提高并发。
