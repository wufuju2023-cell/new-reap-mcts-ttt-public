# 05 — 三阶段组合与调度（Derive & Update Scheme）

## 5.1 调度优先级（按信息量）

1. **TTTRL（C）**：最便宜、最贴近"比赛回路"，先用它来提高 π（默认白天实时跑）；
2. **GRPO（B）**：批处理夜间跑（3 epoch），产出 P1_g 的"大版本"；
3. **SFT（A）**：仅当 base 明显不足（P0 固化）重新开；或成批数据 D3 猛增时（>50k）做一次 refresh。

## 5.2 每日动线（SSH cron，从实例 root 运行）

```bash
00:30  teacher 出题 1000 (DEEPSEEK_API_KEY)          → variants_raw.jsonl
01:00  G1 lean compile gate                            → variants_typed.jsonl
02:00  G2 diff标定 (B=16) + G3 sim                     → variants_pool.jsonl (≤350)
03:00  backup: sync checkpoints/ to /workspace/archive/ (tar.gz)
04:00  rollout group (G=8 × pool ≤350)                 → rollouts.jsonl
07:00  GRPO train (3 inner epochs)                     → P1_<hash>
08:00  eval gate (holdout-30; 若负向 → 回滚 P1_prev)
09:00  summary.json + 告警（电报/邮件可后续接）
```

**TTTRL 白天**：随时对新生成的“阶梯 next”跑（相当于比赛内）。

## 5.3 A/B 矩阵（按周划分）

| 周 | A路径 | B路径 | C路径 | 决策 |
|---|---|---|---|---|
| W1 | baseline REAL-Prover-7B | ✓ A=SFT(D0+D3) | TTT off | eval 表 |
| W2 | 上者 | B=GRPO(P0) | TTT off | 全链增益 |
| W3 | 上者 | B 固定 | **TTT on (chain)** | P2增益 |
| W4 | B+C 最优组合 × 库增长 L_g | 回灌 D3+SFT refresh | 关闭复演 | 收敛 |

## 5.4 退出/自我检查条件

- train 与 eval 同时单调提升（每代） → 继续；
- holdout-30 连续 2 代负增 → 减课程难度（θ_lo ↑）或暂停 teacher（回归基准）；
- GPU 显存不足错误 → 降 batch；磁盘低 → 删旧 runs（保留最新 10 期 + checkpoints 所有 P0/P1)。

## 5.5 文件布局与版本号

```
/workspace/v1/
├ runs/<yyyymmdd>/              # 每期
├ checkpoints/P0.<ts>  P1_g.<ts>  ...  # adapter 全长
├ tt_corpus/ttt_bank/           # TTT 派生（不混训练）
├ libraries/                    # growing mathlib
└ logs/ (main.log, train.log, server.log, run_summary.json)
```

版本命名：`<ALGO>_<g>`（如 `P1_g3`），git 上记录一次 commit + link。
