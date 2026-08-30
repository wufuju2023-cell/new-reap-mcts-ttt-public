# 11 · 仓库地图

> 从一个读者视角：这个公开快照里**每一处目录是什么、干什么、怎么跑**。

回目录：[wiki 首页](README.md) ｜ 上一篇：[开放范围与下一步](10-open-and-next.md)

---

## 0. 一句话总览

面向 Lean 形式化证明的研究型原型：CPU 侧**搜索/验证在 Lean 内**，GPU 侧**policy/value 按标准 HTTP 端点外置**，`app/` + `v1-spec/` + `plan/` + `explain/` + `discussion/` + `lecture/` 构成"机制 → 协议 → 计划 → 论证 → 教案"的完整文档链。

## 1. 目录表

| 目录 | 是什么 | 速读入口 |
|---|---|---|
| `Reap/`（在 `lean-v1/` 下） | 上游 Lean MCTS 核心：`TreeSearch/{Basic,MCTS,BestFirst}`、`Tactic/{Step,State,Generator,Syntax,WallClock,TreeSearch}`、`PremiseSelection` | `lean-v1/Reap.lean` |
| `lean-v2/` | 结构化状态、参数化动作、多轮子程序 + V2 元层（`Eff`/`MetaActions`/`Tower`）Lean 草图 | `reap-mcts-lean-v2-code-1/README.md` |
| `reap-mcts-lean-v2-code-1/` | V2 **最小可运行骨架**（Lean 编译 + Python harness 双跑） | `README.md`（接受命令表） |
| `new-v1-gather-source-code-cpu/` | CPU 侧 V1 全量源码归集：`reap-upstream/` + `reap-training/`（RolloutSink/Verdict）+ `python-driver/`（薄驱动） | `README.md` |
| `new-v2-gather-source-code/` | V2 源码归集（含 `reap-mcts-lean-v2-code-1` 嵌套） | `README.md` |
| `app/` | **GPU 侧服务**：`policy_server.py`（policy+value+TTT）、`value_head.py`、`train_value_head.py`、`train_sft.py`、`v1_run.py`/`v1_sink.py`、`rttt_demo.py`、`mock_policy_server.py` | `VALUE_HEAD.md` |
| `v1-spec/` | 与云平台无关的 V1 协议与训练方法（00 综述 → 04 训练 → 07 runbook） | `00-overview.md` |
| `plan/` | 研究计划 11 篇（动机/架构/环境/数据/RL 更新/评估/路线图/后续训练/TTT/递归自改进/课程） | `00-index.md` |
| `explain/` | 深度分析归档：编号 1–13（价值头/难度/harness/兼容性/元编程/V1V2/数学驱动/上下文/MCTS 谱系/self-play/教师进化…）+ `reap-mcts-lean-v1/` + `reap-mcts-lean-v2/` + `wiki/`（本知识页） | `explain/README.md` |
| `discussion/alphaproof-value-head/` | AlphaProof 从零到完整机制讲授讲义（搜索/Value/TTT） | 目录 README |
| `lecture/` | 教案（road-map） | `lecture/1-road-map.md` |
| `docker/` | 通用容器构建：`lean.Dockerfile` / `reap-lean.Dockerfile` / `train.Dockerfile` | `docker/README.md` |
| `tests/` | 单测（`test_value_head.py` 等） | `python -m unittest` |
| `tools/` | `scan-secrets.sh`（提交前机密扫描）、`check_md_math.mjs`（KaTeX 数学校验） | 用法见下 |
| `.github/workflows/docker.yml` | 分支推送时构建并推送 `ghcr.io` 的 reap-lean 镜像 | workflow 文件 |

## 2. 运行约定

- **模型路径、容器镜像、服务地址、凭据**一律由部署环境通过参数/环境变量注入（`DEEPSEEK_API_KEY` 等）；CPU 侧冻结为接口契约。
- 多轮工具调用必须把结构化观测写回下一个状态；外部工具凭据来自运行时环境变量。

## 3. 本地检查

```bash
python -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=reap-mcts-lean-v2-code-1 python -m v2.smoke_v2          # V2 单元
PYTHONPATH=reap-mcts-lean-v2-code-1 python -m v2.smoke_v2_full     # V2 全链（真验证 + MCTS）
PYTHONPATH=reap-mcts-lean-v2-code-1 python -m v2.runner --steps 8  # 元动作 demo
bash tools/scan-secrets.sh                                         # 提交前
node tools/check_md_math.mjs explain/wiki/*.md                     # doc 数学校验
```

Value head 离线训练示例：

```bash
python app/train_value_head.py --base /workspace/data/real-prover \
  --data /workspace/out/value_train.jsonl --output /workspace/out/value_head.pt \
  --epochs 3 --batch-size 8
```

## 4. 发布（公开化）口径

本快照不包含运行证据、云实例控制脚本、模型权重、私有环境配置或嵌套私有仓库（详见 [PUBLICATION.md](../PUBLICATION.md)）。请勿提交 `.env`、私钥、访问令牌、模型权重、运行日志或带个人/实例标识的快照。

---

## 溯源

- 根 `README.md`、`PUBLICATION.md`；
- 结构内文档入口：各目录 README（见上表）。
