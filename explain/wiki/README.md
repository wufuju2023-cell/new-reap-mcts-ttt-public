# explain/wiki — Reap 双知页(Wiki)

> 面向 `/explain` 场景的**自包含知识页**：每页 = 一个完整主题，可直接引用、可独立阅读。
> 图片均摘自《Reap: Toward an Open AlphaProof》演示文稿（30 页，王语同 / PKU AI4Math × IQuest Research），
> 原片与深度归位见 `explain/`(分析归档) / `plan/`(研究计划) / `v1-spec/`(技术规格) / `discussion/`(讲义)。

## 阅读路径

| 心智模型 | 页面 |
|---|---|
| 我只有 5 分钟 | [00 什么是 Reap](00-what-is-reap.md) → [03 MCTS 核心](03-mcts-core.md) → [09 结果](09-results.md) |
| 我在做搜索 | [01 Lean 环境](01-lean-environment.md) → [03 MCTS 核心](03-mcts-core.md) → [05 Lean 原生](05-lean-native-search.md) |
| 我在做训练 | [02 搜索-数据循环](02-search-data-loop.md) → [04 训练目标](04-training-objective.md) → [07 模型与价值头](07-model-and-value.md) |
| 我在做工程 | [06 Rollout 管线](06-rollout-pipeline.md) → [08 分布式基础设施](08-distributed-infrastructure.md) → [11 仓库地图](11-repo-map.md) |
| 我在做研究 | [10 开放范围与下一步](10-open-and-next.md) → 深挖 `explain/` 1–13 分析归档 |

## 目录

| # | 页面 | 主题 | 图片 |
|---|---|---|---|
| 00 | [什么是 Reap](00-what-is-reap.md) | 问题动机 / 规模曲线 / 开放闭环三支柱 | deck-02/04/06 |
| 01 | [Lean 作为验证环境](01-lean-environment.md) | 证明状态·tactic·kernel / 判定分类 | deck-07 |
| 02 | [搜索-数据循环](02-search-data-loop.md) | AlphaZero 回路 / 搜索产生数据→数据改进搜索 | deck-08/09/10 |
| 03 | [MCTS 核心算法](03-mcts-core.md) | V 决定 Q / PUCT / AND-OR / 子目标独立 | deck-11/14/15/16 |
| 04 | [训练目标](04-training-objective.md) | replay targets / 策略 NLL / 价值分桶 CE / 三阶段管线 | deck-12/21 |
| 05 | [Lean 原生搜索](05-lean-native-search.md) | 外环 vs TacticM 内环 / 语义一致性 > 性能 | deck-17 |
| 06 | [Rollout 管线](06-rollout-pipeline.md) | 六步 / 失败分类 / 无假阳性奖励 | deck-18 |
| 07 | [模型与价值头](07-model-and-value.md) | policy head + categorical value head / 标量头训练 | deck-19 |
| 08 | [分布式基础设施](08-distributed-infrastructure.md) | Actor/Artifacts/Services / 协议约定 | deck-20 |
| 09 | [结果](09-results.md) | RL 增益 / pass@32 跨基准 / 战术精通 / 结构洞察 | deck-22..26 |
| 10 | [开放范围与下一步](10-open-and-next.md) | 已开放 / 未实现 / V1-V2 分层 | deck-27/28 |
| 11 | [仓库地图](11-repo-map.md) | 目录逐入 / 运行约定 / 本地检查 | — |

## 关键术语速查

| 术语 | 一句话 |
|---|---|
| **MCTS** | 蒙特卡洛树搜索：用访问统计把策略先验与验证器反馈融合 |
| **OR 节点 / AND 节点** | 单目标择一(OR) / 多子目标全解(AND)，AND 值 = 子目标最小值 |
| **PUCT** | $Q + c\,p(a\|s)\cdot\frac{\sqrt{N(s)}}{1+N(s,a)}$：价值 + 先验×探索 |
| **价值头 (value head)** | 预测"剩余临界路径步数"的回归头，不是胜率先验 |
| **RolloutSink** | 逐节点流式发射训练样本 (state, tactic, verdict, logprob, value) |
| **RTTT** | Rollout-time test-time training：搜索中在线更新 policy/value |
| **Replay** | 搜索成功后重建证明脚本，重放 + 内核终检后才计入奖励 |
| **塔上升 (Tower)** | V2 元层：验证入库 ⇔ 语言塔上升，仅换目标谓词不改算法 |

---

> 每页末尾附「溯源」：指向 `explain/` `plan/` `v1-spec/` 中对应的深度论述。
