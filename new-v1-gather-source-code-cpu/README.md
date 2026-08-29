# new-v1-gather-source-code-cpu — CPU 侧源码归集（v1 全量）

> 目的：把 CPU 侧 V1 全部代码**实体归集**于此，作为"CPU 层尽量全 Lean 化"的改造基底。
> 参照目标：与原始 reap 仓库一致的结构（Lean 优先；python 仅缩门/编排）。

## 目录

```
new-v1-gather-source-code-cpu/
├─ reap-upstream/                # 上游 Reap Lean 源码（本地参考副本）
│   ├─ Basic.lean                #   （入口）
│   ├─ Options.lean              #   配置选项（endpoints/预算/γ/τ/c 等）
│   ├─ Test.lean                 #
│   ├─ Tactic/{Step,State,Generator,Syntax,WallClock,TreeSearch}.lean
│   ├─ TreeSearch/{Basic,MCTS,BestFirst}.lean
│   └─ PremiseSelection/{API,Syntax}.lean
├─ lean-toolchain                # leanprover/lean4:v4.28.0-rc1（与 reap 一致）
├─ lakefile.toml                 # 上游 lakefile（deps: openAI_client / batteries）
├─ reap-training/                # V1 训练扩展（Lean，可独立编译）
│   └─ Reap/Training/{Verdict,RolloutSink}.lean
└─ python-driver/                # 薄驱动（仅编排；搜索/验证留在 Lean 侧）
    ├─ v1_run.py                 #  batch 编排（生成 Lean 文件→容器执行→checkpoint）
    ├─ v1_sink.py                #  RolloutSink schema 校验（镜像 Lean 侧契约）
    └─ mock_policy_server.py     #  CPU mock（真模型时换 GPU 端点）
```

## 与 GPU 侧接口（视为已封装好的模型层）

CPU 侧依赖 GPU 侧**三个端点**（`policy_server.py` 已具备）：
```
POST /v1/chat/completions   {prompt, n, temperature}        → {choices:[{text, logprob_avg}]}
POST /value                 {prompt}                        → {"score": float}
POST /ttt_step              {items:[{prompt,target,r,logprob_old}]} → {loss,kl,steps}
POST /adapter/snapshot|restore
```
> CPU 侧冻结它们：只依赖契约，不关心 GPU 内部（训练/价值头/在线更新）。

## 术语对齐

- `Reap.TreeSearch`（上游）== CPU 侧搜索内核（Lean）。
- `Reap.Training`（本目录 reap-training）== V1 训练向扩展（rollout sink/batch 语义）。
- python-driver == 仅做「文件/进程/断点」的编排胶水（计划中留白：渐进 Lean 化，最终 driver 也可 Lean `#eval IO`）。
