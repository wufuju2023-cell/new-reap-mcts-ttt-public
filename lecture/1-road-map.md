# Reap MCTS × TTT 学习路线图

本路线图面向希望理解 Lean 证明搜索、MCTS、policy/value 和 test-time training 的读者。
它只列出公有化快照内可用的材料；运行证据、云端控制面和私有部署文档未随本分支发布。

## 1. 从理论到系统

建议按以下顺序阅读：

1. `README.md`：项目边界与公有化约定。
2. `explain/1-价值头的作用.md`：value 在证明搜索中的作用。
3. `explain/10-mcts-usage-and-alternatives.md`：PUCT、MCTS 和替代搜索方法。
4. `discussion/alphaproof-value-head/README.md`：AlphaProof value 的导读。
5. `discussion/alphaproof-value-head/07_AlphaProof从零到完整机制_搜索_Value与TTT.md`：policy、value、Lean、MCTS 和 TTT 的完整关系。

阅读时务必区分三件事：理想的最优规划值、当前策略下的期望回报、以及具体 value head 的预测。未训练的 value head 只能作为未校准启发式，不能直接等同于剩余证明距离。

## 2. V1：Lean 搜索与训练接口

- `plan/00-index.md` 到 `plan/07-roadmap.md`：V1 的动机、架构、环境、数据、训练和评估。
- `v1-spec/`：更接近实现合同的 V1 规格。
- `explain/reap-mcts-lean-v1/`：CPU/Lean 搜索、rollout sink、batch solver 和质量闸门。
- `new-v1-gather-source-code-cpu/`：上游 Reap CPU/Lean 参考代码。

优先关注以下源码：

- `Tactic/Step.lean`：动作执行、失败分类和 kernel 验证；
- `Tactic/Generator.lean`：policy/value HTTP 协议；
- `Tactic/TreeSearch.lean`：OR/AND、PUCT、progressive sampling 和 backup；
- `app/`：轻量 policy server、value head 和本地训练工具。

## 3. Value head 与 TTT

从 `app/VALUE_HEAD.md` 开始，再查看：

- `app/value_head.py`：独立 value head、序列末 token 提取、checkpoint 工具；
- `app/train_value_head.py`：使用 verifier 产生的标签做离线训练；
- `app/policy_server.py`：policy/value 推理、value-only training 和可选 TTT；
- `tests/test_value_head.py`：协议和数值边界测试。

一个稳定的训练顺序通常是：已验证的 Lean 轨迹监督 → held-out 校准 → MCTS 搜索蒸馏 → 可选的在线 TTT。不要把预算耗尽的失败直接当作“不可证明”的监督标签。

## 4. V2：元编程与多轮工具调用

阅读顺序：

1. `explain/reap-mcts-lean-v2/00-overview.md` 至 `04-training-and-metrics.md`；
2. `explain/reap-mcts-lean-v2/多轮tool-call/`；
3. `explain/reap-mcts-lean-v2/emergent-tool-use/`；
4. `reap-mcts-lean-v2-code-1/` 与 `lean-v2/`。

核心原则是：工具观测必须写入下一个搜索状态；同一父状态的多个 policy sample 是 OR 兄弟分支，而不是连续工具调用。若需要把一段顺序工具链作为高层动作，应使用受预算限制的 `EffectSubroutine`，其内部仍应逐步执行并记录观测。

## 5. 运行与安全

本仓库只提供通用本地/容器示例。模型路径、镜像标签、服务地址和凭据由运行时环境配置。提交前执行：

```bash
bash tools/scan-secrets.sh
```

不要提交密钥、令牌、Cookie、私钥、模型权重、训练输出、个人路径、云实例标识或运行快照。
