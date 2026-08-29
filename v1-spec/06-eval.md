# 06 — 评估协议

## 6.1 指标

- **Primary**：$\mathrm{solve@}B$ —— 在固定题集（FATE-M 100 test + 30 holdout）下，每道题得最多
  $B$ 节点（默认 64）内成功（proof 由内核通过视为 solved）的命题占比。

$$\mathrm{solve@}B=\frac{|\{p:\ \exists \text{ kernel-verified proof within }B\ \text{nodes}\}|}{|\mathcal{S}|}$$

- **Value**：$\mathrm{val}_{\mathrm{corr}}$ —— $V_\phi(s)$ 与真实"是否被解出"的 Pearson/AUC（值头诊断）。
- **归一成本**：每 solved 题平均 GPU-min 及每题 token 消耗（API 成本报告）。
- **课程效度**：$\overline{\mathrm{Diff}}(\pi_g)$ 变化率 = 模型"知识面"扩广指标。

## 6.2 eval 集合固定（三套，防泄漏）

| 集合 | 来源 | 用途 |
|---|---|---|
| FATE-M-test（100） | REAL-Prover 官方 data/fate_m.jsonl 随机抽 100 | 主 eval |
| holdout-30 | 手工挑选 + **明确排除课程/演化池** | gating（每代） |
| in-distribution-curriculum-20 | 课程池中的题目（用于测量"训练中是否学到"） | 诊断（上界） |

- 所有 eval 程序：**关闭 TTTRL、关闭 adapter 记忆重启、非演化源自同一 policy**；
- 序列化：`evals.jsonl`（每条记录 参数版本 hash+日期+curriculum 阶段）。

## 6.3 消融矩阵（每组合跑一次，每次 ~2 GPU-h）

| 组 | policy | value | TTT | 目的 |
|---|---|---|---|---|
| A1 | P0(SFT) | - | off | 基线 |
| A2 | A1 | MLP头 | off | 值头收益 |
| A3 | P1(GRPO) | MLP头 | off | RL收益 |
| A4 | A3 | MLP头 | on | 完整 v1 |
| A5 | A3 | LLM-JSON | on | 值头 vs LLM值对照 |
| A6 | 无G1-G3课程（直接抛随机难） | - | off | 课程三闸门的价值 |

核心报告：
- $\mathrm{solve@64}(A4)-\mathrm{solve@64}(A1)$ = 全链增益；
- A5 vs A4 = 值头价值；A6 vs A2/A3 = 课程过滤器贡献。

## 6.4 每条结果格式

```json
{"eval":"FATE-M","date":"2026-08-26T00:00:00Z","weights":"P1g_<hash>",
 "ttt":false,"variant_pool":"hg03","solved":68,"total":100,
 "mean_nodes_to_solve":31.2,"mean_wall_ms":422000,"config":{...}}
```

## 6.5 声明纪律

- 不把被 TTT 用过的同题样本作为正式 eval（每条 eval 跑在冻结权重的白盒检查上）；
- 泄漏检测：Cron 每次训练后 `solve@B(holdout-30)` 保持不变或上升，若下降>15% 暂停课程生成。
