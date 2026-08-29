# Reap MCTS × TTT（公有化快照）

这是一个面向 Lean 形式化证明的研究型原型，包含 CPU 侧搜索、元动作/Eff/Tower 设计、GPU policy/value 接口，以及 value head 训练工具。

## 目录概览

- `app/`：policy server、value head、TTT 和本地 smoke 工具。
- `reap-mcts-lean-v2-code-1/`：V2 元动作与 MCTS 的最小 Python/Lean 原型。
- `lean-v2/`：结构化状态、参数化动作和多轮子程序的 Lean 草图。
- `new-v1-gather-source-code-cpu/`：CPU/Lean 参考实现和接口研究材料。
- `explain/`、`discussion/`、`plan/`：设计说明、训练目标和实验规划。
- `v1-spec/`：与具体云平台无关的 V1 协议和训练方法。
- `docker/`：通用容器构建示例。

## 基本原则

CPU 维护 Lean 状态、执行动作、验证证明并运行 MCTS；GPU 通过约定的 HTTP 接口提供 policy 候选和 value 估计。多轮工具调用必须把结构化观测写回下一个状态；外部工具的凭据只能来自运行时环境变量。

本快照不包含运行证据、云实例控制脚本、模型权重、私有环境配置或嵌套私有仓库。实际部署时请自行配置模型、Lean 服务和容器镜像。

## 本地检查

```bash
python -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=reap-mcts-lean-v2-code-1 python -m v2.smoke_v2
```

请勿提交 `.env`、私钥、访问令牌、模型权重、运行日志或带有个人/实例标识的快照。提交前运行 `bash tools/scan-secrets.sh`。
