# 00 — 系统综述

## 0.1 一句话定义

一个 alpha-proof-style 的 Lean4 定理证明器「训练-搜索」闭环：
**teacher(DeepSeek V4 Flash) 产出课程变体 → 三闸门过滤 → student(7B policy + 值头) 在 reap MCTS 中搜索 → Lean 内核验证 → 验证结果驱动参数更新（GRPO/TTTRL）→ 库增长 → 下一代更难课程**。

## 0.2 组件图

```
            [A] Teacher  (DeepSeek V4 Flash, 冻结, 仅文本)
                 │  variant 候选 {statement, hierarchy}(批量,温度0.5)
                 ▼
          [G] 课程闸门 (Lean 编译 → Diff 标定 → Sim 过滤)
                 │ P_g: {v : Diff∈[0.5,0.9], Sim≥0.7}
                 ▼
            [C] Student  (REAL-Prover 7B policy + MLP value head)
                 │  FastAPI+transformers+peft (logprobs=True)
                 ▼
            [B] reap MCTS (OR/AND 树, PUCT, 验证器=Lean checkProof)
                 │  结果: solutions.jsonl / verdicts.jsonl
                 ▼
            [T] 训练器 (TRL GRPO + value 回归 / TTTRL 在线)
                 │  θ_{g+1}, φ_{g+1}
                 ▼
            [L] 累积库 growing_mathlib (L_g) ──context──> [A] [S] 索引用
```

## 0.3 术语表

| 术语 | 指代 |
|---|---|
| `p_*` | 目标难题（FATE-M 或用户命题） |
| variant | teacher 生成的、结构相似的简化/对称/推广变体 |
| Diff(v) | 1 − solve@B_low(π_g, v)；B_low=16 |
| Sim(v,p_*) | AST 共享率，τ≈0.7 |
| `L_g` | 累积库（已验证定理的 Lean 文件 + JSON 索引） |
| GRPO | group-normalized policy gradient，无 critic |
| TTTRL | 推理期训练：MCTS 搜索内在线更新（per-theorem LoRA step） |
| `ctx` | prompt 中附带的检索前提（库项） |

## 0.4 信息流（每代 g）

```
1. A 生成 N=1000 变体（批量 prompt 会话）
2. G 编译过滤 → D 标定(Diff) → P_g 实际入池(≤300)
3. B+C 对 P_g 每道题跑 MCTS（max_nodes=64, max_steps=64）
4. 成功路径 → checkProof → solutions.jsonl（正样本 + 证明脚本）
   失败路径 → verdicts.jsonl（负样本 + ucc)
5. T 训练：SFT 微调（若数据量不足则先 SFT）→ GRPO 一次性回合；
   或 TTTRL（per-theorem 在线更新，仅当启用标志）
6. 解出的定理并入 L_g；L_g 索引推送 [A]（next batch 注入 ctx）
7. E 评估门：固定 30 题 holdout，solve@B 单调不降才进入下一代
```

## 0.5 与 AlphaProof 的映射

| AlphaProof（Nature/blog 口述） | v1 实现 |
|---|---|
| formalizer = fine-tuned Gemini 翻译 1M 题 | teacher = DeepSeek V4 Flash + 闸门（更宽、更便宜） |
| solver = LM + AlphaZero RL | student = REAL-Prover-7B LoRA + reap MCTS |
| 验证 = Lean | 验证 = checkProof（同 Lean） |
| "verified proof → reinforce LM" | solutions.jsonl → GRPO/TTTRL 更新 |
| “self-generated variations during contest” | 课程闸门 P_g 的变体中含目标锚定阶梯 |
| 模型私有 | 全部开放（REAL-Prover-7B + 我们的权重 + 库） |
