# 03 — 课程学习（Teacher=DeepSeek V4 Flash）

## 3.1 角色与协议

- **Teacher**：DeepSeek-V4-Flash（`api.deepseek.com/v1`，OpenAI chat 格式，`n=1`）；
  用户密钥注入：`DEEPSEEK_API_KEY`（不落盘训练产物、不回显日志）。
- **输出契约**（JSON 一行一 variant）：
```json
{"statement": "theorem <name> : ...", "hierarchy": 1, "note": "const-to-var"}
```
- 仅允许 `#import` 已存在的 `mathlib`/`L_g` 中符号；出生成器前置约束。

## 3.2 Prompt 模板（冻结在 tools/prompts/teacher_v1.md）

```
你是数学家：为下列正式定理生成若干【更简单但结构相似】的变体，
每个变体必须是 well-typed 的 Lean statement（EXAMPLE 级别），可引用库与下面的 ctx。
算子白名单: [常量→变量, 加假设, 引理外置, 对称/对偶变体, 复合局部化]
目标 p_*: ...
当前 Diff(p_*): ...   建议层级: 0.5~0.9
库上下文 ctx(L_g): [lemma_x: ..., ...]
输出: JSON 数组 {"variants":[...]}
```

单次批量请求：20 条/请求，temperature=0.5；收集器聚合 1000 题/轮。

## 3.3 三闸门（全部通过才入池）

**G1 Lean 编译**：将 statement 插入模板 lean 文件（`import Mathlib; example : ...`），`lake env lean` 编译；失败 → 丢弃（记录原因）。排除 `sorry/admit/?`。

**G2 难度（Diff 标定）**：用**当前** policy $\pi_g$ 与低预算跑 solver：

$$d(v)=1-\mathrm{solve@}16(\pi_g,v)$$

- 标定结果**缓存**（`cache/diff_index.json`：sha256(statement) → diff）；
- 门限：[0.5,0.9]。超出区间：反馈 teacher（fail 附 diff 与原因），教师下次调节 hierarchy。

**G3 结构（Sim）**：与目标结构共享：

$$\mathrm{Sim}(v,p_*)= \frac{|\text{common AST subtrees}|}{|\text{AST}(p_*)|}\ge 0.7$$

- v1 简化：小参数正则（`== 目标含 N 个变量的变体数量`）+ 关键常量子串一致性；
  实现：`tools/sim.py`(ast 比较)。计算失败（如 AST 差异过大）→ 判 0.3 并降权。

## 3.4 目标锚定阶梯

对每个 $p_*$ 维护 `ladder(p_*) = {v_0 ≤ v_1 ≤ … ≤ p_*}`（diff 单调），
新解出的变体即阶梯顶点；只有当 $\mathrm{next}(v_i)$ 前趋被解出后才把 $v_{i+1}$ 放入 $P_g$。
（相当于 AlphaProof 自比赛“变体边解边推进原题困难度”的显式版本。）

## 3.5 库增长（Growing Mathlib）

```
L_{g+1} = L_g ∪ {t : checkProof 通过且 t 可在隔离命名空间 RecursiveMath.<idx> 声明}
```
- 存储：`libraries/growing_mathlib.lean`（追加）+ `libraries/index.json`（name→statement, hash）；
- **教师上下文注入**：`ctx(L_g)` 取 top-8（用 cosine embedding——简化：用 `state_tactic_pairs` 的 retriever 复用）。

## 3.6 预算与调度（每轮课程）

| 步骤 | 资源 | 预计 |
|---|---|---|
| 1000 变体（DeepSeek） | API 20 请求 | ≤¥2、10 分钟 |
| G1 编译 1000 | 本地 lake env lean 并行 ×8 | ~1 h |
| G2 Diff 标定 ~700 | 16 节点搜索 | ~2 GPU-h |
| 入池 P_g ≤350 | — | — |
| Rollout（64 节点×350） | — | ≈4–6 GPU-h |

> 全部安排为 nightly CRON：每晚自动一轮，早上由 SSH 汇报 summary。
