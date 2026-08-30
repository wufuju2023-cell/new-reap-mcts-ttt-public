# ds-1：InternLM2.5-StepProver-Critic 作为值网络 V(s) = −d\*(s) 的可行性评估与改造规范

> 标题：**Existing 值网络能否直接用？**
> 依据：arXiv:2410.15700v2（InternLM2.5-StepProver）§2.1、§2.2、Appendix A（Critic Model）；
> 对照：本目录 `1-cpu.md` §32–33（d\*(s) 定义与 OR/AND 节点语义）、`2-gpu.md`、
> `3-value-head.md`（六类 value 训练法）、`4-3value-head.md`（双头/三套 target）。
> 目标场景：`reap-mcts-lean-v2`，V(s) = −d\*(s)，d\*(s) = 从 s 到 solved 的最优剩余步数。

---

## 0. 结论（TL;DR）

1. **可以复用，但不是"直接用"**。该 critic 是一个训练良好的**排序型标量评判器**（在证明树内"谁更接近 no_goals"），它和我们要的 V(s) = −d\*(s) 之间隔着**明确的语义鸿沟**：

   - critic 只接受过**偏好序监督**（path pairs / sibling pairs），其输出分数**无数值标定、无跨树锚点**；
   - 我们的值网络必须提供**绝对刻度**（"差一步"与"差十步"在数值上相差 9，且可直接参与 OR=max / AND=min 聚合与 Q 的 −1+V(s′) 备份）。

2. **三段式结论**：

   | 用途 | 可行性 | 说明 |
   |---|---|---|
   | 作为**状态扩展排序启发式**（CGS 式：分数最高的 state 先扩展） | ✅ 直接可用 | 这正是论文的用法，pair accuracy 78.0%，效果好 |
   | 作为**MCTS 的 Q-backup 数值**（V 进 `G = −1 + V(s′)`） | ❌ 不可直接使用 | 分数无步数刻度，加法结构会被单调变换破坏 |
   | 作为**模型结构/训练配方的参照**，自建 V(s)=−d\*(s) 网络 | ✅ 强烈推荐 | 论文披露的完整配方（基底 + 偏好对 + 一轮微调）可以直接搬 |

3. **必做的改造（三处）**：

   - **改造一：数值标定**。保留 critic backbone（冻结），新加回归头，用已验证轨迹的 −d 标签做 Huber 回归；
   - **改造二：目标函数**。从"纯 pairwise ranking"改为"回归为主 + ranking 辅助"的双目标；
   - **改造三：输入格式对齐**。state 序列化模板（Lean 版本、字段布局）与 critic 训练时对齐，否则 78.0% 的 pair accuracy 不可复现。

---

## 1. 论文事实归纳：critic 到底是什么

| 属性 | 论文披露内容 |
|---|---|
| 模型规模 | 1.8B（从 InternLM2-Chat-1.8B-SFT 初始化，Chat 版而非 Math 版） |
| 训练轮数 | 微调 1 epoch，8×A800 |
| 训练数据 | 偏好对，来自 miniF2F-valid、Mathlib、Lean-Workbook-Plus 的 best-first search 轨迹；最终轮 454K 对（去重，no_goals 相关对降采样到 10%） |
| 自举数据 | ~8,000 对（InternLM2-StepProver 在其训练集上搜索轨迹） |
| 目标函数 | RLHF reward-model 风格 pairwise preference，非回归 |
| 两类偏好对 | ① Path Pairs：同一成功路径上，靠近 no_goals 的子状态 > 靠近 root 的父状态（V(sₜ) < V(sₜ₊Δ)）；② Sibling Pairs：成功路径上的状态 > 同一兄弟节点（未通向证明） |
| 评测 | miniF2F-test 生成 6,510 对，pair accuracy **78.0%** |
| 使用方式 | 搜索时查询 critic 分数，扩展分数最高的未展开状态（CG search）；与 BF（平均 log 概率）构成混合 BF+CG |
| 效果 | 把 prover 在 miniF2F-test 从 59.4% (BF, 256 次) 提到 65.9% (BF+CG)；ProofNet 22.3% → 27.0% |
| 自带局限 | 论文自述：**缺少稳定的 critic 度量指标**，难以迭代 critic 质量 |

