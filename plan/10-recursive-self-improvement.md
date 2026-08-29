# 10. 递归自改进 (Recursive Self-Improvement)：让 reap 自我迭代

把 §05/§08/§09 组装成一个**能自己产生更难任务**的闭环：模型 $\pi_g$ 用 reap 解一批问题 → 验证过的证明变成训练数据 + 用于生成（演化）更难的新题 → 训练出 $\pi_{g+1}$ → 下一轮用 $\pi_{g+1}$ 解更难的问题。代数越高，模型越强，任务同步变难——这就是 Seed-AI / AlphaProof-style 的 "seed-growing" 环路，套用到 Lean 上。

## 10.1 环路总览

```
        ┌──────────────────────────────────────────────────────┐
        │  Evolution (演化器)                                    │
        │  from proved theorems → mutate →  well-typed 检查       │
        │  → 难度分层 → 下一代的题目池 P_{g+1}                      │
        └───▲────────────────────────────────────────────────────┘
            │ 难但可解的新题
            │
┌───────────┴──────────────┐     rollout+verdicts      ┌──────────────┐
│ Solver（复用 reap）        │ ───────────────────────▶ │ 数据 & 训练器    │
│ π_g × MCTS × Lean 验证    ├──────────────────────────│ (08 后训练/09 TTT)│
│ 解 P_g（含 TTT 在搜索中更新）│     验证过的证明脚本        └───────▲──────┘
└───────────▲──────────────┘  ────────────────────────·──────┘
            │ 服务最新权重 θ_{g+1}                        │
            └────────────────────────────────────────┘
```

## 10.2 三个组件

### (1) Solver：批量版 reap

现状 `reap!!` 依赖编辑器 widget，脚本模式用的是同一函数 `Reap.TreeSearch.reapMCTS`（`Tactic/TreeSearch.lean:624`）——它在解出后直接 `replaySolvedNode + checkProof`，成功后当前目标就闭合。修改点：

```diff
# 原逻辑：证明脚本只通过 InfoView 展示
# 新增：验证通过后，把脚本 JSONL 输出（每个 theorem 一行）
+ Reap/Tactic/TreeSearch.lean: 在 runMCTS 成功分支写
+   {"theorem": "...", "script": "...", "tree":...} -> solutions.jsonl
+ 新增 Reap/Batch.lean：
+   - 读题目列表，循环执行 "setGoals [goalMVar]" + reapMCTS
+   - 每道题加 trace 标记 / 写 return code，
+     由 Python 侧 `lake env lean batch.lean` 判定 solve@B
```

求解器输出两类信号：(a) **解出的** script（正样本）；(b) **没解出的** 失败 trace（负样本 + 难度信号）。

### (2) Evolution：从已证明定理生成更难定理（本功能的"递归"核心）

对每个解出的 theorems（含 mathlib/用户定理），用策略化变异生成候选新题 $p'$：

| 变异算子 | 例 |
|---|---|
| 常量→变量 | `2 * n = n + n` → `a * n = n + a` 抽象 |
| 断言弱化/推广 | 定理成立域扩到 Semiring/Group |
| 复合 | 把两个证明接起来的中间引理抽出来 |
| 对偶/反例变体 | `≤`→`≥` 或交换量词 |

两道过滤门槛（都调 Lean）：
1. **well-typed**：$p'$ 通过 `#check`/`example` 编译（语句合法、不需要证明还没引入的引理）。
2. **当前代难解**：用预算 $B_{\mathrm{low}}$（比如 16 节点）测

$$\mathrm{Diff}_g(p') = 1 - \mathrm{solve@}B_{\mathrm{low}}\big(\pi_g, p'\big)$$

只保留 $\mathrm{Diff} \in [\theta_{\mathrm{lo}}, \theta_{\mathrm{hi}}]$（太难→几乎解不出，浪费；太容易→无信息量），形成难度分层：

$$P_{g+1} = \{p' : \mathrm{Diff}_g(p')\in[\theta_{\mathrm{lo}},\theta_{\mathrm{hi}}]\}$$

