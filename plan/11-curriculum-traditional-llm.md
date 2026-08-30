# 11. 课程学习 + 变体逼近法（传统 LLM 管线，无 TTT/递归更新）

本页与 §05/§09/§10 的区别：**模型训练用传统三段式管线（pre-train → SFT → post-train），推理时参数完全冻结**。不做测试时训练，不做代际内在线更新。能力逼近 "难问题" 靠两样东西而非在线梯度：

1. **课程阶梯**：把难题 $p_*$ 拆成一族"刚够得着"的变体 \(\mathcal{V}(p_*) = \{v_1 \prec v_2 \prec \cdots \prec v_k = p_*\}\)，模型先解 $v_i$，数据攒够、权重更新后，再解 $v_{i+1}$；
2. **累积库（growing mathlib）**：每解出新的真定理 $t$，以 formal 形式追加进库 $L_{t+1} = L_t \cup \{t\}$；下一轮 SFT/后训练数据包含"用 $L$ 中的引理证明更难的定理"的轨迹 → 抽象能力随时间累积。

## 11.1 环路

```
┌────────────────────────────────────────────────────────────┐
│ 课程引擎（offline，批处理）                                    │
│  P_*：目标难题池（FATE-M / mathlib 未解定理 / 用户定理）          │
│    │  难度度量 Diff(p)（下面 11.2）                            │
│    ▼                                                         │
│  variant production：为每个 p_* 生成简化/相似变体  ⟵  LLM-gap 模型  │
│    │  过滤：well-typed + variant≈p_* 结构相似 + “刚够得着”         │
│    ▼                                                         │
│  当前可解阶梯 C_g = { v : Diff_g(v) ∈ [0.4, 0.9] }            │
│    │                                                        │
│    ▼  solver: reap 批量模式（§10 M9 的 Batch.lean）             │
│  proof 轨迹 → data pool D_g（含 正/负样本 + 库引理引用 trace）      │
│    │                                                        │
│    ▼                                                        │
│ 训练：SFT(D_g ∪ D_old replay) → ≤1 epoch lr 1e-5            │
│        （可选 post-train: GRPO=group-no-critic 或 DPO）        │
│    │                                                        │
│    ▼                                                        │
│ π_{g+1}（推理冻结参数）→ 重新标定 Diff_{g+1} → 阶梯整体右移          │
│ 解出的定理 → 写入 L_{g+1}（积累库）                              │
└────────────────────────────────────────────────────────────┘
```

## 11.2 难度度量与"刚够得着"变体

用当前模型 $\pi_g$ 在预算 $B_{\mathrm{low}}=16$ 节点的 solve@B：

$$\mathrm{Diff}_g(p) = 1 - \mathrm{solve@}B_{\mathrm{low}}(\pi_g, p)$$

变体 $v$ 由 **gap 方向**生成：沿"如何让 $v$ 与 $p_*$ 共享结构但更容易"的方向搜索。困难度值域 $(0,1)$；选择目标：

$$\mathcal{V}_g(p_*) = \{ v:\ \mathrm{Diff}_g(v)\in[0.5, 0.9],\ \mathrm{Sim}(v, p_*) \ge \tau \}$$

其中 $\mathrm{Sim}$ 是结构相似度（语句 AST 维度/常量替换项数，简单用：变体与目标共享的语法子串长度比）：

$$\mathrm{Sim}(v,p_*) = \frac{|\text{common AST subtree}|}{|\text{AST}(p_*)|},\qquad \tau \approx 0.7$$

直觉：模型恰好够不到 $p_*$（Diff 接近 1），只能够到类似但更简单的 $v_i$；**每个 $v_i$ 都带有其"梯子"上的后续目标 $\mathrm{next}(v_i) \in \{v_{i+1}, \dots, p_*\}$**，证明 $v_i$ 的抽象与引理可以直接复用。

### 生成算子（传统 LLM 都可以做，无需训练）

| 算子 | 例子 | 难度方向 $\nabla \mathrm{Diff}$ |
|---|---|---|
| 消去泛化词缀 | 把 `∀ x∈G` 实例化为 `x=1` | 降低 |
| 常数替换 | 难题的常量 → 数值 | 降低 |
| 引理外置 | `p_*` 已证的中间引理替换为假设 `h : lemma` | 降低（但 Sim 保持） |
| 假设增强 | 给变体加假设，便于用 simple tactics 结束 | 降低 |
| 反例变体 | `≤`换`≥` 等对称运算 | 等难度（相似变体，练泛化） |
| 反向算子 | 上述的逆（重新实例化/去引理） | 升高，用于逼近 $p_*$ |

生成器：用**任意 LLM**（甚至不用专属模型——传统方法也强调：这里 LLM 只是工具，不被训练）批量产出变体，Lean 编译过滤 well-typed，再 Diff 排序。备注：变体生成器可以就是"当前 LLM API"（如 deepseek/kimi 等通用模型），与要被训练的模型解耦。