**关键推理**：1.8B + 1 epoch + 纯排序目标就达到 78.0% 对正确率，说明其能力主要来自"大偏好数据集 + 排序目标"，而非基底的数学深度。这对我们有两个含义：

- 我们完全可以用**同一个公开基底（`internlm/internlm2-chat-1_8b-sft`，无需 gated 权重）**加自己的回归目标重训一个"标定版"值网络；
- 论文权重即使难以获取（仓库需授权），**不构成阻塞**——配方比权重值钱。

---

## 2. 与 V(s) = −d\*(s) 的语义差异（数学层面）

### 2.1 我们的定义（1-cpu.md §32–33）

$$
d^*(s) = 1 + \min_a d^*(T(s,a)),\qquad
V^*(s) = -d^*(s)
$$

$$
\text{AND 态 } s = (g_1,\dots,g_k):\quad
V^*(s) = -\max_i d^*(g_i) = \min_i V^*(g_i)
$$

这里的绝对刻度是不可省的：OR 节点取 max、AND 节点取 min，都是对**数值**运算，且 δ=1 的步代价使"深一步 = 值减一"成为精确的递推关系。MCTS 备份 `G(s,a) = −1 + V_φ(s′)` 与 `Q` 的取均值，也都依赖同一刻度。

### 2.2 critic 的实际监督（单调序，不等距）

Path pair 只提供同一成功路径上的**全序**：V(sₜ) < V(sₜ₊Δ)；sibling pair 只提供"成功路径 vs 失败分支"的二分强弱。因此 critic 输出的标量 s_critic 与真值 −d\*(s) 的关系只能是：

$$
s_{\mathrm{critic}}(s) = g(-d^*(s)) + \varepsilon(s),\qquad g \text{ 单调（不可微未知）}, \ \varepsilon \text{ 带树间漂移}
$$

由此可推出三条硬结论：

1. **保持选择不变**：只要 g 在同一棵搜索树内单调，`argmax s_critic` == `argmax (−d\*)` 成立 ⇒ 用于"先扩展哪个 state"的 CGS 启发式成立（任何单调变换都不破坏 argmax）；
2. **破坏数值运算**：`−1 + s_critic(s′)` 不再是"深一步扣一分"，Q 累加、OR/AND 聚合全部失真 ⇒ 不能作为统计性 value 进备份；
3. **跨树不可比**：偏好对只在树内构建，分数全局分布无锚点。论文的"用 critic 重估所有未证明语句、取 top 50%"隐含了跨题可比假设，但那是检索式用法，不是定长闭环。

### 2.3 它更像哪一轴？

对照 `3-value-head.md` §28 的双头设计，critic 本质上是在学 **V_succ 轴**（"这份状态更可能通向证明"）与**树内排序**的混合体，而**不是 V_len 轴**（剩余步数）。所以把它移植为 V_len 必须替换目标。

---

## 3. 适配性矩阵：需求 × critic 现状

| 我们系统的需求 | critic 现状 | 判定 |
|---|---|---|
| 兄弟状态之间的相对排序（先扩展哪个） | Sibling Pairs 直接训练，78.0% | ✅ 原生支持 |
| 同一成功路径上的进度单调性 | Path Pairs 直接训练 | ✅ 原生支持 |
| 全局绝对值 = 剩余步数 | 无数值锚点 | ❌ 需改造一 |
| 跨问题可比性（用于选题/预算分配） | 无显式监督，隐式漂移 | ⚠️ 需标定后评估 |
| AND 态（多 goal）逐 goal 聚合 | 单标量整体打分 | ⚠️ 需改造：按 goal 拆分查询再取 max |
| 输入序列化与 Lean 版本对齐 | 按 StepProver 模板（NAME/PROOF_BEFORE/STATE_BEFORE），Lean 4.7.0 | ⚠️ 需对齐 |
| V2 元状态：工具观测 H_obs、库 L（`4-training-and-metrics` §4.1：价值需含工具特征） | critic 只接受纯 Lean state，看不到 H_obs | ❌ 架构缺口 |
| 与共享 backbone 方案兼容（2-gpu / 3-value-head §31：单 backbone + 双头） | 独立 1.8B 模型，与 7B policy 不共享表示 | ⚠️ 引入双模型成本，但 1.8B 代价小 |
| 推理成本 | 1.8B，每次扩展一次前向 | ✅ 可控（比 7B policy 便宜 ~4x） |

