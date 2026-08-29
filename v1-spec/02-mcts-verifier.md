# 02 — MCTS 与环境（reap 复用规范）

## 2.1 复用策略：reap 原样，仅加"rollout 记录器"

| 模块 | 策略 |
|---|---|
| `Reap/Tactic/Step.lean`（parse/forbid/timeout/kernel-check） | **原样**（安全性依赖） |
| `Reap/Tactic/TreeSearch.lean`（OR/AND、PUCT、证明摘录、回放） | 原样；唯一新增：**tree-exporter patch** |
| `Reap/Tactic/Generator.lean`（prompt/LLM 协议） | 原样（我们的 FastAPI 兼容） |
| `Reap/Options.lean` | 仅用配置键；`reap.value_endpoint` 指 `FastAPI:/value` |

**Tree-exporter patch**（约 30 行，patch 文件入 `tools/patches/`）：
- 在 `visitNode`（`TreeSearch.lean:238`）与 `updateNode/updateEdge` 处，追加 JSONL 记录：
```json
{"kind":"node","tactic":"...","logp":-12.31,"verdict":"ok|error|timeout|solved",
 "value":0.52,"diff_visit":1,"parent_key":"...","state_key":"..."}
```
- 输出路径接 `reap.raw_tree_path` 同目录的 `rollout.jsonl`；写入用 append+flush。

## 2.2 MCTS 度量（与 reap 现有实现保持一致，配方为 spec 只读）

$$c(N)=c_{init}+\ln\frac{N+c_{base}+1}{c_{base}},\quad \hat p_i=e^{\log p_i},\ p_i=\hat p_i/\text{sum}$$

$$Q_i^{(OR)}=\gamma^{-1-v_i}-\text{stepcost},\qquad Q_i^{(AND)}=1-v_i$$

$$U_i=c(N)\,p_i\,\frac{\sqrt{N}}{1+n_i}$$

- 探索系数：`c_init=0.001`、`c_base=3.2`、`γ=0.99`、`τ(prior_temperature)=50`（默认，全部来自 Options）。
- **AND 语义**：AND 节点的值时取未解子节点的 min；focus 子节点 stepcost=0。

## 2.3 验证器语义（拿来做训练 reward 的规范定义）

```
verdict(s,a):
  parseError | forbidden | tacticException | tacticTimeout
  | tacticErrorMessages | unassignedGoal | assignedProofHasMVarOrSorry
  | auxProofHasMVarOrSorry | auxProofKernelCheckFailed | finalProofCheckFailed
  → 最终 reward: r=+1 iff 存在一条 root→leaf 全 solved 路径（checkProof 全通过）
```

**负样本**：error 类型及其 JSON 化信息记录（`EvalError` ToJson），训练时"错误 tactic 的负偏好对"来源。

## 2.4 断言与过滤

1. `checkProof` 通过 = 训练正标签（**不以"Lean 内部无报错"代替**——reap 会拒绝 unassigned/mvar/aux-篡改）；
2. 树中重复状态去重：`stateKey`（pp-goals JSON hash）碰撞即合并子节点（prior 相加，`TreeSearch.lean:282-288`）——训练采样时以**去重后的边**为准（防重复count 膨胀）；
3. 每个 rollout 结束时输出 `solutions.jsonl`（含 proof script 与 $p_*$ 映射）。

## 2.5 采样预算（作为训练/课程输入）

| 参数 | rollout(找解) | Diff 标定 |
|---|---|---|
| max_nodes | 64 | 16 |
| max_steps | 64 | 16 |
| n (samples) | 6 | 3 |
| 每题超时 | 200s | 40s |
| Prompt 长上限 | 4096 tok | 4096 tok |
