# 5分钟 SPX Gamma 多空分级评级引擎实施计划 (Implementation Plan)

## 1. 需求与背景分析
当前 5 分钟周期的 SPX Gamma 信号为三元粗粒度状态（`Bullish`、`Bearish`、`Neutral`）。在实际微观订单流与期权推进中，即使同样处于看多或看空顺势推进区间，不同市场背景下的信号置信度与动能强度存在显著层次差异。
为了对顺势推进信号进行客观精细化分层，将单边信号升级为四级评级体系：
- **多头分级**：`Bullish_L0`、`Bullish_L1`、`Bullish_L2`、`Bullish_L3`；
- **空头分级**（方向相反严格对称）：`Bearish_L0`、`Bearish_L1`、`Bearish_L2`、`Bearish_L3`；
- **中性状态**：保持现有的六大细分子类型（`Neutral:Exhaustion-Top/Bottom`、`Neutral:Compression-Top/Bottom`、`Neutral:Conflicted`、`Neutral:Balanced`）。

## 2. 核心设计与量化评级规则

### 2.1 基础判定 (Level 0 Baseline)
- `Bullish_L0`：满足现有的第三层决策树绿柱支配推进规则（纯净度 PASS、Gamma 优势 >= 2.0x、现价未撞入 8 点天花板禁区、顺势推进 Cushion 充盈达标、Pos 处于安全区）；
- `Bearish_L0`：满足现有的第三层决策树红柱支配推进规则（严格反向对称）。

### 2.2 三大加分项 (Bonus Factors, 各占 1 分)
1. **多空主力集群 Gamma 规模比率 >= 3.0**：
   - 多头：`imbalance_score >= 3.0`（Call 集群 Gamma 是 Put 集群绝对值的 3 倍及以上）；
   - 空头：`bear_ratio >= 3.0`（Put 集群 Gamma 绝对值是 Call 集群的 3 倍及以上，即 `imbalance_score <= 0.333`）。
2. **开盘黄金布局时段 (06:30 - 08:30 PT)**：
   - 目标时间戳（美西时间）处于 `06:30:00 <= target_time <= 08:30:00`，为机构资金建仓与趋势爆发主浪期。
3. **主力集群 Gamma 趋势整体上 Trend Up (持续扩张净注入)**：
   - 提取开盘 06:30 以来至当前时刻的全部集群演化节点（`history_nodes`）；
   - 多头考察 Call 集群规模，空头考察 Put 集群规模绝对值；
   - 量化要求：样本节点数 >= 2，最新值高于起点（`curr > first`），线性拟合斜率 `slope > 0`，最新值处于序列高位（`curr >= 0.85 * max`），且具备显著扩张增幅（绝对增量 >= 1.0B 或相对增幅 >= 15%）。

### 2.3 分级映射与判定矩阵
- 满足 0 项加分：`Bullish_L0` / `Bearish_L0`（基准）
- 满足 1 项加分：`Bullish_L1` / `Bearish_L1`（强化）
- 满足 2 项加分：`Bullish_L2` / `Bearish_L2`（高确信）
- 满足 3 项加分：`Bullish_L3` / `Bearish_L3`（极强力主升/主跌浪）

## 3. 架构落地与改动范围
1. **算法与核心引擎**：
   - 在 `PyTools/quantdata/trend_regime.py` 中新增 `evaluate_cluster_gamma_trend_up(history_nodes, side='bull')`；
   - 在 `PyTools/quantdata/spx_gamma_analyst.py` 中重构第三层决策树 Direction、risk_advice、direction_cn_map 与 verdict 判词。
2. **后端与前端协同**：
   - 在 `bbt_data_web/data_app/bbt_signals.py` 中升级方向查询过滤，支持前缀匹配与各分级精确查询；
   - 在 `bbt_data_web/static/js/bbt_signals.js` 中新增分级徽章渲染；
   - 在 `bbt_data_web/templates/bbt_signals.html` 中丰富方向下拉选项。
3. **约束遵循**：
   - 绝不触发任何历史数据回填。