---

## 4. 改造规范（推荐路径 A→B→C→D，逐级加码）

### 改造一：数值标定（必须做，最便宜）

把 critic backbone 当**冻结特征提取器**（对应 3-value-head.md §26 的"线性头预初始化"思路，但基底换成 Lean-specialized 的 1.8B）：

```
Lean state s
      ↓
critic backbone（冻结，w 不变）
      ↓
hidden h ∈ ℝ^d（取最后层/倒数第二层 pooled）
      ↓
回归头： V(s) = wᵀh + b
      loss = Huber(V(s), −d_label)
```

- 数据标签：**成功且 Lean 已验证的轨迹**（Mathlib human proofs + 我们 MCTS 产生的全部验证轨迹）：

$$
  z_t = -(T-t)
$$

- 训练方式：先只训 (w,b)（可视为线性回归/闭式解），验证 R²、Spearman ρ 可行后再解冻最后 k 层或加 LoRA；
- 这一改造让 V 同时获得：**绝对刻度 + 与 policy 解耦**；
- **先测表示质量再投入**（对应 4-3value-head.md §20）：若冻结 1.8B 特征上回归 ρ ≤ 0.2，则说明该基底对"剩余步数"无表示能力，直接放弃高成本微调。

### 改造二：目标函数（训练阶段）

总目标：

$$
L = \lambda_{\mathrm{rank}}\,L_{\mathrm{rank}} + \lambda_{\mathrm{reg}}\,L_{\mathrm{reg}}
$$

- $L_{\text{rank}}$：沿用论文的 path/sibling 偏好对（建议直接用他们公开数据的分割与构造方式）；
- $L_{\text{reg}}$：Huber $(V(s), -d)$，d 来自验证轨迹；
- 建议 $\lambda_{\text{reg}} \gtrsim \lambda_{\text{rank}}$，**先回归后排序**：分类器能凑出 78% 对正确率的两分性，但回归才能给出步数刻度；
- 若只做"改造一"（纯回归头冻结解码），则 rank 项由冻结 backbone 已有的偏好表示隐式承担，不需要重训。

### 改造三：输入格式对齐

- replica 论文的 Prover prompt 模板的语义字段（图 2：`NAME` / `PROOF_BEFORE` / `STATE_BEFORE` / `TACTIC`→critic 版本去掉 TACTIC）；
- 我们的 `Enc(s)`（2-gpu.md §1）须与 critic 训练时的 state 序列化**逐字节一致**，包括 Lean 版本（论文用 Lean 4.7.0）、换行、hypothesis 打印顺序、多 goal 打印方式；
- **验收手段**：离线在 miniF2F-test 的 6,510 对（论文公布的方法自己重造）上复现 pair accuracy ≈78.0%。达到即说明序列化对齐；达不到则先查格式而不是先改模型。

### 改造四：AND 态与 V2 元状态

1. **多 goal**：把 AND 态拆成 k 个单 goal prompt，分别打分：

$$
   V(s_{\mathrm{AND}}) = \min_i V(g_i) \quad(\text{即 } -\max_i d(g_i))
$$

   不满足：直接整体打分会把"最难的 branch"与"总进度"混为一谈，破坏 1-cpu.md §33 的精确语义；
