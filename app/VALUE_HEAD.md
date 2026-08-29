# Value Head 使用说明

本目录提供一个与 REAL-Prover policy 共享 backbone 的独立连续 value head，并
借鉴 `nanoproof` 的训练信号：用 Lean 验证成功的 proof trajectory、剩余证明
深度或 MCTS backup return 监督状态价值。当前实现不是把 `nanoproof` 的 64 个
离散 value token 直接移植过来，而是保留本项目原有的标量接口。

## 模型与数值语义

```text
backbone 最后一个有效 token hidden (H)
    -> Linear(H, 256)
    -> SiLU
    -> Linear(256, 1)
    -> Tanh
    -> V(s) ∈ [-1, 1]
```

`H` 从模型配置动态读取，不再硬编码为 4096。backbone 通常使用 BF16，value
head 使用 FP32。默认训练目标是验证器产生的归一化 discounted return；也可以
传入 `proof_depth`，脚本会按 `-min(depth, 64)/64` 转换成目标。

### HTTP 输出模式

- `scalar`（默认）：返回 `score = -V(s)`，符合本项目 `v1-spec/01-policy-value.md`。
- `distance`：把质量值映射到 `[1, max_distance]` 的正距离，适配采用
  `value/v1/chat/completions`、并在 Lean 侧再取负的 nanoproof/verified-collector
  风格客户端。

两种模式共享同一组 head 参数；不要在不匹配的模式下混用 checkpoint。模式和
`max_distance` 会写入 checkpoint 元数据，恢复时会校验。

## 文件

- `value_head.py`：独立 `ValueHead`、padding-aware hidden 提取、TD/discounted
  return 工具、原子 checkpoint、head-only trainer。
- `policy_server.py`：把 value head 接入 REAL-Prover、`/value` 推理、TTT 联合
  policy/value 更新、snapshot/restore。
- `train_value_head.py`：冻结 backbone、离线训练 head，生成 `value_head.pt`。
- `rttt_demo.py`：演示在 `/ttt_step` 中同时提交 policy 与 `value_target`。

## 离线训练

在 GPU 容器中准备 JSONL。每行至少包含以下字段之一：

```json
{"prompt":"<Lean state>","value_target":0.35}
{"state":"<Lean state>","proof_depth":8}
{"state":"<Lean state>","value_target":-8,"target_kind":"nanoproof"}
{"states":["s0","s1"],"rewards":[0.0,1.0],"gamma":0.99}
```

然后运行：

```bash
python /workspace/app/train_value_head.py \
  --base /workspace/data/real-prover \
  --data /workspace/out/value_train.jsonl \
  --output /workspace/out/value_head.pt \
  --epochs 3 --batch-size 8
```

脚本只使用显式监督字段；不会默认把旧的 `value.score` 当标签，以免把随机
value 预测自举成训练真值。若确实要迁移旧数据，显式加 `--allow-score`。

## 启动服务

```bash
python /workspace/app/policy_server.py \
  --base /workspace/data/real-prover \
  --value-head /workspace/out/value_head.pt \
  --output-dir /workspace/out \
  --port 8760
```

如果省略 `--value-head`，服务会在 `/workspace/out/value_head.pt` 存在时自动
加载；首次更新后会自动写入该路径。服务启动后可检查：

```bash
curl http://127.0.0.1:8760/health
curl -X POST http://127.0.0.1:8760/value \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"STATE: ..."}'
```

Lean 的 OpenAI client 形式也受支持：

```bash
curl -X POST http://127.0.0.1:8760/value/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"reap","messages":[{"role":"user","content":"STATE: ..."}]}'
```

## 在线 TTT 数据

`POST /ttt_step` 的每个 item 可包含：

```json
{
  "prompt":"<Lean state>",
  "target":"<tactic>",
  "r":1.0,
  "logprob_old":-4.2,
  "value_target":0.8,
  "done":true
}
```

也可以使用 `proof_depth`、`next_value` 或 `next_prompt`，服务会构造一步 TD
目标 `r + gamma * V(next)` 并裁剪到 `[-1,1]`。`value_loss`、更新次数和梯度
范数会在响应中返回；`/value/train` 可只训练 head，不更新 LoRA policy。

## 重要限制

仓库中没有可公开加载的、已经在 REAL-Prover 权重上训练完成的 value-head
二进制文件；`nanoproof` 上游也没有随源码提供这种 checkpoint。因此本次交付
的是可复现的训练实现、协议适配和验证测试，而不是声称随机初始化 head 已经
具备证明能力。要获得可用于生产搜索的 head，必须用 Lean-verified rollout 或
Mathlib proof trajectory 运行上述离线训练，并在独立 holdout 上评估排序质量。
