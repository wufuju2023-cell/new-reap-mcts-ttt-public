# 03. BatchSolver：批量 driver 设计（解决 P2 无批处理）

## 3.1 输入格式（batch.jsonl）

```json
{"id": "fate-0001",
 "imports": ["Mathlib.Algebra.Order.Ring.Star"],
 "theorems": [        // 每个 theorem 独立跑，但共享 imports
   {"name": "aux", "statement": "∀ {m n : ℕ}, ..."}
 ]}
```

## 3.2 Lean 侧 driver（`reap-v1/MCTSDriver.lean`）

```
elab "v1batch" : command => do
   -- 1) 读 batch.jsonl（IO）
   -- 2) 对每个 theorem：生成临时 MVar（用 Theory/runTactic 方法打开目标）
        → mkProofCheckContext
        → Reap.TreeSearch.runMCTS generatePolicyValue (maxNodes:=reap.max_goals…)
        → 若 solution? 存在： replaySolvedNode + checkProof
        → 写 RolloutSink 行（node_visited 全程；task_done 结尾）
        → 写 solutions/failures 行
   -- 3) 每 task 完成 `touch state/<batch>/<id>.done`
```
- 与上游 `reap!!` 差异：**无 widget、无 async、无 UI**；结果只写文件；错误完整捕获。
- 每个 worker 的 Lean 进程**只加载一次**（imports 在进程间无共享——module 加载 ~1-3 分钟一次，per-worker 摊销）。

## 3.3 Python 编排（app/v1_run.py）

```
usage: v1_run.py --batch batch.jsonl --workers 4 --out out/b1
  --policy http://127.0.0.1:8760   (或缺省=policy_server 的 /v1/chat)
  --value  http://127.0.0.1:8760/value
  --ps     http://127.0.0.1:8760/premises  (v1 可省略→ LeanSearch 副作用)
  --max-runtime 1800 --per-task-timeout 300
  --continue                      # 跳过已完成 .done，追加
```

行为：
- 发 worker 进程（`sudo docker run` 或直接 `lean --run` 于 reap-lean 镜像内）；
- 每 worker 记录 stdout/stderr 到 `logs/worker<N>.log`（滚动）；
- 聚合 `solutions.jsonl`/`failures.jsonl`/`rttt_buffer.jsonl`；
- `--continue` 先扫描 `.done` 集合；
- 结束打汇总：solved/total、平均时长、verdict 分布。

## 3.4 断点/幂等（AGENTS 全局规则）

| 文件 | 语义 |
|---|---|
| `state/<batch>/<id>.done` | 每 task 完成 → `touch`（原子） |
| `state/<batch>/worker<N>.state` | worker 的当前 task id（进程杀掉可追） |
| `solutions.jsonl` | append-only，task_done 行含完整 script |
| 重跑规则 | 扫描 `.done` 跳过；其他追加行通过 `tree_hash` 去重 |

## 3.5 失败分类统计（结束打印）

```
verdict_dist = {parse: n, forbidden: n, timeout: n, errorMsgs: n, unassigned: n, kernel: n}
solve_rate = solved / total
```
> 这些统计用来判断策略是否"语法稳定"——配合 RTTT 的负样本。

## 3.6 与容器/云部署

```
docker run --rm --device /dev/kfd --device /dev/dri --group-add video \
  -v /workspace/batch:/batch -v /workspace/out:/out \
  ghcr.io/example-org/reap-lean:4.28.0-rc1-reap \
  bash -c "lake env lean /workspace/reap/Reap/Training/MCTSDriver.lean ... "
```
（详见 `docker/lean-reap.Dockerfile` + `environment-spec` 恢复剧本）
