# 03. 塔上升（Tower）与验证门

> 对应 7-reap-v1-v2 §3 第四组件；"验证入库 ⇔ 语言塔上升"的可执行定义。

## 3.1 库与塔的形式化

$$L_0 := \emptyset, \qquad L_{t+1} := \begin{cases} L_t \cup \{t\} & \mathrm{gate}(t)=\mathrm{ok} \\ L_t & \mathrm{gate}(t)=\mathrm{reject}\end{cases}$$

其中 $\mathrm{gate}(t) \equiv \mathrm{checkProof}_{\mathrm{Lean}}(t)= \mathrm{ok}$（**kernel 级验证，非文本级**）。

定义 **抽象深度**：

$$\delta(t,L) := \#\{d\in L : d\ \text{出现在 }\mathrm{proof}(t)\}$$

**命题（Tower=Growth）**。若 $t_{k}\in L$（此前被验证入库），则对于后续以 $t_k$ 为引理的证明 $\hat t$，
$\delta(\hat t, L) \ge \delta(t_k,L)+1$（严格递增）；于是"语言塔"的高度

$$\tau_g := \max_{t\in L_g}\delta(t, L_g)$$

是单调不减序列——与 8-v2 §3 指标 C（技能涌现度量）同形。

## 3.2 难度–驱动的课程（教师经 V2 动作生成）

设教师（teacher，V1 的 11/12 架构）输出候选集合 $M_{g}$：

$$\mathcal{M}_{g+1} := \left\{v : \mathrm{Diff}_g(v)\in[0.5,0.9] \ \wedge\ \mathrm{Sim}(v, p_\ast)\ge .7\right\}$$

其中 $\mathrm{Diff}_g(v)=1-\mathrm{solve@}B_{\mathrm{low}}(\pi_g,v)$，$\mathrm{Sim}$ 为 AST 子串相似度。**课程**是

$$\text{"工具需求密度随 } d_g\text{ 单调上升"}\quad(\text{8-v2 §1.2})$$

的机器内实现：$\mathrm{effect}$ 被需要 ⟺ 单靠 $\pi_{\theta}$ 的
形式能力无法在 $B$ 内到达终局。

## 3.3 验证门的旁路防护（Tower 的防穿）

- **一致映射**：$\mathrm{gate}:\mathrm{Prf}\to\{0,1\}$ 是布尔函数（无随机、无状态）——两次调用结果一致；
- **不可写入**：agent 无法生成 $\mathrm{checkProof}$ 的等价物的改写（$\mathcal{I}_{\mathrm{sep}}$ 的机器边界）；
- 因此"伪造引理/软证明"的难度 = 破解 Lean kernel（看作$\mathrm{TFNP}$ 计算限，超出本 spec 范围）。

## 3.4 度量与训练接轨

- $\tau_g$（塔高）为 V2 状态特征 $s$ 的一部分（$\mathrm{enc}$ 含 $L$ 与深度统计）；
- V2 的 rollouts 中每个 $\mathrm{adddecl}$ 都会产生一条 `tower-event` 样本（与 V1 sink 兼容：
  追加 `kind == "tower"` 字段，保持 schema 向后兼容）。
