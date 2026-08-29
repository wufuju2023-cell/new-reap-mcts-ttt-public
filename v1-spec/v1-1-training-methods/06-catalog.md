# 06 — 超参总表与产物目录（Catalog）

## 6.1 训练超参总表（单一真源，改此表→改代码→锁 config hash）

| 类别 | 参数 | 阶段 A | 阶段 B | 阶段 C |
|---|---|---|---|---|
| 模型 | 类/lora_r | 8B/32 | 8B/32 | 8B/32 |
| | lora_alpha | 64 | 64 | 64 |
| | lora_dropout | 0.05 | 0.05 | 0.05 |
| | 精度 | bf16 | bf16 | bf16 |
| 优化 | lr | 2e-4 (cos) | 2e-5 (cos) | α=3e-4 |
| | betas | (0.9,0.95) | 同 | — |
| | wd | 0.01 | 0.01 | — |
| | bsz×accum | 4×16 | 2×10 | 1 |
| | epochs/runs | 2 | 3 | ≤16 步/题 |
| 数据 | seq_len | 4096 | 4096 | 4096 |
| | 混合比 D0:D3 | 1:1 | — | — |
| | 组大小 G | — | 8 | — |
| 正则 | β_kl | — | 0.02 | 100 |
| | clip ε | — | 0.2 | — |
| | γ 折扣 | — | 0.99 | 0.99 |
| | 值头 lr | — | 1e-3 | 2e-3 |
| | TTT η | — | — | 0.3 |
| | TTT 每题步数 | — | — | ≤16 |
| 数值 | max_grad_norm | 1.0 | 1.0 | — |
| | seed | 42 | 42 | 题级 seed |
| | logprob 下限 | 1e-8 | 1e-8 | 1e-8 |

## 6.2 产物布局（统一 path_relative）

```
cfg/          configs：每种训练方式的 yaml + 生成的 config_hash；
data/         datasets.jsonl (D0/D1/D2/D3/D4) + 标记任务题池；
runs/<date>/
     variants_raw/typed/pool.jsonl   (D2 中间体)
     rollouts.jsonl (B: 每组 G 条)
     solutions.jsonl  verdicts.jsonl (D3/D4)
     ttt_metrics.jsonl (C)
     evals.jsonl  (step+epoch 分数)
     summary.json (该代元数据 + config_hash + 增益)
checkpoints/  P0_<ts>.safetensors(lora) / P1_gN_<ts> / 值头值
libraries/    growing_mathlib.lean + index.json
ttt_bank/     TTT adapter（不入训练，明确产物标签）
logs/         *.log
```

## 6.3 关键约定（防错）

1. `config_hash = sha256(json.dumps(hyperparams sorted))`，写入每个产物 JSON 头部（自监控）；
2. 每道 eval 题都有 `ttt:false` 标签；
3. 出现 `NaN`/`inf` 任何值 → 停止训练、保留失败现场（logs/）恢复；
4. 全部 job 以 `nohup`进 `/workspace/v1/logs/<job>.log` + 时间戳。（符合“可恢复、4 分钟预算命令”纪律——所有长任务拆步骤、每步幂等）
