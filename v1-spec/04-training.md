# 04 — 训练（SFT → GRPO → TTTRL）

## 4.1 阶段 P0：跨模型 SFT（若当前 policy 非 REAL-Prover 微调版本）

损失（token-mask）：

$$\mathcal{L}_{\mathrm{SFT}}=-\mathbb{E}_{(x,\mathrm{ctx},a)\sim D_0}\sum_t\log\pi_\theta(a_t\mid x,\mathrm{ctx},a_{<t})$$

- 输入 `D_0` = 50k state_tactic_pairs（a model registry/hf-mirror 拉取）+ 课程正样本；
- 仅 adapter 可训练（LoRA r=32）；lr 2e-4 cosine；batch=8×grad_accum=16；≤2 epochs。

## 4.2 阶段 P1：GRPO（主体训练回路）

对题目 $p$ 采样 G=8 条 MCTS rollout（我们设 group 内部**同 prompt**，利于组内基线）：

$$\hat A_g = \frac{r_g-\mathrm{mean}(r)}{\mathrm{std}(r)+\epsilon},\quad \mathcal{L}_{\mathrm{GRPO}}=-\frac{1}{|G|}\sum_g\frac{1}{T}\sum_t\min\left(\rho_{g,t}\hat A_g,\ \mathrm{clip}(\rho_{g,t},1-\epsilon,1+\epsilon)\hat A_g\right)$$

$$\rho_{g,t}=\frac{\pi_\theta(a_{g,t}\mid s_{g,t})}{\pi_{\theta_{\mathrm{old}}}(a_{g,t}\mid s_{g,t})}$$

- 用 **server 返回的 logprob（log π_old）** 构造 importance ratio —— 这正是选定
  FastAPI+transformers 的原因（llama.cpp/vLLM 均无法保证同一 logprob）；
- 值分支（若用 GRPO 开关默认值头不作为基线，但仍**单独回归**）：$\mathcal{L}_V$（§1.2）；
- KL guard：$\beta=0.02$，`ref = P0 输出 checkpoint`；
- 每次训练 ≤3 内部 epoch，训练完成即换 adapter（`adapter_id = P1_g<timestamp>`），server reload 原子化。

## 4.3 阶段 P2：TTTRL（测试时训练，对应 AlphaProof "contest loop"）

- 模式：搜索题目 $p$ 的 rollout 期间，教师=policy 自己 API 调用；每次（state,tactic,verdict）事件一次在线小步：
  - policy：$\theta \leftarrow \theta-\alpha\,\nabla[-\hat r\cdot\log\pi_\theta(a\mid s)]-\alpha\beta\,\nabla\,\mathrm{KL}[\pi_\theta\|\pi_{\theta_{\mathrm{base}}}]$
  - value：$\phi \leftarrow \phi+\alpha_V\,\big(\hat r+\gamma V_\phi(s')-V_\phi(s)\big)\cdot\nabla V$
- **per-theorem adapter_id**：每题初始化新 LoRA 副本；允许 "memory bank"（继续用前题 adapter）；eval 前必须销毁；
- 预算：每道搜索内 ≤16 梯度步 / 每节点 ≤1。强制更新节流：仅当
  $\Delta\log p>\varepsilon$ 且网络时延 <2s 时触发（CPU→GPU 同步）。

## 4.4 数据设计（对照AlphaProof：verify-only 强制）

- 正样本：solutions.jsonl（kernel 验证轨迹），权重 w=1；
- 负样本：verdicts.jsonl 中 error/forbidden/timeout 对，仍以 logprob 计算优势：
  $\hat r=-0.1$（error）;
- 不做 "soft-label"（如状态相近也奖励）——保持干净，防止 reward hacking 泄漏。

## 4.5 检查点/回滚

- 每代后备：`checkpoints/P1_g/`（`config.json` + `adapter` + `score@3`）；基线 `P0` 永远保留；
- 门断：hard eval 集（固定 30 题，不含课程池），solve@B 相对 P0 **不得低于 85%**；
- 破坏性诊断：由 eval 收敛率 drop 判定 + KL 值超过阈值 $\kappa=0.5$ 回滚。

## 4.6 可量化目标（v1 口径）

| 目标 | 指标 |
|---|---|
| v1 可行 | FATE-M 子集 100 题 solve@64 ≥ 50%（≤ 一周回滚） |
| v1 课程增益 | TTT 开/关对 P1 的 solve@B 差分 ≥ +5pt |
| 库增益 | P_g 中引用 `L_g` 的比例 ≥30%（消融关闭库） |