2. **V2 工具观测 H_obs**：critic 的 1.8B 基底看不到 effect 观测。两条路线：
   - (a) 保守路线：value 只消费纯 Lean state（与 V1 一致），工具信息留给 policy（4-training-and-metrics 的"经策略链间接回传"仍成立）；
   - (b) 激进路线：prompt 里追加 `OBS:` 字段附加观测摘要，并重新偏好+回归训练。建议先做 (a)，用 (b) 做 ablation。

---

## 5. 验证协议（不重蹈"无稳定度量"覆辙）

论文自述对 critic 缺稳定度量，此处给出我们系统的三层协议：

| 层 | 指标 | 观察点 | 通过线 |
|---|---|---|---|
| L0 表示质量 | 冻结特征上回归的 R² 与 Spearman ρ(V, −d)；树内 z-score 后的兄弟对正确率 | 证明"表示里有没有步数信息" | ρ ≥ 0.6（参考 4-3value-head §20 的 ρ≈0.8 期望） |
| L1 标定 | 训练集外再报 pair accuracy + 与 −d 的 ρ；跨题分位数归一化后可比性 | 证明"排名与标定同时成立" | 复现 78.0% 且 ρ ≥ 0.6 |
| L2 端到端 | 同一 MCTS 预算 B 下：solve@B、平均最短 proof 长度、CPU 时间 C_{s_i}（1-cpu.md§31 定义）；BF vs CGS vs 标定 CG 三臂对照 | 证明"值网络真的让搜索更快更深" | 标定 CG ≥ BF 平均最短长度更长（对标论文 1.66 vs 4.44） |

**泄漏红线**：论文 bootstrapping 用了 miniF2F-train 的搜索轨迹，评估 critict 一律在 held-out 集（miniF2F-test / ProofNet），避免"训练集内排名出 78%"的假阳性。

---

## 6. 分阶段实施基线（可独立交付）

| 里程碑 | 内容 | 产物 |
|---|---|---|
| M0 | 获取权重：优先官方 release；若 gated/不可得，直接用 `internlm/internlm2-chat-1_8b-sft`（公开）作为等价基底 | 能推理出分数的模型 |
| M1 | prompt/序列化桥接，离线重造 6,510 对，复现 78.0% | 格式对齐证据 |
| M2 | 冻结 backbone + 线性回归头，Huber(−d)，报告 R²/ρ | 标定值网络 v0 |
| M3 | 接入 MCTS 做 BF / CGS / 标定 CG 三臂 A/B（预算一致） | 端到端结论 |
| M4 | 解冻 LoRA（或全参）双目标训练一轮 | 标定值网络 v1 |
| M5 | 可选：critic score 蒸馏进自研共享 backbone 的 V head（保持单模型） | 单模型方案的 V |

---

## 7. 风险与边界

- **许可**：InternLM2 系列为相应开源协议；critic 权重在 HF 上需授权（API 返回 401/gated）。**配方可复刻、权重不可强求**；
- **域漂移**：critic 训练域 = miniF2F + Mathlib + Lean-Workbook-Plus + Lean-GitHub；我们 V2 的任务域含元级动作（fill-hole/patch/addDecl/run-effect），与其训练域差异大 ⇒ 回归头在自有数据上重训不可省；
- **censored 数据**：sibling 支的"失败"可能是预算不足而非不可证（4-3value-head §10），回归标签只取验证成功轨迹，避免把 censor 当负例；
- **惩罚噪声**：论文 dedup + no_goals 对 10% 降采样说明"多 goal/已解状态对"是噪声源，采样时同样处理；
- **与共享 backbone 决策的再平衡**：引入 1.8B 第三方 = 改变 3-value-head §31"单 backbone"的架构；若采纳，建议把 M5 蒸馏作为终态。

---

## 8. 一句话答复

> StepProver-Critic 可以直接当"扩展优先级"用（它的训练目标和 CGS 用法天然匹配）；
> 但要当**我们的 V(s) = −d\*(s)**，必须加回归标定头 + 换双目标 + 对齐序列化；
> 若搞不到权重，用公开的 1.8B 基底重训一套标定版即可，论文的价值是配方，不是那坨二进制。
