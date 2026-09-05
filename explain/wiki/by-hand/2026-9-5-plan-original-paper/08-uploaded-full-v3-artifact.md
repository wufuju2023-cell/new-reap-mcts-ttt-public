# 08 — 上传的 full-v3 V1 artifact：身份与评估边界

本页记录 2026-09-05 在 Edge Default profile 的已登录 Hugging Face 会话中实际读取到的 artifact metadata。full-v3 是实验编号，不代表模型结构版本、训练规模或质量等级。

## 已验证的 artifact identity

| 字段 | 值 |
| --- | --- |
| repository | alpha-proof-open-source / alphaproof-full-v3-value-head |
| visibility | private |
| uploaded commit | c59450c，signed / verified |
| snapshot schema | reap.gpu.snapshot.v1 |
| session / experience | exp-e24fc3c0a20c-01 |
| snapshot role | release |
| backbone | FrenzyMath / REAL-Prover，revision fe76f68d9a88f342cb7b546307c20292fea9cced |
| hidden size | 3584 |
| transferred components | adapter、value_head |
| value-head shape | linear-3584-silu-256-linear-64 |
| backend file | backend.json，220,477,868 bytes |
| backend SHA-256 | becf7c4c6650fca4b11b1087ddd86f4c5dfb69f9b21913bc3f8c81c8f1c37479 |
| session acceptance | independent Lean，completed / passed |

它确认了“shared REAL-Prover policy base + trained LoRA adapter + categorical value head”的 artifact 已被上传。它不是 standalone Transformers checkpoint；必须由匹配的 REAP runtime 解码 torch-save-base64 snapshot，并将 adapter 与 64-bin head 挂到匹配 base revision。

## 它能证明什么

- artifact 实际包含 adapter 与 value-head weights；
- head 是 64-bin categorical MLP，而不是 standalone scalar head；
- provenance session 记录 independent Lean acceptance passed；
- base revision、snapshot schema、大小和 checksum 可用于精确完整性校验。

## 它不能证明什么

- 64-bin value 的 calibration、ranking error 或 holdout quality；
- value-on 比 value-off 更好；
- 它与本地 D=8 R2 release 的 weights 或 support 可互换；
- full-v3 比任意其他 V1 artifact 更强；
- AlphaProof-scale TTRL 已完成。

因此，artifact 的第一个实验目标应是 **load-and-evaluate**，而不是直接宣传能力。

## 下载后不可跳过的检查

1. 对 backend.json 计算 SHA-256，并匹配本页 digest；
2. 读取 snapshot schema、session identity 和 transfer groups；
3. 用固定 REAL-Prover revision 启动匹配 V1 runtime；
4. 检查 LoRA target modules、64-bin head tensor names / shapes / dtypes；
5. 用 golden prompt 验 policy token logprobs，用 golden state 验 expected-distance output；
6. 在 theorem-level holdout 上执行 value-on/off、real-prior/uniform 与 frozen-base comparisons。

只有前五项成功，才能说 full-v3 artifact 可加载；只有第六项成功，才能讨论它是否是好 value head。
