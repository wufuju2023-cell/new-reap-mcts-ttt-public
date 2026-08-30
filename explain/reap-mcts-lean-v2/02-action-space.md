# 02. 元动作空间与类型保证

> 对应 7-reap-v1-v2 §3 的第三个组件；实现"$\mathcal{I}_{\mathrm{type}}$：动作即类型检查"。

## 2.1 动作类型（元级动作元组）

$$
\mathcal{A}=\{ \mathrm{fillhole},\ \mathrm{patch},\ \mathrm{adddecl},\ \mathrm{effect} \}

$$

每个动作带一个 **Lean 项** $\tau$（或效应签名 $\sigma$）作为其"类型";
形式化（syntax 级）：

$$a\in\mathcal{A} \iff \exists \text{ term }\tau: \mathrm{typecheck}(\tau \mid s)= \mathrm{accept}$$

## 2.2 合法性谓词与零非法率（定理 2.1, part.3 形式化）

定义：

$$\mathrm{legal}(a,s) := \mathbb{1}\{\mathrm{typecheck}_{\mathrm{Lean}}(\tau_a\mid s)=\mathrm{accept}\}$$

**定理（Zero-Illegality）**：若 $\pi_\theta$ 仅对 $\mathcal{A}$（合法集）进行采样，且 $\mathrm{typecheck}$ 为 Lean 的判定决策程序，
则

$$\mathbb{P}_{a\sim\pi_\theta(s)}[\mathrm{legal}(a,s)] = 1$$

**证明（sketch）**：动作由类型化构造器生成（$\mathrm{fillhole}$ 要求 $\tau:h$ 自底向上检查），
任何不通过检查的元组被拒绝（$\mathrm{go back}$ 到搜索）；因此生成分布 support 包含于合法集。

**语义推论**：自由文本代理的 $\mathrm{illegal}$ 概率 = $\mathrm{Pr}[\mathrm{typecheck}(a)=\mathrm{reject}]>0$（模型代码不保证）；
而 V2 的 $\mathrm{illegal} := 0$ 处处成立——**这是训练崩溃的无障碍保证：每一时刻的搜索树都是合法树**。

## 2.3 目标谓词的泛化（V2 真正"换档"之处）

V1：$\mathrm{Goal} :=$ "$\Gamma \vdash Q$"（证明一个命题）。
V2：$\mathrm{MetaGoal} :=$ "$\mathrm{codeTerm}_{\mathrm{type}}:\mathrm{OutputType}$"（构造一个满足类型 $\mathrm{OutputType}$ 的元级项）。

$$\mathrm{MetaGoal}\ \supseteq\ \mathrm{Goal}$$

（证明本身是 $\mathrm{OutputType}:=\mathrm{Proof}$ 的特例）。

**类型即谓词**：$\mathrm{legal}$ 与 $\mathrm{solved}$ 的判定都是**类型检查**——因此 V2 的 MCTS 的目标函数
（G 的定义域）与 V1 完全同构，只是 $\mathrm{Goal}$ 的对象更大（$\mathrm{LeanTerm}$ 全域）。

## 2.4 动作–观测同像性（元级）

- 动作 = 合成 $\mathrm{LeanTerm}$；
- 观测 = typecheck 反馈 / kernel 判定 / 检索与实验综述——均以 Lean 表示；
- 因此 MCTS 的**状态去重键**（`Tactic/State.lean stateKey`）直接复用（pp 字符串全文）——V2 的搜索
  数据结构即 V1 数据结构的**泛化实例**。

## 2.5 实现的三个层级

| 层级 | 对象 | 例子 | 动作 |
|---|---|---|---|
| L0 | 证明 | $\Gamma\vdash Q$ | $\mathcal{A}_{\mathrm{V1}}$ |
| L1 | 元证明（编写引理/证明框架） | $\mathrm{adddecl}(\mathrm{lemma})$ | $\mathcal{A}_{\mathrm{V2}}\setminus\{\mathrm{effect}\}$ |
| L2 | 元元（harness/课程） | 生成教师问题、课程算子 | $\mathcal{A}_{\mathrm{V2}}\cup\{\mathrm{meta-courses}\}$——**仅离线 harness 使用，禁止 agent 触达**（$\mathcal{I}_{\mathrm{sep}}$） |
