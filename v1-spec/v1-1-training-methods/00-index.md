# v1-1 · Training Methods — 训练方法详细规格

本目录为 `v1-spec` 的**训练方法展开**：SFT / RL（GRPO）/ TTTRL / 值头训练 / 课程回灌的具体执行规格——精确到数据集格式、损失函数、超参表、调度器、命名与产物布局。目标实例：AMD Radeon Cloud（W7900 48GB / gfx1100 / ROCm 6.x，SSH 直连，模板 788 HuggingFace，忽略其自带 repo）。

| 文件 | 内容 |
|---|---|
| `00-index.md` | 本页。训练总体时间轴与图 |
| `01-data-spec.md` | 数据集来源、清洗、格式、prompt 模板、缓存键 |
| `02-sft-spec.md` | 阶段 A：SFT 的完整配置（模型参数/优化器/loss/验证/checksum） |
| `03-rl-spec.md` | 阶段 B：GRPO 完整配置（rollout loop/importance/advantage/值头/正则/热重载） |
| `04-tttrl-spec.md` | 阶段 C：TTTRL（线上每题更新）的完整配置与安全规则 |
| `05-derive-update-scheme.md` | 三者如何组合/调度；每周节奏；A/B 矩阵；退出条件 |
| `06-catalog.md` | 全部超参清单（一个表）、命名约定、产物布局清单 |

---
## 训练时间轴（总图）

```
Week 0 (今日)     → 环境 up（SSH、模型拉取、server 启动、reap 编译、smoke test）
                 → 产生 baseline.jsonl (REAL-Prover-7B 原版 solve@16 / solve@64 on FATE-M-100)
Week 1           → A: SFT 混合（50k state_tactic_pairs + 阶段C回灌正样本）→ P0.
                 → E0: eval(A)-eval(baseline) 记录。
Week 2           → B: GRPO（rollouts on 课程池 P_g × G=8, 3 内部 epoch）→ P1.
                 → E1: 记录 solve@64 与 Δ(P1,P0)。
Week 2-3         → C: TTTRL on/off 对照；确认 ΣΔ 有效后常开（eval 集 off）。
Week 3+          → 循环：课程生成（DeepSeek ×1000）→ 闸门 → rollout → training → eval gate；
                  库增长 L_g 作为 context 注入 → 阶梯右移。
```

所有阶段产物严格按 `06-catalog.md` 命名，阶段间可中断续跑（checkpoint in 每阶段开头）。
