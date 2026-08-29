# 11｜AlphaGo Zero 的 Self-Play 与 Reap-α-Π-TTT 的自改进对应（严格分析）

> 归档：AlphaGo Zero 自博弈机制的形式化；Lean 证明域“对手→教师”的等价重排；RTTT 作为“事件粒度 self-play”；收敛条件与不动点判据。

## 1. AlphaGo Zero：Self-Play 的形式化机制

### 1.1 定义与循环

设零和博弈状态 $s$、动作 $a$、**终局回报** $z(s)\in\{-1,0,1\}$；网络 $\theta$（双头：搜索的 policy + value）。Self-play 定义为**同参数策略之间的策略迭代**：

$$\pi_{t+1} \leftarrow \mathrm{distill}\big(\underbrace{\pi^{\mathrm{search}}}_{\mathrm{MCTS}(\theta_t)}\big),\qquad V_{t+1} \leftarrow \mathrm{regress}\ \mathbb{E}[z\mid s]$$

关键结构：**数据生成者 = 学习者**（同一 $\theta$），循环为

```
θ_t → 自我对局(搜索驱动采样 π_search) → 轨迹 (s, π_search, z)×N
    → 重训练（策略熵蒸馏 + 价值 MSE + L2 正则）→ θ_{t+1} → 新对局
```

- **数据是“内生的”**：对手即自己，观测与分布**由当前水平自动定义**——self-play 无需外部标签的根源；
- **搜索增强（policy improvement）**：MCTS 的 visit 分布 $\pi^{\mathrm{search}}$ **严格优于**网络原始 $\pi$（每局 1600 sims ≈ 近似最优），蒸馏 $\pi_t \leftarrow \pi^{\mathrm{search}}$ = **一步策略改进**：
$$\mathcal{L}_\theta = -\epsilon\,\pi^{\mathrm{search}}\ln\pi_\theta + \lambda\|V_\theta(s)-z\|^2 + c\|\theta\|^2$$
- **非平稳性管理**：目标（产生数据的分布）随 $\theta$ 演化——用“最新代数据为主 + 少量 replay”的近端策略采样管理；
- **无“对手难度调整器”**：难度由自身水平内生（对手=自己），训练曲线 = 策略曲线的联立提升。

### 1.2 实现“self-improvement”的充分条件

1. 可判定的终局信号（胜负确定、无噪声）；
2. 搜索改进可蒸馏（搜索分布优于策略分布）；
3. 对局分布有意义（对手=自己 → 对弈质量单调）；
4. 学习-博弈错峰（延迟约 1 代，避免“追自己尾巴”的病态）。

## 2. Lean 证明域：“Self-Play 的数学等价形”

| AlphaGo Zero | Lean/Reap 域 |
|---|---|
| 两玩家 zero-sum | **单玩家 AND/OR 树**（无对手、转移确定性） |
| 对手=自己 | **对手不存在 → 由“出题者”（教师/演化器）承担“发难”** |
| 终局胜率信号 | $\mathbb{1}\{\mathrm{kernel\ checkProof} = \mathrm{ok}\}$（稀疏、严格） |
| 胜负黑箱 | 校验器给出**中间诊断**（parse/error/未闭合/子目标）→ 更丰富信号 |
| 胜率单调推进 | **无天然单调度量** → 用 $(d_g,\ \mu,\ \mathrm{solve@}B)$ 向量 |

**关键否定**：纯“自对弈”在数学上**不存在**（没有一局“证明比赛”），所以 self-play 的等价物只能是 **“自考题”（self-problem-generation）→ 自作答 → 沉淀**：

$$\boxed{\text{对手} \to \text{教师/题库演化器},\qquad \text{胜率} \to \text{验证+中间信号},\qquad \text{对局} \to \text{求解轨迹}}$$

## 3. Reap-α-Π-TTT 的自改进环

