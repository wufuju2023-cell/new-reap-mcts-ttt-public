# 07 — 运行手册（Runbook）

## 7.1 每日轮询（cron，SSH 会话）

```bash
# 0:00 课程生成（DeepSeek→闸门→入池）
cd /workspace/v1
python -m curriculum --generate 1000 --gate all --budget 350
# 2:00 求解与学生回滚展开
python -m rollout --pool current --nodes 64
# 5:00 训练与更新（GRPO 或 P2-TTTRL 模式）
python -m trainer --mode grpo --epochs 3
# 7:00 eValuate & gate
python -m eval --set holdout-30
```

## 7.2 首日 bootstrap（一次性）

```bash
# (1) SSH in
ssh -p <port> root@<host>
# (2) 环境
bash setup_env.sh
# (3) 拉模型（a model registry）
python -m fetch_models --hub <model-registry>
# (4) 服务自检
curl -X POST localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"reap","messages":[{"role":"user","content":"tactic for: proof example: (1:Nat); exact Nat.zero\n"}],"n":1,"logprobs":true}'
# (5) 跑通第一题
lake env lean test/trivial.lean
# (6) 第一轮 eval 基线
python -m eval --set fate-m-100 --weights realprover-7b-baseline
```

## 7.3 故障处理

| 现象 | 处理 |
|---|---|
| FastAPI 首次请求 3 分钟 | 预热 worker（`--live-load`）；用 `waitress` 已自含 |
| `logprobs` 请求返回 400 | 检查 chat 模板长度 > max_tokens；回退原生 completion API |
| DeepSeek 限流 | 加重试指数退避 ∓ 3s；避免 burst（≥ 30s 分段） |
| Lean 编译 404 | `lake env lean file.lean` 时 ensure `import Mathlib` + 下载 mathlib cache |
| checkProof 高失败率 | 确认 kernel toolchain ≠ s4 不匹配；reap 训练用 v4.28.0-rc1 代 |
| GPU util 低 | 检查是否用 GPU adapter；`reset` 后 `nvidia-smi`等价`rocm-smi` |
| TTT 误更新到 eval 数据 | 始终设 `--ttt-off` for eval；白名单 eval 集不可触发 TTT |

## 7.4 每世代里程碑（Gate）

| Gate | 条件 |
|---|---|
| G-A | initial baseline solve@64(FATE-M) 记录并公示 |
| G-B | P1 GRPO ≥ A1 +5pt |
| G-C | 库比例 ≥30%；否则暂停库自动扩展，改人工标注库 |
| G-D | holdout-30 每三代不下降（≥-2pt） |

## 7.5 artifact 管理

```
/workspace/v1/
├ checkpoints/   P0_P1_g...   (adapter；保留 5 代)
├ libraries/     growing_mathlib.lean + index.json
├ runs/<date>/
│  ├ variants.jsonl  diff_index.json  solutions.jsonl  verdicts.jsonl
│  ├ evals.jsonl  summary.json
├ patches/       reap tree-exporter patch
└ prompts/       teacher_v1.md  prompt_spec.md（golden test）
```

## 7.6 退出/清点

- 每轮结束输出 `summary.json：{cycle, solve@B, Δ, credits_left, next_action}`；
- 每周五做一次 3h 大回滚（保守策略：若 crash，重拉 `P1g-2`）。
