# 02 — 阶段 A：SFT 详细规格

## 2.1 起点与预算

| 项 | 值 |
|---|---|
| 起点 | `FrenzyMath/REAL-Prover`（Qwen2.5-Math-7B 微调）BF16 |
| 训练参数 | 仅 LoRA 适配器（r=32, alpha=64, dropout=0.05, 全部 attn+mlp 模块）+ 可选 embedding 矩阵 |
| 数据混合 | D0(50k) ⊕ D3(本阶段≥5k)；每 batch 采样 1:1 |
| 距离检查 | 每 epoch 结束跑 eval（P0 的 holdout-30 初始分数） |

## 2.2 损失

$$ \mathcal{L}_{SFT} = -\mathbb{E}_{(x,\mathrm{ctx},a)\sim \mathcal{D}}\ \sum_{t}\ \log\pi_\theta(a_t\mid x,\mathrm{ctx},a_{<t}) $$

**weight 规则**（`w` 字段）：
- $w=1.0$ D0/D3 正样本（kernel 验证通过）；
- $w=0.1$ D4 负样本（仅作为“不该给出”的负样例，D2 错误 case 共享；公式同 — 用户侧 TTT 为负向偏好，SFT 不用负样本）；
- 计划：**D4 仅用于 TTTRL/DPO（§05）**，A 阶段只吃正样本。

## 2.3 训练器配置（TRL SFTTrainer 或原生 transformers + accelerate）

| 超参 | 值 | 备注 |
|---|---|---|
| optim | AdamW (betas=(0.9,0.95), weight_decay=0.01) | BF16 |
| schedule | cosine, wd 0.01, max_lr=2e-4, min_lr=1e-5 | — |
| epochs | 2（A 阶段） | 过拟合 gate |
| batch | 4 × grad_accum=16 → ef batch 64 | 48GB 放得下 4096 seq |
| max_seq_len | 4096 | 截断 |
| lora r/alpha | 32 / 64 | — |
| 数值 | bf16=1, gradient_checkpointing=1, offload 无 | — |
| eval | 每 500 步 eval holdout-10（stub） | 预置 |
| 存储 | checkpoint 每 1000 步 1 快照；全量每个周期保存 | 磁盘 ~200GB（预留） |
| 随机种子 | seed=42；Sampling ratio D0:D3=1:1 | 记录 config 哈希 |

## 2.4 验证协议

1. 训练前 smoke：`lake env lean test/trivial.lean` 通过；
2. 每 100 步：生成 eval-10 题目 10 条（低预算 nodes=16），打印 $\Delta$ 曲线到 `evals.jsonl`；
3. epoch 结束：`holdout-30`（防泄漏纪律的 first value）+ 提示下一个跑法。

## 2.5 产出

```
checkpoints/P0/<timestamp>/(adapter + config.json + metrics.jsonl)
```

- P0 是唯一从 REAL-Prover 起始的 checkpoint → **永久保留**；
- 若 P0 无法提升 ≥0（比原版 7B 差 5% 以上）→ 回退 base，先只跑 D0（不开 D3）。
