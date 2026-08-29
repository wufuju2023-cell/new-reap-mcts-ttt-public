# 02. RolloutSink：训练样本面 schema（解决 P3 无轨迹面）

每条**事件**一行 JSONL（append-only；`\n` 在字符串字段中转义为 `\\n`）：

```
{"kind": "node_visited",
 "task_id": "fate-0001",
 "ts": "2026-08-27T07:20:11.123Z",
 "tree_hash": "abc123",              # 该 task 树指纹（含种子，便于去重/回放）
 "node_idx": 37,
 "parent_idx": 21,
 "depth": 4,
 "state_pp": "⊢ n / m ∣ n ∧ ...",     # 通过 Tactic.State.stateKey 加 pp 全文
 "state_key": "sha256:...",          # 供去重/缓存
 "goal_count": 2,
 "partial_goal": 0,                  # AND-child focus index, 或 -1
 "tactic": "apply Nat.div_dvd_of_dvd",
 "verdict": {"class": "ok" | "parse" | "forbidden" | "timeout" | "errorMsgs",
             "messages": "…首 200 chars…",
             "kernel_check": true|false},
 "policy": {"logprob_avg": -12.3, "n_samples": 6, "sample_idx": 2},
 "value": {"score": 0.412, "source": "policy_server"},
 "prior_p": 0.00004,
 "num_visit_child": 0,
 "was_solved": false,
 "children_expect": "and"
}
```

## 2.1 规则与约束

1. `verdict.class` 严格枚举 6 类（对应 `EvalError`），禁止自由文本；
2. `kernel_check=false` 时 `class=ok` 不允许（Step.checkProof 强制 true 才能算 ok）；
3. 每个节点**最多**一行，重复采样只写 `sample_idx`（避免膨胀）；
4. `state_pp + tactic` 哈希即主键（重跑同 tree_hash 时丢弃）；
5. 值/策略来源记录 `source`（policy_server / local_policy 等等，训练时校验版本一致）；
6. 文件轮转：单个 sink 文件 >200MB 自动 `.1`/`.2`（训练读 rolling 列表）。

## 2.2 事件族（三类）

| kind | 触发 | 用途 |
|---|---|---|
| `node_visited` | 每次扩展 | 策略/价值监督（正负样本核心） |
| `task_done` | 每题结束（solved/failed） | 胜负标签、树收益、结算 R |
| `rttt_update` | TTT 步实际发生 | 在线学习审计（loss/kl/lr/adapter hash） |

## 2.3 进训练管线的消费面

```
Sink → 三个下游:
  A. solutions.jsonl   (task_done + solved 且含 script)
  B. failures.jsonl    (task_done 未解 + 全轨迹 node_visited)
  C. rttt_buffer.jsonl (RTTT 用的实时流，见 §5)
```
`hash.txt` 每次滚动记录文件 sha256，防篡改/防重复训练。
