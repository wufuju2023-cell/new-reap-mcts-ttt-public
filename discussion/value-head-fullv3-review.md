# 评审备忘：REAL7B full-v3 value head（F1 / H1 案例）

> 对 `reap-new-update-model`（master）`discussion/new_value_head_in7b_ex1/` 的设计/实现评审结论（2026-08-30）。
> 全文依据：`01_设计说明/`、`02_成功案例/`、`code/train_value_head.py`、`code/categorical_search_backend.py`、`code/online_ttt.py`。

## 总体判断

设计干净、AlphaProof 语义一致、证据纪律强。**可以继续**

- 冻结 7B 表征只训 934K 参数的小头：可复现、可审计、随机对照容易做——选择正确。
- `d∈[1,64]` → 搜索端 `V=-d` 只做一次接口变号：数值可解释、backup 可核对方向。
- 四层 split 隔离（sample/state/root/family）+ 分片 SHA + 恢复器 fail-closed：教科书级。

## 需要注意的点（按优先级）

### 1. 在线 target 语义：`search_visit_backup` 是“访问分布均值”而非“最短已知距离”

`online_ttt.py:_target` 取 `valueSum/numVisit`（OR 节点已访问边的均值）。初期未探测长分支会被计入均值 → target 系统性偏大；头部学到的其实是“访问分布下的期望 return”，而文档语义宣称的是“剩余步数”。

- AlphaProof 也是 visit 平均，不算错；建议：要么在文档把 `d` 定义为“期望剩余距离”，要么提供 min-over-visited-children 的 target 变体做对照。
- 收敛时均值→最优路径，动态自洽；F1 两臂 scale 差异（2.9 vs 32.2）主要由离线训练造成，方法无碍。

### 2. 特征漂移：离线头在冻结 base 特征上训练，TTT serving 是 base+LoRA

初始无漂移（`init_lora_weights=True`，B=0 等价 base），联合 TTT 实时补偿——自洽。但建议加一个**每 learn 后 hidden L2 drift 审计指标**（adapter 版本 vs value 特征均方差异），防“只更 policy 不更 head”的配置回归，并解释 v0→v2 raw-distance-mean 3.01→3.23 的移动幅度。

> 注意：早期公开快照的 `policy_server.py` 语义为 `init_lora_weights=False`（零长训）；full-v3 路线已改为 `init_lora_weights=True`（B 矩阵零初始化，初始等价 base）。口径以 full-v3 为准。

### 3. 因果证据强度：F1 是单题单 pair

- 20 题矩阵建议按对报 win/loss/revisit 差，而不是只报聚合 solve@；
- H1 的 `selection_value_refresh=false` 必须固定在报告标题行（否则会误以为 learn 后旧节点回访用了新头）。

### 4. 实现级小项

- `value()` 的 clamp `[1,64]` 与 softmax-期望解码一致，OK；建议在 `value_metadata` 记录 clamp 命中率（saturation rate），20 题结论需要它。
- `create_session` 替换 `session.value_head` 后 `load_state_dict(strict=True)` + 拷贝校验——保留。
- 复现 B 层“四组特征同 fingerprint + 四层隔离”，`assert_split_isolation` 全覆盖——保留。

### 5. 可选用法

F1 访问计数证据（`[0,7,0,1] vs [0,4,1,3]`）已证明 value 在改变选择；下一步可在 `/value` 返回里加 `selected_visits_before/after`，把 selection 差异做成每 checkpoint 的连续曲线而非单点。

## 结论边界

full-v3 是当前“最好但未必够好”的可执行候选；完整 20 题矩阵未完成前不能宣称稳定默认。失败、耗尽和未完成实验不伪装成成功案例——这一纪律在整个示例包中执行得很干净。
