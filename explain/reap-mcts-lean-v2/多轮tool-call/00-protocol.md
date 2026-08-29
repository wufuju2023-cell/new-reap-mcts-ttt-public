# 多轮 tool-call（v2, CPU/无 miner）：形式化协议

> 依据：`explain/5-alpha-as-Lean-coding-agent`（ℒ = 带效应的类型化语言）、
> `7-reap-v1-v2`（Reap.Agent：Eff 通道/元动作/塔上升/层次不变量）、
> `agentic-perspective/01-rollout-cot`（树式 rollout，自本仓库源码）。本文把“多轮工具调用”严格化为
> ℒ 上的**程序合成 + 执行-回注循环**，并对应到 `Reap/*` 实际代码路径。

## 0. 形式框架（全部定义以代码事实收敛）

- 状态：$s = (\mathrm{lcx},\ \mathrm{Env},\ \mathrm{obs\text{-}history},\ \mathcal{L})$（lcx=Lean 局部上下文；Env=世界原语注册表；obs 历史；库 L）
- 动作：$a:P\in\mathcal{A}(s)$，其中 $P:\Gamma\vdash P:\mathrm{Eff}\ R$（**类型化效应程序**，唯一“动作”形态）
- 转移：$T(s,a)= s'$，跑 $\Xi(P)\to(r,\mathrm{obs})$：$r$ 是类型化结果，$\mathrm{obs}$ 是结构化观测
- 终止谓词：$\mathcal{G}(s)$（kernel 闭环 / 测试通过 / 实验断言成立——由 verifier 决定，不自由）

**“多轮”的形式化**：$P = a_1;a_2;\ldots;a_m$，$s_0 \xrightarrow{a_1} s_1 \cdots \xrightarrow{a_m} s_m$，
$\mathrm{obs}$ 链不回传 token 文本——只把**类型化观测**并入 $s_i$（§5 收益 2）。

## 1. 执行器定义（代码路径）

| 原语 | 运行载体 | 回传观测类型 | 实现锚点 |
|---|---|---|---|
| `tactic` | Lean kernel 校验 | `EvalResult`（ok/errorMsgs/parse/forbidden/timeout） | `Reap/Tactic/Step.lean evalTacticStr` |
| `prove-block` | 整段 example 展开 | kernel-confirmed script | `Reap/Training/MCTSDriver`（v1） |
| 世界效应（python/检索/训练/网络） | harness/runner 队列（amdbridge） | JSON **→转成 ℒ 值** | `runner.py` + `RolloutSink` JSONL |
| 库注册（塔上升） | lake 项目加声明 | new-def + kernel check | `apply at L` 后 addDecl |

> 每个原语都是 $\mathrm{run}: \mathrm{Spec}\to \mathrm{Obs}$ 的类型化接口——工具调用**不产生奖励**，
> 只产生状态更新（§8 的 verifier-grounded tool use）。

## 2. 多轮调用协议（逐轮不变式）

```
while budget and not done:
  1. sample  P ∈ A(s)          （策略 π_θ 生成，n>1）
  2. static filter:  typecheck(P)     → 非法项 0 容忍废弃
  3. run(P) → (r, obs)          （超时/心跳：每原语预算，取自 reap.heartbeats）
  4. observe: obs → 类型化值 → 并入 s
  5. (v2 GPU) buffer → ttt_step； (v2 CPU) 仅记录（sink）
  6. checkpoint & idempotent   （每验证点=状态快照，重启续作，与 AGENTS 幂等规则一致）
```

### 2.1 多轮间“信息”到底传什么（关键）
- **传**：新 lcx/新断言/库新增/可复现实验输出（类型化）。
- **不传**：自由文本摘要；“模型以为发生了什么”从不进入状态（§4/§8 的奖励-噪声对抗）。

### 2.2 多轮的回退/异常语义
| 事件 | 处置 | 对应代码语义 |
|---|---|---|
| parse/forbidden | 该动作作废，换候选 | `EvalError.parseError/forbiddenTactic` |
| timeout | 该原语预算耗尽→剪枝 | `withTimeout`（`reap.timeout` 选项） |
| unassigned / mvar / sorry | 证明未闭合→该子任务失败 → 树内 AND-backup | `checkProof` 分支 |
| 效应层异常 | 观测=错误值，状态不破坏 | runner 返回 stderr 文本→类型化 |

## 3. 元编程与“塔上升”（多轮工具调用如何升级问题域）

- 元动作：fill-hole / patch-Expr / **addDecl（证据上升为库层）** / run-effect。
- 塔上升定义：$L_{t+1} = L_t \cup \{ v : \mathrm{kernel}(v) \underbrace{}_{\mathrm{typecheck}+ \mathrm{run}} \}$
- 抽象深度：$d_g = \#\{\text{引用库声明}\}\cdot \text{…}$——多轮完成的越久，$d_g$ 单调不减（§7/§8 的“语言塔”是 可测的 MCTS 地形线）。
- **无 miner 的含义**：库 L 的增长仍然发生（自举），但**入口不设“新题挖掘器”**——大任务分解由目标任务本身 + LLM 规划层提供（外层 agent ∥ 内层 P-V+TTT，见 agentic 02）。

## 4. 大型任务（multi-round 顶层协议）

```
目标任务 G （大定理/大实验/模型训练）
  ├─ 分解：G = 子任务树（中层规划 lang/工具）
  ├─ 每个子任务 → ℒ 动作（§1）；L 随子任务完成增长（塔上升）
  ├─ 证据链：observe→(断言成立?)→checkpoint→下一步
  └─ 预算: 每子任务 → max_steps/LLM query 数；全局 → wall-clock；中断/续作=状态化
```
- 大任务特性：子任务之间**非正交**（共享 L/上下文）——因此多轮调用采用**栈式上下文**（当前子任务堆栈 + 全局 L），不做无界长上下文（与 LLM agent 的“长上下文单链”相反，长任务我们靠树+库，而非 token 长链）。
