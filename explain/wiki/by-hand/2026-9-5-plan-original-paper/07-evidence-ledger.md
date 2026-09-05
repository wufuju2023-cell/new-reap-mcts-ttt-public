# 07 — V1 证据定位表

本表只列 V1 release-time code 和真实结果。它不以旧文档或公开 prototype 作为架构证据。

## V1 源码

| 结论 | source of truth |
| --- | --- |
| 冻结 REAL-Prover 7B、LoRA session、policy generation | v1-result release source 的 gpu_runtime/real_backend.py |
| shared hidden backbone 的 categorical head | gpu_runtime/verified_backend.py |
| verified categorical label contract | gpu_runtime/verified_objective.py |
| OR / AND trajectory return 构造 | cpu_runtime/verified_trajectory.py |
| mixed replay + Mathlib learner | gpu_runtime/mixed_backend.py 与 mixed objective |
| HTTP policy token logprobs / value route | V1 gpu_runtime runtime / server source |
| Lean value consumer 的负号约定 | V1 CPU / Lean patch source |

release-time code archive 与本地 V1 source 文件 hash 对齐；因此这里可以同时引用源码和实际运行回执。

## V1 真实运行结果

| 结论 | evidence family |
| --- | --- |
| 两次 V1 mixed joint updates | evidence/current/latest-release-gpu 的 step receipts |
| 392 LoRA + 4 categorical head tensors changed | step receipt 的 parameter diff manifest |
| base remains frozen | same receipt 的 base fingerprint checks |
| R2 publication | checkpoint / release / weights metadata |
| R2 fresh-service consumption | evidence/current/latest-recovery-gpu |
| policy candidates 与 value 实际经 HTTP 返回 | recovery service intents / responses / report |
| recovery run 通过 8 gates | latest-recovery-gpu report |
| uploaded full-v3 snapshot | Hugging Face manifest / session：220,477,868-byte backend、adapter + value_head transfer、independent Lean acceptance |

latest-release wrapper 的最终 transport failure 不会抹掉已经完成并有 receipt 的 step-2 release；后续 recovery 以 exact published release 完成独立消费验证。两者应一起报告，不能只摘取任一侧。

## 断言门

| 想说的话 | 最低证据 |
| --- | --- |
| V1 critic 已训练 | committed update / release receipt，且 LoRA 与 head parameter diffs 存在 |
| V1 critic 可服务 | fresh-session load + policy/value HTTP consumption receipt |
| V1 critic 有用 | theorem-level heldout calibration 和 value-on/off search ablation |
| V1 优于 base | paired fixed-budget comparison |
| V1 已达到 AlphaProof TTRL | target variants、focused RL、paired target results、规模报告 |

uploaded full-v3 满足“artifact 可取得、adapter + head 有 acceptance provenance”；本地 R2 满足“fresh V1 runtime 已恢复服务”。两者都还不满足“critic 有用 / 已校准”。这个边界比“上传了模型”或“训练 loss 变化”更能保护实验结论。
