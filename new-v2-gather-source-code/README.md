# new-v2-gather-source-code — CPU 侧源码归集（v2 全量；no-miner 现况）

> v2（Reap.Agent/Meta）CPU 侧代码实体归集；**no-miner**（暂不接任务挖掘器）。
> 该目录 = v2 改造的基底：与上游一致地用 Lean 写 MCTS 与多轮工具调用。

## 目录

```
new-v2-gather-source-code/
└─ reap-mcts-lean-v2-code-1/           # 既有 v2 原型（原样搬运）
   ├─ lean-v2/                         # Lean 侧
   │   └─ v2/{Eff.lean, Tower.lean, MetaActions.lean}
   └─ v2/                              # Python 原型侧
       ├─ mcts_loop.py                 #   MCTS 主循环（动作类型层；T1-T5 未实现）
       ├─ eff_registry.py              #   Eff 白名单（2 个 verifier）
       ├─ gate_lean.py                 #   Lean gate（podman 冷启动 per 节点）
       ├─ tower.py                     #   塔（register/depth/height, 全局单例）
       ├─ policy_client.py             #   策略客户端（mock/gpu 端点）
       ├─ mine.py                      #   （no-miner → 保留 API，未来再接）
       └─ smoke_v2*.py / runner.py     #   冒烟/执行器
```

## Lean 化方向（v2 改造主线 = 多轮 tool-call 的 T1-T5）

| 目标 | Lean 侧承担 | 说明 |
|---|---|---|
| T1 观测并入状态 | `Node.state` → `(ctx, obs, ok, tower)` 结构化 Lean 类型（`v2/Eff.lean` 的 `EffObs` 进入 `MetaActions.lean` 的状态） | 多轮观察闭环 |
| T2 参数结构化 | 动作 = Lean 结构/JSON-schema，约束解码出参数后 typecheck | `MetaActions.lean: Action` 已是代数类型——可扩展为带参数的 `effect (spec : EffSpec)`（现有） |
| T3 时序包 | Lean 写 `EffectSubroutine`（顺序执行 a1..am 的内部与预算/超时） | v1 的 `Step.evalTacticStr` 辅助组件复用 |
| T4 塔进状态 | Tower per-node（Lean `Tower` 作为状态成员；提交需 gate-ok） | 与 MCTS 分支隔离 |
| T5 gate 服务化 | Lean 常驻 gate（`#eval`/lean --run 服务模式）替代 podman 冷启动 | 与 GPU 端点同级 |

## 与 GPU 层契约（同 v1：视为已封装接口）

- 策略/价值/TTT 端点：同 v1（`policy_server`；`mode==v2` 时返回元动作文本）。
- GPU 侧不关心 CPU 的树/多轮；CPU 侧把 GPU 的 `choices[].text/logprob_avg` 当作**外部先验**喂给 `v2.MetaActions` 生成/校验。
