# 01 — 数据集规格（Data Spec）

## 1.1 来源与优先级

| # | 数据 | 量 | 用途 | 获取（国内网络） |
|---|---|---|---|---|
| D0 | `FrenzyMath/state_tactic_pairs` | ≈50k | 阶段 A SFT 主料 | a model registry datasets 镜像（搜同名）或 hf-mirror.com |
| D1 | FATE-M（`frenzymath/REAL-Prover/Realprover/data/fate_m.jsonl`） | ~test 集 | 评估/目标难题 p_* | github raw（mirror: ghproxy）或魔搭 repo |
| D2 | 课程变体（DeepSeek 生成 + 闸门通过） | 每代 1000→350 | 阶段 B rollout & TTTRL | 服务器本地产物 |
| D3 | self-rollout 成功轨迹（solutions.jsonl） | 每代 300± | 回灌 A/B | 本地产物 |
| D4 | 失败轨迹（verdicts.jsonl, error 类） | 每代 ≈3000 | 负样本 pair | 本地产物 |

> 国内规则：任何 HuggingFace URL → **hf-mirror.com 或 a model registry**；git clone github → ghproxy 前缀或 `git clone <mirror>`。

## 1.2 示例格式（JSONL 一行一条）

```jsonc
// D0/D2（训练输入）
{"goal_key": "sha256(ppGoals)", "state": "<ppProofState>",
 "context": ["lemma_1: <statement>", "..."],     // 检索前提（≤8）
 "tactic": "exact ...", "old_logprob": -14.2,     // 只在 D2 有
 "is_error": false, "error_meta": null, "w": 1.0}

// D1（目标集）
{"id": "FATE-M/xxx", "formal_statement": "theorem ... : ...", "hard": true}
```

- 每个样本 2 份 JSON 校验：lean 编译自检（smoke 抽样 1%）+ `logging` 完整性。
- **不允许**包含 `sorry/admit/?`/`exact by` 逃逸；保留 `EvalError` 类型作为标签字段。

## 1.3 Prompt 模板（冻结，golden test：`tools/prompt_spec.md`）

> 必须与 `Reap/Tactic/Generator.lean:73` 的 `mkPrompt` 完全一致；区别仅为 context 前缀（若无库，上下文空数组时模板行为保持一致）。任何模板改符号 → golden test FAIL → 重新校准 SFT/GRPO。

## 1.4 去重与对称性

- 去重：`sha256(state_pp)`（reap 的 stateKey 同样式）——**按目标键去重**，同一状态被多题重复出现则各计各的、训练 token 摊销？
  （实现选择：去重优先 —— 训练时 D2/D3 以 state_key 去重一次，避免采样权重偏高。）
- 分组：GRPO 每题一个 **group key = problem_id**，保证组内同 prompt。

## 1.5 大小控制

- 每 batch 截断 4096 token（SeqLen）；过长 context_0 时丢弃旧项；
- 每日数据输出总量限制 ≤ 4GB（压缩 gzip 保留 7 天）。