给每一代都留一个"分层池"，让新模型从 $\text{Diff}\approx 0.5$ 开始（"just beyond" 原则——像 AlphaEvolve / Seed-AI 的难度-分层）。

### (3) Trainer：就是把 §05–§09 串起来

- 对 $P_g$ 求解后拿到 `solutions.jsonl`；
- 每代训练：**continue-SFT（§08，旧 50k + 新解，各 1:1）** 做一个版本，接着 **GRPO（§05）** 或直接用 **TTT（§09）**；
- 关键点：新代解法只回放 *kernel 验证过* 的，失败样本进 TTT/负采样；
- 每次训练结束做 **eval gate**（固定 30 题 holdout），solved 数不降才继续递归。

## 10.3 递归的机制与安全

定义代际 $g$，衡量"智能增长"：

$$S_g := \text{generation 求解率曲线 }\ \mathrm{solve@}B\ \text{with}\ \pi_g$$

- **单调性检查**：$\max_p \mathrm{Diff}_{g}(p) > \max_p \mathrm{Diff}_{g-1}(p)$，即下一代需要能解上一代"最难题"，否则环路退化（没有新训练信号 → 递归停止）。
- **防遗忘/防漂移**：每代改 $KL(\pi_g\Vert\pi_{g-1})$

$$\text{KL}_g = \mathrm{KL}\big[\pi_{g}\|\pi_{g-1}\big] \le \kappa$$

- **evaluation 隔离**：固定 eval 集与演化题池**完全分开**，演化出的题绝不进 eval；否则"递归自改进"曲线成为假象。
- **世代成本**：每代 ≈ 新题池规模 × (解算 + 训练) 的一次性成本；观察收益递减时停止。

## 10.4 风险与应对

| 风险 | 应对 |
|---|---|
| 演化题全部过难/过易，池子空 | 动态调 $\theta_{\mathrm{lo}}$，回退到"概率最大的变异算子"加权抽样 |
| 模型退化（演化出的题崩坏） | KL 约束 $+$ eval gate $+$ 每代保留 checkpoint |
| 泄漏/污染（演化题在 eval 中） | 题目命名空间隔离，eval 从冻结表加载；演化池含 hash 检查 |
| 递归收益递减 | 每代记录 $\mathrm{Diff}$ 分布 + solve@B 曲线；连续两代无进步 → 换协议（如加大预算/更强制演化逻辑），或停止 |

## 10.5 修改清单（基于当前 repo）

```
repo/
├─ Reap/Tactic/TreeSearch.lean   # [+rowtree 输出 & runMCTS 的 proof script 同步给 batch]
├─ Reap/Batch.lean               # 新增：list-of-theorems 批量 solver（无 UI 依赖）
└─ new-update-model/
   ├─ sgd/  evolution.py         # 变异+well-typed+Diff 排序（调 lean 编译）
   ├─ sgd/  loop.py              # 世代总控：solver→train→evolve→eval gate
   └─ tools/ttt_server.py        # §09 的适配器服务器（peft-即时梯度 + chat 协议转发）
```

阶段顺序（在 §07 基础上加）：

| Milestone | 内容 | 预计 |
|---|---|---|
| M9 | Batch 模式 reap：`Batch.lean` 无 UI 跑题池，输出 `solutions.jsonl`（这一步几乎零学习成本，先做） | 0.5 d |
| M10 | Evolution v1：常量→变量 + well-typed 过滤 + Diff 排序（窄算子在 FATE-M 子集） | 2–3 d（需 GPU 跑 Diff 度量） |
| M11 | 环路闭环：$\pi_{g} \to P_{g+1} \to \pi_{g+1}$，含 eval gate 与 KL 约束 | 5–7 d |
| M12 | 自我改进曲线报告（solve@B per generation） | 2 d |

## 10.6 结论

- **不需要改 MCTS 本身**——"递归自改进"发生在 MCTS 之外：证明脚本被演化出的更难题目 *重新验证*，强化模型与题目难度双轴上升。
- **先做 M9（Batch 化）**：现有代码支持，改 20 行；之后每一步都是增量，可回滚。
