# 03. miner-trained / deterministic-miner / no-miner（三态与推荐）

## 3.1 定义（“miner” = 新任务/困难的挖掘器，即“从哪来下一批数学题”）

| 态 | 描述 | 监督来源 | 优点 | 风险 |
|---|---|---|---|---|
| **no-miner** | 只从固定题目池/自采样 rollout；不做任务挖掘 | 外部给定 | 简单、无新假设 | 难度被池子锁死；技能收敛快、上限低 |
| **deterministic-miner** | 规则化的挖掘/演化器（常量→变量、引理外置、库索引扩展、难度阈值过滤） | 固定规则（可审计、可复现） | 课程可控、稳定、零训练成本 | 演化多样性受限（难以发现“跨域巧变”） |
| **miner-trained** | 可训练挖掘器（== 教师/演化器模型，§12 teacher 或元 RL） | 目标策略/验证器回注（mined 题被迭代改善则 reward） | 自动发现更优课程（技能涌现通道） | 训练成本+稳定性（生成退化需冷却/监督） |

## 3.2 与我们其它文档的映射

- deterministic-miner ≙ `teacher 生成 `刚够得着` 变体`（Diff∈[0.5,0.9]，Sim≥0.7）——§11/§12 课程的**规则版**；
- miner-trained ≙ teacher 经过 B 数据 DPO 后训练——§12 的**学习版**；或 RL 化 Evolution（§10）；
- no-miner ≙ `v1 batch 直接用 FATE-M 池` + RTTT（我们 V1-1 已做的形态）。

## 3.3 演进路线建议（reap-mcts-lean-v2 主纲）

```
M1（现 V1-1 主态）： no-miner          —— 先证明“信号闭环”可行
M2（V2 前段）   ： deterministic-miner —— 可控课程（规则挖掘+难度分层）→ 提升解率/技能利用率（§8 的 Diff 指标）
M3（V2 后期）   ： miner-trained        —— 把“挖掘”本身做进技能（RL 课程学习）
                                           判定指标：mined-题解率 提升 & 工具使用迁移（§8 A/B/C/D）
```

## 3.4 一条**可与 agentic 视角合并**的结论

- **mined 的题目 = 难度-层的 agentic 任务**：depth_ladder 越高，需要的 skill 组合越完整（实验→检索→规律→证明→验证→进一步证明）——miner 控制的是 agentic 技能的**暴露密度**（§8：任务的“技能需求密度”成为自动课程）。
- 因此三态的差别**不只在数据**，而是 **agent 能力曲线的节奏器**：no-miner=平滑爬坡；deterministic=阶梯锁定；miner-trained=自适应爬坡。
- 合规的红线：miner 生成任务也走同一道**验证门**（kernel/反例）——不引入不可验证的“软目标”（§8：唯一正式终局裁判=数学）。

## 3.5 V1/V2 内的落地接口

- Lean 侧：`Reap.Training.BatchSolver` 增加 `--pool <no|det|learned>`（no=file池；det=规则演化脚本（evolution.py，v1-spec 10 一节）；learned=teacher API 生成，回注 feed）。
- 指标记录：每代输出 `diff_hist`、`mined_solve_rate`、`skill_usage`（§8 的用法分布），并用 `02-vs-llm-agent §2.4` 的综合指标注册表沉淀。