## 11.3 累积库增长

定义库：

$$L_0 = \emptyset;\qquad L_{g+1} = L_g \cup \{\text{theorems } t : \text{proof verified by } \checkmark_{\text{kernel}}(t)\text{ at gen } g\}$$

- 证明时会生成"新引理"（reap 的 `checkProof` 产物是完整 script；把不依赖外部难题的定理以 `lemma` 形式登记）。登记到一个人工维护的命名空间（如 `RecursiveMath.<idx>`)，写进一个可检索的 Lean 文件库 `libs/growing_mathlib.lean` + 索引 JSON。
- **形态**：训练数据里，难题的提示词上下文带上相关库条目（复用 reap 的 `num_premises` 检索），所以 SFT 数据记录 `context: [库条目...]`——让模型学会"用引理"。
- **度量**：抽象深度 = 证明中引用库定理的次数 $\mathrm{depth}(t) = \#\{\text{库宣言 refs in proof}(t)\}$；库增长 = $\max \mathrm{depth}$ 随 $g$ 上升 = 模型"能力升级"的化身。

## 11.4 传统 LLM 训练（post-train 方式）

用户约束：**不使用 test-time update / recursive per-theorem update**。意味着：

- **SFT**：$D_g$（变体解 + 库上下文标注 + 旧 50k pairs replay 控制遗忘）

$$\mathcal{L}_{\mathrm{SFT}} = -\mathbb{E}_{(x,\mathbf{ctx}, a)\sim D_g \oplus D_{\mathrm{old}}} \log \pi_\theta(a\mid x,\mathbf{ctx})$$

- **post-train**（可选且“传统”）：GRPO（§05 公式）或 DPO/偏好对（成败变体成对构造），训练后部署，推理期零更新。
- 迭代节奏：每轮 $g$ 是**完整的训练周期**（新数据规模、固定 lr 计划），不是在线更新；难度阶梯是数据分布的变化，不是参数的变化。

数据规模预算表：

| 阶段 | 数据来源 | 样本量指示 | 估计机型 |
|---|---|---|---|
| SFT 0 | FrenzyMath/state_tactic_pairs | 50k | 1× 24GB GPU, 1 hr |
| SFT g≥1 主 | 变体证明轨迹（成功/失败） | 10k–50k/gen | 1× 24GB GPU, 0.5–2 hr |
| post-train | GRPO 群组回滚 | 200 道定理 | 1× 80GB 或分批 |

## 11.5 为什么"变体阶梯 + 库增长"有望逼近最终难题

1. **同分布转移**：$v_i$ 与 $p_*$ 结构共享；$v_i$ 解出的 proof 通常用到 $p_*$ 的解需要的抽象步骤。
2. **训练信号只会越来越好**：只要 $\mathrm{Sim} \ge \tau$，每代新增的轨迹都是"对准"目标的，不是随机数据。
3. **库是"外脑"**：证明难度本质上等于"需要引入多少中间引理"；变体阶梯提供入口，库增长提供中层构件——两者相加，难度单调收敛：

$$
d_{\text{resolved}}(g+1) \ge d_{\text{resolved}}(g), \qquad
d_{\text{resolved}} := \max\{\mathrm{Diff}:\ \text{proof found}\}

$$

4. **失败样本也有用**：把 $v$ 的失败 trial 与成功记录配对，形成传统 DPO/偏好数据（成功 > 失败）。

## 11.6 与 §10 的选择关系

| 方案 | 更新时机 | 机制 | 何时用 |
|---|---|---|---|
| §10 递归自改进 | 训练时 + 演化器 | 难题目进化 | 想快速增长、数据自动 |
| §09 TTT | 推理时在线 | 单题内参数调整 | 想低预算、每代间隔短 |
| **§11（本页）** | **训练时（传统）** | **课程变体 + 库增长** | **想做严谨的课程数据基线 / 对比实验** |

推荐：**先跑 §11 作为主实验**（可控、可复现、诊断友好），§09/§10 作为增强（若 §11 饱和再叠加）——这正与"用新数据集训练传统 LLM"一致。

## 11.7 任务清单 & 修改点

```
new-update-model/
├─ curric/ variants.py        # 变体生成+Sim+Diff 排序（LLM API 生成, Lean 编译过滤）
├─ curric/ ladder.py          # 每题维护 阶梯 skips & 阈值自适应（θ_lo/hi 自动调）
├─ curric/ lib_growth.py      # 证明核→growing_mathlib.lean + index.json（库追加）
├─ curric/ train.py           # SFT/GRPO（TRL）+ 每代 eval gate
└─ tools/                     # batch solver (M9)，ps_server 前端复用 §02
```

第一目标（M13）：在 FATE-M 子集选 20 道难题，各生成 20 个"刚够得着"变体，跑通 π_0 → SFT → π_1 → 难度再标定闭环，打印每代 $\mathrm{Diff}$ 分布。
