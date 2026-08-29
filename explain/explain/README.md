# explain/ — 新架构分析归档

> 从对话/思考中沉淀的深度分析（按“严格专业语言”撰写）。每个文件 = 一个主题的完整论证链。

| # | 文件 | 主题 |
|---|---|---|
| 1 | `1-价值头的作用.md` | 价值头严格定义（MDP 嵌入 / PUCT / 稀疏奖励 / 与围棋胜率关系） |
| 2 | `2-hard-problem如何进步.md` | 极简 vs 极难问题：难度形式化、$\log B = \Theta(L^*)$ 指数、根本挑战 |
| 3 | `3-harness.md` | 数学直觉与外部知识：分拆“局部语义(NN) + 全局过程记忆(harness)”，人类研究放大判据 $d_g$ |
| 4 | `4-alpha-proof与智能体训练是否兼容.md` | MCTS-PV 与工具调用 agent 训练流程兼容性：off-policy/价值联合/三层桥接 |
| 5 | `5-alpha-as-Lean-coding-agent.md` | Lean 作为唯一智能体语言（$\Gamma \vdash P:\mathrm{Eff}\,R$、类型化观测、单语言闭环） |
| 6 | `6-meta-programming.md` | 元编程视角：同像性/语言塔(=库增长)/反射分层/自指不变量 |
| 7 | `7-reap-v1-v2.md` | Reap 多版本化：Core / Reap.Training(V1) / Reap.Agent(V2) |
| 8 | `8-v2-math-drive.md` | V2 训练主纲：数学驱动 agentic 技能涌现（终局裁判 / 工具仅证据 / 迁移指标 A-D） |
| 9 | `9-context-management.md` | 链式任务上下文：四类记忆、O(1) 窗口不变量、MemoRegistry 方案 |
