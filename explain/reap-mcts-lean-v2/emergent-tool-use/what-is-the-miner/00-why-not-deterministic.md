# 00. 为什么"挖掘器"不应该是固定算法

## 0.1 形式问题

规律提取 = 在描述复杂度空间中找**极小模型**（奥卡姆归纳）：

$$
\mathcal{C}(O) := \arg\min_{u:\ u\ \mathrm{models}\ O}\ \mathrm{K}(u),\qquad \mathrm{K}:\text{Kolmogorov 复杂度}
$$

## 0.2 定理与推论

**定理（K 不可实现）**．$\mathrm{K}$ 不可计算 ⇒ 不存在总计算算法求解 $\mathcal{C}(O)$。

**推论（固定算法族不完备）**．对任意固定决定族 $\mathscr{A}$（如有限差/递推/插值——即现有 $F_k^{{\det}}$），
存在结构 $u^\ast$ 与观测家族 $O$，使 $u^\ast\models O$、$\mathrm{K}(u^\ast)$ 任意小，但 $u^\ast\notin\mathscr{A}$。
（合理推论：模式发现的完整光谱 = 描述长度空间的搜索 ⇒ 属于**可训练归纳系统**，而非某确定程序。）

## 0.3 可训练挖掘器（MineGen_ψ）

定义生成器 $M_\psi:\mathcal{O}\to\Delta(\mathrm{Patterns})$。训练目标（双轨）：

$$
\mathcal{L}_{\mathrm{mine}}(\psi) :=
-\mathbb{E}_{(O,c^{\mathrm{ok}})\sim\mathcal{D}_{\mathrm{verified}}}\big[\log M_\psi(c^{\mathrm{ok}}\,\vert\,O)\big]
+\ \mathbb{E}\Big[\nabla_\psi \log M_\psi(c\,\vert\,O)\cdot \mathrm{kl}(c)\Big]
$$

- $\mathcal{D}_{\mathrm{verified}}$：塔（kernel 验证）正例 + $\mathrm{Refute}$ 桶（负例）；
- $\mathrm{kl}(c)$：门控奖励 $\mathbb{1}\{\mathrm{gate}(c)=\mathrm{ok}\}$。

**Claim（可学性）**．若候选空间在 $\mathcal{F}_k$ 上的参数化结构统计可学习，则存在 $\psi^\ast$
使 $\mathbb{P}[\mathrm{gate}(M_{\psi^\ast}(O))=\mathrm{ok}]\ge\delta>0$——收益来自"集中到可证类"的先验，
非免费午餐：$\mathcal{F}^c$ 上仍降级为 OpenConjecture 输出。

## 0.4 学习-奖励分离定理（防奖励黑客）

**定理**．设 $\mathrm{gate}$ 与 $M_\psi$ 分离，奖励仅在 $\mathrm{gate}(c)=\mathrm{ok}$ 时取 1：

$$\mathbb{P}_\psi[\mathrm{gate}(c)=\mathrm{ok}\ \wedge\ \mathrm{fake}(c)] = 0\qquad (\mathrm{fake}:=\text{语法自举伪规律})$$

因为 $\mathrm{gate}=\text{kernel 裁决}$ 不可欺骗。**推论**：学习自由度只存在于"候选生成"；
判定层（gate/Refute/F_k 判定）永远确定性——这正是 $\mathcal{I}_{\mathrm{sep}}$ 在挖掘层的显现。

## 0.5 红线（挖掘器训练约束）

1. 监督标签只来自塔与反例桶（禁止"生成器自标"——自指切断）；
2. $\mathcal{F}^c$ 输出（OpenConjectures+score）**不进梯度流**；
3. 元学习（ψ 从自身成功序列再更新）仅允许外部训练管线推进（禁自动循环）。