```
教师（对手位）：按 Diff(p)∈[0.5,0.9]、Sim≥τ 生成“刚够得着”新题 p
学生（搜索位）：MCTS(p; π_θ, V_φ) —— 每节点 = Lean 验证
              ├─ 叶价值回填（min-backup, OR/AND）
              ├─ RTTT：buffer≥k → θ（REINFORCE+KL锚）与 φ（TD: V←V+α_V[r+γV(s′)−V]）
              │         ——【在线一步，不待整批】
              └─ 成功 → 定理+证明 → 入 L（库增长）
库 L：新引理 → 教师出题“地形”变难（可用引理变多 ⇒ Sim 更高 ⇒ 题目更难）
循环（链式）——有效改进判据：solve@B↑；d_g↑；μ≥0.4；迁移指标 A≥基线
```

### 3.1 与 AlphaZero 的严格映射表

| 环节 | AlphaGo Zero | Reap-α-Π-TTT（我们） |
|---|---|---|
| 对手 | 自身（零和） | **教师/演化器 + 新题**（Single-player 挑战） |
| 搜索 | MCTS (minimax) | MCTS（AND/OR + min-backup + $\gamma$-discount） |
| 改进来源 | search-visit 蒸馏 | 搜索值回归 + RTTT 单步 RL（adv = r+γV(s′)−V(s)） |
| 训练节拍 | 每 1000 局批次 | **每次调用（RTTT）**——批粒度→事件粒度 |
| 终局信号 | $z$ | $\mathbb{1}[\mathrm{kernel}]$ + 失败诊断（更丰富） |
| 稳定性管理 | 近端采样 + 延迟训练 | KL 锚 + snapshot/rollback（`/adapter/snapshot|restore`） |
| 进度量 | 自我对弈胜率（内生） | $(d_g, \mu, \mathrm{solve@}B)$ 外部向量 |

### 3.2 为什么 RTTT 是“更紧的 self-play”

- 改进周期从 $O(\mathrm{batch})$ 缩到 $O(1)$（每个验证事件）——信号延迟最小，单题“难点”即时转化为梯度（把“自对弈难度”刻在题内而非题间）；
- 代价：非平稳目标以事件频度出现，须**锚定**（KL 至 base）+ **回滚快照**；
- 因此 RTTT 是在保持 self-play 精神（“当前水平生成的分布来提升自己”）下的**更高频版本**。

## 4. 收敛性与不动点（诚实论证）

- AlphaZero 收敛依赖“指标（对手）单调”，无形式证明但实证好；
- 数学自改进 $\theta$ 收敛**不是自动的**，需要：
  (i) 教师“恰好够得着”平衡（不出过难/过易）；
  (ii) 库重利用率 $\mu$ 保持（否则新问题无法借旧引理，链断）；
  (iii) 价值头锚定（RTTT 过频 → 漂移 → PUCT 的 $Q$ 失真）。
- **退出判据**：$d_g$ 饱和 / $\mu$ 退化 / 变体通过率过低 ⇒ “研究陷入局部不动点”——应调整课程+教师（而非加算力），对应 AlphaZero 遇到性能平坦时增强网感而不是加 sims。

## 5. 结论

1. AlphaGo Zero 自改进 = **零和-同策略对弈下的内生策略迭代**（无标签、单调、批粒度）；
2. Reap-α-Π-TTT 是**结构重排**：对手→教师+难度地形；胜率→验证+诊断；对局→求解轨迹；批→事件（RTTT）；并增加 **库增长 $L$**（AlphaZero 没有的外部记忆，是对非平稳数据的补强）；
3. **“能够自我提升”的严格判据**：solve@B↑ 且 $d_g$↑ 且 μ≥0.4，且**非由教师预调**（教师只按 Diff/Sim 出题，不“透露解法”）——达到与 AlphaGo Zero 同等级的**内生改进**定义（内生性表现为“难度增强”而非“胜率增强”）；
4. **两者并非同构**——差别是本质的：数学没有零和对手，所以“自我改进”只能由“自考题 + 自作答 + 知识沉淀”逼近——这就是为什么教师、课程、库增长被纳入系统：**它们合起来承担了 AlphaGo Zero 中“对手”的认知功能**。
