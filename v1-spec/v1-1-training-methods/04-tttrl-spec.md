# 04 — 阶段 C：TTTRL（Test-Time Training on Rollouts）详细规格

对应 AlphaProof 比赛回路：**搜索期间对当前题目在线更新参数**；v1 实现 = “per-theorem LoRA” +(可选 adapter 记忆)。

## 4.1 触发与节流

| 项 | 值 |
|---|---|
| 触发 | 每个节点 verdict 之后（或每次 `evalPolicyValue` 返回后） |
| 单步更新阈值 | 每次都试 → 资源可控；默认每节点 1 步，每题 ≤16 步 |
| 工具 | `/ttt/step`（FastAPI 内 forward+backward on LoRA head） |
| 单步代价 | 1× (forward+backward) on 7B < ~1.2s (48GB 卡) → 每步挂载：±2s 算可接受 |
| 节流条件 | 若 `|Δlogp(当前 tactic) − 同分布| < 0.05` 或 value 变化 <0.01 则跳过 |

## 4.2 更新规则

**Policy**（on-policy REINFORCE + KL 锚）：

$$\theta \leftarrow \theta - \alpha_{\mathrm{ttt}}\, \nabla_\theta\big[-\hat r(s,a)\cdot \log\pi_\theta(a\mid s)\big] + \alpha_{\mathrm{ttt}}\beta_{\mathrm{ttt}}\,\nabla_\theta \mathrm{KL}\big[\pi_\theta\|\pi_{\mathrm{base}}\big]$$

其中

$$\hat r = +1\ (\text{solved}),\quad -\eta\ (\text{error/timeout}),\quad 0\ (\text{ok-不闭合}),\quad \eta=0.3, \quad \alpha_{\mathrm{ttt}}=3\times10^{-4},\ \beta_{\mathrm{ttt}}=100$$

**Value**（TD）：

$$\phi \leftarrow \phi+\alpha_V\big(\hat r+\gamma V_\phi(s')-V_\phi(s)\big)\nabla_\phi V_\phi(s),\quad \alpha_V=2\times10^{-3}$$

## 4.3 参数隔离与记忆

- 每题 launch 时从 `P1_base` 复制 LoRA 参数；
- **三档记忆策略**：
  1. `fresh`（默认）：每题起点=P1；题解完成即丢弃；
  2. `chain`：同一 `p_*` 阶梯的相邻变体间延续 adapter（强烈推荐，AlphaProof 的变体链同款）；
  3. `bank`：将 24h 内所有成功的 adapter 存 `ttt_bank/<task>/`，遇到同类 state 继承（可选——v1 先不做，留 v2）。
- **安全**：进入 eval 集前销毁一切 adapter；TTT 不许生成正面奖励用于 `D3` 之外的论文数据（明确标注 `ttt=True` 的数据不允许混合进 A/B 训练集）。

## 4.4 TTTRL 目标监控

- 每题记录 `ttt_metrics.jsonl`：起始值 $V_0$、第 $k$ 步 value、增量、是否 solved、更新步数。
- 跨天检查：TTT 增益指标 `ΔTTT = solve@B(ttt-on) − solve@B(ttt-off)`（同 eval set，两法对称）> 5pt 才算 TTT 有贡献。

## 4.5 危险与规则

1. **样本污染**：绝不在同一题目上进行 eval + TTT（必须重置 server adapter_id 或停机重载 base）；
2. **循环退化**：连续 3 题 TTT 后 KL(π_θ‖π_1) > κ=0.15 时，停止 chain（只允许 fresh）；
3. **崩溃恢复**：每题结束执行 server `/ttt/reset` → 回到 P1_base（如失败重试 3 次）。
