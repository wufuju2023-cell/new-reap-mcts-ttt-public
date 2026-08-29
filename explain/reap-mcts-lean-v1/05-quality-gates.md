# 05. Lean✓ 集成与测试/质量门（上游 #4/#3 承接 + 验收）

## 5.1 Lean 环境闭环（本 spec 核心可执行路径）

1. **reap-lean 镜像**（`ghcr.io/example-org/reap-lean:4.28.0-rc1-reap`，构建中）：
   - lean 4.28.0-rc1（容器已验证）+ reap clone + lake build（openAI_client/batteries/requests 内置）；
   - 运行：`docker run --rm ghcr.io/... bash -c "cd /workspace/reap && lake env lean <driver>"`。
2. **验证信号**：BatchSolver 的每题结果以 `checkProof`（Step.checkProof）为唯一 solved 判定——
   **没有"只是 close 但未 kernel 验"的成功**（防 reward hacking）。
3. **policy/value 端点**：全程指向本地 `policy_server`（8760），形成"Lean→server→Lean"循环；
   无外网 LLM 依赖（完全受控，logprobs 由 server 返回）。

## 5.2 测试策略（承接上游 #4：TryThis 可测性）

- `#guard_msgs` 化：把所有输出改为 **Lean 标准 info/error 消息**（`logInfo` / `throwError` 携带 context 消息），
  使测试可 `#guard_msgs in <cmd> => info "…"`（信息层可捕获）；
- 单元测试：`Reap/Training/Tests/*.lean`：
  - verdict 分类每个分支（parse/forbidden/timeout/errorMsgs/ok+kernel/unassigned/aux/kernelcheck）各一条；
  - 状态去重（同 state pp 不同 tactic 同 Node 去重）；
  - RolloutSink 每行 schema 校验器（python `v1_sink.py --validate`）。
- 端到端冒烟：`v1_run.py --batch smoke.jsonl --workers 1 --budget 3`（一道简单题期望 solved，一道非法题期望 failure）。

## 5.3 错误信息优化（承接上游 #3）

- 配置未设置（policy/ps/value endpoint 为空）→ 启动时**一次性显式错误**：
  `[Reap.Training] config: policy_endpoint not set; set via set_option reap.policy_endpoint "http://…"`,
  并 `exit code 2`（trainer 可判）；
- LLM 请求错误失败在 sink 中标记 `verdict.class = "infra_error"` 并带 server response 摘要（非 panic）。

## 5.4 交付物清单

- `reap-v1/`（Lean：RolloutSink/BatchSolver/Verdict/Config/MCTSDriver/Tests）
- `app/v1_run.py`、`app/v1_sink.py`、`app/rttt_client.py`
- `docker/reap-lean.Dockerfile`（镜像） + `docker/train.Dockerfile`
- 输出样例：`out/solutions.jsonl` / `failures.jsonl` / `rttt_buffer.jsonl` / `rttt_metrics.jsonl`
- 文档：本目录（投递 00-05）

## 5.5 验收（DoD 复核）

1. 见 00-overview §0.4 的五条；
2. 关键行：**单命令跑通 → 100 题 batch → ≥80% solve 基线（use REAL-Prover pretrained policy）→ 记录 metrics**。
