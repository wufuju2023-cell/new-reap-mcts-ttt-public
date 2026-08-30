# 07 · 模型与价值头

> 双头网络：**Policy head**（生成 tactic + prior）与 **Categorical value head**（64 档剩余距离 $d\in[1,64]$，搜索效用 $V=-d$）。

回目录：[wiki 首页](README.md) ｜ 上一篇：[Rollout 管线](06-rollout-pipeline.md) ｜ 下一篇：[分布式基础设施](08-distributed-infrastructure.md)

---

## 1. 当前形态：REAL7B full-v3（64 档距离头）

> 依据 `reap-new-update-model` `master` 的 `discussion/new_value_head_in7b_ex1/`（F1 / H1 真实成功案例），**不再是**早期版本的标量 `[-1,1]`+随机初始化。

**核心语义（README 原文）**：

```
非终态距离：d ∈ [1,64]        搜索效用：V(s) = -d
已证明终态：d=0, V=0          Lean 非法动作：丢弃
形式化确认的死节点：-∞         预算耗尽/未找到证明：unknown（不是 -∞）
```

**结构**（冻结 REAL-Prover 7B 表征，只训小头）：

```
hidden state (3584)
  -> Linear(3584, 256) -> SiLU -> Linear(256, 64) -> logits over distance bins 1..64
```

- 参数 934,208；离线目标 = 距离档**交叉熵**（unweighted CE，AdamW 1e-3 / wd 0.01 / seed 20260829 / batch 4096 / ≤30 epoch early-stop）；
- 推理解码：`p = softmax(logits)`，`d = Σ k·p[k]`，`V = -d`（MCTS 只在接口处变号）；
- 数据：train 205,628 个 LeanTree 状态（80k + 125,628 扩展，来源 manifest 绑定）；val/test 各 8000；sample/state/root/theorem-family 四层 split 隔离；
- 随机对照：**同结构、同 seed、同训练前初态的精确初态 R64**（不是任意随机头）。

## 2. 为什么 64 档 categorical 而不是单标量

1. 保留距离不确定性（softmax 分布可形状化），期望值仍给 MCTS 可解释标量；
2. 在线小数 target 可投影到相邻两档，形成 **two-hot categorical target**（`distance_two_hot`），不必伪造整数标签；
3. 代价：64 截断后长距离区分变弱、分布外状态可能过度乐观——必须用真实搜索轨迹 + Lean 结果审计。

## 3. 在线（TTT）联合更新

REAL7B 路线的题内 TTT 是 **LoRA + categorical 头 + optimizer 同一步更新**：

- 在线 target = 本题真实 MCTS 的有限 `search_visit_backup`（不是失败→-∞）；
- target 裁剪到 `[1,64]`，小数用 two-hot CE；policy 项 + 对冻结 base policy 的 KL 约束同时存在；
- 更新必须有真实参数/optimizer 变化 + policy version 递增 + 后续 generation 消费（`online_update_consumed_by_later_generation`）；
- 已知限制（H1 案例落记）：`selection_value_refresh=false` 时，learn 后旧节点缓存值不重算——新生成/新 value 前向消费新版本，但旧节点回访不归因于更新后头。

**历史形态（早期公开快照）**：标量 `Linear(H,256)→SiLU→Linear(256,1)→Tanh→V(s)∈[-1,1]`，`scalar`/`distance` 两种 HTTP 输出模式（见 [app/VALUE_HEAD.md](../../app/VALUE_HEAD.md)），backbone BF16 + head FP32；该形态已被 full-v3 距离头取代为当前主线。

## 4. 怎么判定“好”与“够好”

- 离线门：NLL / MAE / 根内排序（within-root order）/ 公共 pair——只证明“学到距离结构”，**不能**替代端到端；
- 相对选择顺序：完整证明数 + 独立 Lean → value 导致的关键合法后继/回访 → 跨题稳定性 → 独占成本；
- F1 matched pair 证据链：相同 policy/RNG 下 4 个候选，full-v3 访问 `[0,7,0,1]` vs random `[0,4,1,3]` → 回访关键存在状态 → 后续 `simp` 闭合（独立 Lean success），random 臂耗尽；
- 20 题矩阵未完成前：full-v3 是“最好但未必够好”，不能宣称稳定默认。

## 5. 配置锚点（v1-spec/01，未变部分）

- Policy：`FrenzyMath/REAL-Prover`（Qwen2.5-Math-7B 微调，BF16，REAL7B 冻结特征）+ LoRA；
- 推理：FastAPI OpenAI 兼容端点，`n=6, temperature=0.99, max_tokens=1024, logprobs=true`（token 级；logP<-30 截断防 PUCT NaN）；
- 不依赖 vLLM（gfx1100 不在 vLLM ROCm 官方支持矩阵）。

---

## 溯源（点击跳转）

> 举例在私有主仓 `reap-new-update-model`（master），公开快照不包含；以下为 GitHub 链接。

- [discussion/new_value_head_in7b_ex1/README.md](https://github.com/wufuju2023-cell/reap-new-update-model/tree/master/discussion/new_value_head_in7b_ex1)（REAL7B 7B 新价值头总入口：设计 / F1 / H1 / 复现）；
- [01_设计说明/01_Value设计与评价方法.md](https://github.com/wufuju2023-cell/reap-new-update-model/tree/master/discussion/new_value_head_in7b_ex1/01_设计说明)（语义 / 防泄漏 / 结构 / 接入 MCTS / 课程与 TTT / AlphaProof 对应）；
- [01_设计说明/00_术语表.md](https://github.com/wufuju2023-cell/reap-new-update-model/tree/master/discussion/new_value_head_in7b_ex1/01_设计说明)；
- [02_成功案例/01_F1匹配随机头因果案例.md](https://github.com/wufuju2023-cell/reap-new-update-model/tree/master/discussion/new_value_head_in7b_ex1/02_成功案例) + [02_成功案例/02_H1平方望远镜课程成功](https://github.com/wufuju2023-cell/reap-new-update-model/tree/master/discussion/new_value_head_in7b_ex1/02_成功案例)；
- 实现代码：[train_value_head.py](https://github.com/wufuju2023-cell/reap-new-update-model/blob/master/discussion/new_value_head_in7b_ex1/02_成功案例/02_H1%E5%B9%B3%E6%96%B9%E6%9C%9B%E8%BF%9C%E9%95%9C%E8%AF%BE%E7%A8%8B%E6%88%90%E5%8A%9F/code/train_value_head.py)、[categorical_search_backend.py](https://github.com/wufuju2023-cell/reap-new-update-model/blob/master/discussion/new_value_head_in7b_ex1/02_成功案例/02_H1%E5%B9%B3%E6%96%B9%E6%9C%9B%E8%BF%9C%E9%95%9C%E8%AF%BE%E7%A8%8B%E6%88%90%E5%8A%9F/code/categorical_search_backend.py)、[online_ttt.py](https://github.com/wufuju2023-cell/reap-new-update-model/blob/master/discussion/new_value_head_in7b_ex1/02_成功案例/02_H1%E5%B9%B3%E6%96%B9%E6%9C%9B%E8%BF%9C%E9%95%9C%E8%AF%BE%E7%A8%8B%E6%88%90%E5%8A%9F/code/online_ttt.py)；
- 早期标量版本：[app/VALUE_HEAD.md](../../app/VALUE_HEAD.md)、[v1-spec/01-policy-value.md](../../v1-spec/01-policy-value.md)。
