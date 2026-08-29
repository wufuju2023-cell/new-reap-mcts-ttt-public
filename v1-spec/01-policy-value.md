# 01 — Policy & Value 网络规格

## 1.1 策略（Policy）

- **模型**：`FrenzyMath/REAL-Prover`（Qwen2.5-Math-7B 微调，>8B 参数，BF16）。
- **训练**：LoRA（rank 32, alpha 64, dropout 0.05, 目标模块全部 attention+mlp）；
  checkpoint = adapter 文件 + 基础权重冻结。
- **推理协议**：FastAPI 实现 OpenAI `/v1/chat/completions` 兼容端点：
  - 请求：`{model, messages=[user 含 mkPrompt 格式], n=6, temperature=0.99, max_tokens=1024, logprobs=true}`
  - 响应：`choices[].message.content`（tactic 字符串，`<think>` 前缀由 reap 的 stripThinkingPrefix 处理）
  - logprobs：**返回 token-level logprob 数组**；reap 端求和 = `log π(a|s)`（`Generator.lean:18-27`）。
  - 依赖：`transformers` + `peft`；加载 `load_in_bf16=True, device_map="cpu"` 之后移 GPU；
    **不依赖 vLLM**（gfx1100 不在 vLLM ROCm 官方支持矩阵）。
- **prompt 模板（必须固定地复刻 reap）**：`Reap/Tactic/Generator.lean:73-82`：
  ```
  User: Please generate a tactic in lean4 to solve the state.
  Here're some theorems that may be helpful:
  Formal name: <n>
  Formal statement: <s>
  ...
  STATE:
  <ppProofState>
  TACTIC:

  Assistant:
  ```
  任何模板漂移 → 模型分布偏移。放 `tools/prompt_spec.md` 并写 golden 单测。

## 1.2 值网络（Value）

- **原理**：MLP head over policy backbone 的 last hidden states：

$$V_\phi(s) = \mathrm{MLP}_\phi\big(h_{\theta}(s)\big),\quad h\in\mathbb{R}^{4096}\to 256\to1,\ \text{tanh 输出}\in[-1,1]$$

- **训练分离**：head 与 policy adapter **同体更新但参数独立**（backbone 冻结或低 lr）；
  目标（MSE）：

$$\mathcal{L}_V=\mathbb{E}\big[(V_\phi(s)-G_t)^2\big],\quad G_t=\sum_{j\ge0}\gamma^j r_{t+j},\ \gamma=0.99$$

- **部署**：同一 FastAPI 暴露第二路径 `/value`：body `{state}` → `{"score": -V_φ}`（reap 期望最小化 score，故取负，保持 `Generator.lean:143` 兼容）。
- **初始化**：v1 用 policy 本身的值 prompt（LLM-JSON）完成少量 prefit 即切 head；若 head 不稳，回退 LLM-JSON 值（配置开关 `value_mode=head|llm`）。

## 1.3 服务端（一个进程全栈）

```
FastAPI :8000
 ├─ POST /v1/chat/completions   (policy; logprobs)
 ├─ POST /value                 (value head)
 └─ POST /ttt/step              (§04 TTTRL: 单步在线更新, 供 per-theorem 调用)
   （同一进程内管理 LoRA adapter 切换；TTT 与 serve 共用权重；
     serve 无状态, 每次请求带 adapter_id 可热切换 —— 支持每道题隔离）
```

## 1.4 集群与资源

| 内存 | 7B bf16 权值 ≈14GB；KV cache 2–4GB；ct 下激活 4–6GB | 48GB 充裕 |
|---|---|---|
| 吞吐 | single-user 顺序；batch 时同请求 n=6 并行生成 | 接受（探索用） |
| 并发 | 1 实例同时 1 个 reap 搜索；搜索-训练轮换成批 | 接受 |

## 1.5 数值与安全

- 温度 0.99 是 reap 默认（`Options.lean:43-46`）；训练集采样配对时需要
  logprobs 一致，使用 server 输出（不额外蒸馏）。
- **logprob 边界**：sum 之后 logP<-30 截断（防 float underflow/prior=∞
  引发 PUCT NaN）。llama.cpp 不提供梯度和 token 级 logprobs → 明确排除该路径。
