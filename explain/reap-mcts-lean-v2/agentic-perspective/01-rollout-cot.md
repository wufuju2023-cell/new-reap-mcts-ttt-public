# 01. agent rollout & chain-of-thought（v1/v2 的严格定义）

## 1.1 术语再定义（与 LLM agent 用词区分）

- **rollout**（我们）：`环境转移的树展开`（或“单轨路径”）。动作=类型化 Lean 项（tactic/函数/工具调用），
  转移=执行器 $\Xi$（Lean kernel 校验、Python 计算、检索、训练 worker）返回**类型化观测** $o$。
- **chain-of-thought（CoT）**（我们）：**不是自然语言中间步骤**，而是
  - v1：树的展开历史（$\{s_0,a_0,s_1,\ldots\}$ 的多分支森林，含每步 verdict）；
  - v2：值估计轨迹（每节点 $V_\phi(s_t)$、搜索回传 $Q$）——**“思考”是机器验证过的形式对象与标量值**。

## 1.2 v1（CPU MCTS agent rollout）

```
rollout(题 P) =
  s0 = (parser ctx, env L0, obs=∅)
  loop while budget:
    π(s): 采样 k 个类型化动作 a（Lean tactic / 工具 Effect 项）
    for a in top-k: T(s,a)  =  Lean/工具执行 → o（ok|error|parse|timeout|副作用结果）
                        └─ verdict 即环境反馈（含 kernelCheck 终局）
    树展开 & PUCT 选择（先验×价值）
  终止：kernel 闭环（replay）或预算耗尽
  产物：sink JSONL（node/task/rttt 事件）+ solutions/failures
```
- **CPU 侧无在线参数更新**：只生成数据与信号（“信号机器”=10 的定位）。
- **tool use 的形态**：Lean 端 Effect 项（$P: \Gamma \vdash P: \mathrm{Eff}\ R$）——类型检查器是动作合法性的**零容忍过滤器**（5 的收益 1）；结果以类型化值回流（收益 2）。

## 1.3 v2（GPU，在线 P-V-TTT agent rollout）

```
rollout(题 P)` = v1 展开 + 在线环:
  每个/每 k 个节点事件 → buffer (s, a, r, logp_old)
  → ttt_step:  策略 LoRA 一步（REINFORCE+KL 锚）
              → 价值头 TD: V_φ(s) += α_V(r + γV_φ(s') − V_φ(s))
  → 下一节点选择使用**已更新**的 V/π（边做边学）
  → 每题结束: adapter snapshot/rollback 保护
```
- **agent 的“认知”= 树搜索 × 在线梯度**：TTT 使 rollout 与学习同环（4 与 10 的“MCTS 事件发生器”）。
- 与 **Mutanov/OpenR 型 test-time RL** 一致：无需离线 RL 循环，价值/策略在**调用期内**进化为问题专用化（hindsight 自适应）。

## 1.4 CoT 的工程可测性（本管线的独特优势）

| 项 | LLM agent CoT | 本管线 CoT |
|---|---|---|
| 中间步可验证 | 部分（单元测试） | **全部**（每步 verdict + kernel） |
| 中间步可追溯 | 文本日志 | 结构化 JSONL + 重建树（raw_tree） |
| 价值中间量 | 无 | 每个节点 $V$、每条边 $Q$、$\gamma$ 回传 |

> 结论：**rollout/CoT 在本管线是“机器可读的正则数据结构”**，其生成者是搜索+执行器，而非模型写作。
