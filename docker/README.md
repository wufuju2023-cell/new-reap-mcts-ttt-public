# 容器职责与本地运行示例

CPU/Lean 容器负责证明状态、MCTS 和 kernel 验证；GPU 服务负责 policy/value 推理和可选的 TTT 更新。两者通过 HTTP 与 JSONL 交换数据，不把凭据或模型权重写入仓库。

## 构建

```bash
podman build -f docker/lean.Dockerfile -t reap-lean:local .
podman build -f docker/reap-lean.Dockerfile -t reap-lean-runtime:local .
podman build -f docker/train.Dockerfile -t reap-train:local .
```

## 接口

| 端点 | 用途 |
|---|---|
| `POST /v1/chat/completions` | 返回候选动作和 logprob |
| `POST /value` | 返回 value 服务约定的 score |
| `POST /ttt_step` | 可选的在线 policy/value 更新 |
| `GET /health` | 服务状态和 checkpoint 状态 |

示例服务地址使用 `127.0.0.1` 仅代表本机；部署到其他环境时通过配置或环境变量传入地址。

## 凭据与模型

模型下载、容器仓库登录和远程执行所需的令牌必须通过运行时环境变量或平台 secret 注入。不要把 token、SSH 私钥、Cookie、实例 ID、运行快照或模型权重提交到 Git。

完整的云平台控制脚本和真实运行证据未包含在公有化快照中；请在自己的基础设施上重新配置。
