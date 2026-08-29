# 02. 下一切片实现规格（mine-policy 档）

## 2.1 组件

```
v2/mine_policy.py        # MineGen_ψ 的 policy/value 客户端（复用 PolicyClient/mock | GPU）
v2/mine_events.py        # miner 事件协议：
#   (obs_set, candidate, verdict ∈ {ok, refute, open}, kl)
#   → 与 ttt_step 同构（k 事件缓冲 → 单步梯度 → 热更新）
v2/mcts_loop.py          # [改] 增加 "mine-select"/"mine-fit"/"mine-refute" 元动作族
v2/mine.py               # [保留] 确定性层（F_k 判定/Refute/score）——作为 gate 结构
v2/smoke_joint.py        # 双任务联合冒烟
```

## 2.2 动作/特征/奖励

| 项 | 规格 |
|---|---|
| $\mathcal{A}_{\mathrm{mine}}$ | `mine-select(k, window)`（选 O 子集）、`mine-fit(family)`（有限差/递推/符号匹配）、`mine-refute(m)` |
| 状态特征 | $H_{\mathrm{obs}}$ 统计矩、有限差表、$\log|O|$、塔深度直方图 |
| 奖励 | 仅 $\mathbb{1}\{\mathrm{gate}(c)=\mathrm{ok}\}$（+0.5 型）；refute→负信号（-0.2）；open→0.05 只计分 |
| TTT | 与证明档同一 `/ttt_step`：$(s,c,\mathrm{verdict},\mathrm{kl})$ 事件队列，k≥8 触发 |

## 2.3 指标（扩到 miner 面）

$$
P@k = \frac{\#\{c\in \mathrm{top-}k:\ \mathrm{gate}=\mathrm{ok}\}}{k},\quad
\mathrm{RefuteRecall} = \frac{\#\{\text{被反例击中的劣质候选}\}}{\#\text{全部劣质候选}},
\quad
\lambda = \frac{\#\mathrm{gate}=\mathrm{ok}}{\#\mathrm{Survivors}}
$$

验收：合成集 $P@k\ge0.3$、$\mathrm{RefuteRecall}\ge0.5$、$\lambda$ 随代际不降、TowerDelta>0。

## 2.4 双档冒烟断言（smoke_joint）

1. 证明档 smoke_v2_full 无回归；
2. mine 档：mock O（立方和/费波那奇/素数间隔）→ select/fit/refute 链路各 10 步 → 记录 $\lambda$、P@k；
3. 联合：共享 tower 的 joint 运行（α 课程递减验证——α 逐代减少，命中率单调上升）。

## 2.5 界线（代码内强制）

- `gate`/`refute` 永不接收梯度（无 learnable 参数）；
- `OpenConjectures.jsonl` 只写不读入训练（flag `--allow-open-in-grad` 需显式+警告）。
