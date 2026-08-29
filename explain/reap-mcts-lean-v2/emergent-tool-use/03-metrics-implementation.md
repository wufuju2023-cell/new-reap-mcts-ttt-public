# 03. 指标与实现规格（可执行断言）

## 3.1 指标

| 记号 | 定义 | 期望/验收 |
|---|---|---|
| TheoremYield | $\lambda=\dfrac{\#\{\mathrm{Survivors}:\mathrm{gate}=\mathrm{ok}\}}{\#\mathrm{Survivors}}$ | $\ge 0.3$（$\mathcal{F}_k$ 内） |
| RefuteRate | $1-\sigma,\quad \sigma=\dfrac{\#\{\mathrm{Survivors}\}}{\#\mathrm{Candidates}}$ | $\ge 0.5$（劣质候选被过滤） |
| TowerDelta | $\rho\big(\Delta\tau_g,\ \mathbb{1}[c\ \text{入塔}]\big)$ | $>0$（因果链统计证据） |
| ConjQuality | $\mathrm{score}$ 分布（§2.4）右移 | 高分候选占比上升 |

## 3.2 `v2/mine.py` 实现规格

```
mine.py
├─ fit_polynomial(vals: list[tuple[int,int]]) -> Candidate
│     # O 上 k 阶多项式拟合（有限差矩阵；N_k ≤ deg+1）
├─ fit_linear_recurrence(seq) -> Candidate          # 前 k 项 + Berlekamp–Massey 或线性消元
├─ fit_algebraic_identity(vals) -> Candidate        # 双计数/系数比较安全类
├─ refute_search(candidate, O, m=64) -> (bool, 反例?)  # 穷举/邻域/对称约化
├─ classify(candidate) -> "F_k" | "F^c"            # 由生成的代数形式判定
└─ score(candidate, O) -> float                     # §2.4 公式（ρ_feas·(1−p̂_refute)）
```

接口约定：
- 候选结构：`{"kind": "poly"|"recurrence"|"identity", "coeffs": [...], "stmt": "Lean 串", "class": "F_k"|"F_c"}`；
- 全部为 DeterministicE 子类效果（进入白名单 v2/eff_registry）；
- Gate 仍为 `gate_lean`（容器 kernel）；非 $\mathcal{F}_k$ 的 Survivors 不送 gate。

## 3.3 与 V2 代码接入（增量点）

```
reap-mcts-lean-v2-code-1/v2/
├─ mine.py                # [新增] 有限插值 + 反例搜索 + score
├─ mcts_loop.py           # [改] 节点扩展新增 “mine” 动作类型：
│                          #     效果观测 H_obs → mine → candidate → refute → score
├─ eff_registry.py        # [改] 注册 mine 为 DeterministicE 白名单
├─ smoke_emergent.py      # [新增] 断言：
│                          #  ① poly 拟合：N=deg+1 点 → gate=ok 的定理
│                          #  ② recur：前 k 项 → 闭式（法 3）
│                          #  ③ 非安全类候选人 → 输出 score 且不送 gate
│                          #  ④ Δτ_g 与入塔的正相关（模拟 ≥20 步的统计）
└─ smoke_v2_full.py       # [改] smoke 清单包含 smoke_emergent
```

## 3.4 验收序

1. `python3 -m v2.smoke_emergent` 全过；
2. **TheoremYield ≥ 0.3**（在合成的 poly/recurrence 数据上）；
3. RefuteRate ≥ 0.5（注入反例构造的生成器）；
4. TowerDelta 测量（run ≥50 步，相关系数 >0）；
5. 与 v2 smoke_v2_full 兼容（无回归）。

## 3.5 因果与安全

- 仅 $\mathcal{F}_k$ 生成定理入塔；$\mathcal{F}^c$ 只出 "OpenConjectures.jsonl"（带 score 字段）；
- 禁止：把未证命题写进 $L$（$\mathcal{I}_{\mathrm{tower}}$ 扩展）；禁止：反例搜索失败即视为证明（必须 gate）。
