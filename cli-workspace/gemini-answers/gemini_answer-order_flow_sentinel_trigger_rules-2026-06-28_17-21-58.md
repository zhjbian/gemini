# Gemini Answer - order_flow_sentinel_trigger_rules

## Question
PyTools/order_flow_analysis/order_flow_sentinel.py trigger的order flow分析记录的规则是什么


## Answer
在 `PyTools/order_flow_analysis/order_flow_sentinel.py` 中，触发订单流分析并记录信号的核心判断逻辑由**基础指标评估**和**三大优化方案引擎（基于 `order_flow_rules_optimizer.py`）**共同决定。

具体规则如下：

### 1. 基础指标评估规则 (Base Heuristics)

哨兵每 5 分钟获取最近 30 分钟内（6 个 5 分钟 Bar）的 Delta 和价格变化：
- **预设条件过滤 (Pre-condition)**:
  * **多头预设 (`pre_bullish`)**: 累计 RTH Delta 占比总成交量比例 `delta_pct_vol <= 0.015`。
  * **空头预设 (`pre_bearish`)**: 累计 RTH Delta 占比总成交量比例 `delta_pct_vol >= 0.015`。
- **触发因子 (Conditions A, C, D)**:
  * **条件 A (15分钟动量)**: 最近 15 分钟 Delta `>= 8000` 或单个 5 分钟 Delta `>= 6000`（看多）；看空反之为 `<= -8000` 或 `<= -6000`。
  * **条件 C (CVD 趋势/Runup)**: 累计 Delta 较日内低谷的回升值 `delta_runup >= 10000`，或 30 分钟净 Delta `> 5000`（看多）；看空反之（`delta_drawdown >= 10000` 或 `<-5000`）。
  * **条件 D (价量收敛/共振)**: 30 分钟价格上涨 `>= 15` 点且 30 分钟净 Delta `> 0`（看多）；看空反之为价格下跌 `<= -15` 点且 30 分钟净 Delta `< 0`。

---

### 2. 三大优化逻辑规则 (Optimized Rules)

在基础指标之上，哨兵调用了优化引擎，通过以下三个方案直接干预、覆盖或阻断信号判定：

#### (1) 方案一：大单净量安全网 (Big Trade Net Filter)
统计过去 **2 小时内** 机构大单的累计净成交量（以 3000 手为强力阈值）：
- **多头防线**: 若 2 小时大单净买量 `>= 3000` 手，**无条件屏蔽 (Block) 所有看空信号**（`is_bear_high = False`）。
- **空头防线**: 若 2 小时大单净卖量 `<= -3000` 手，**无条件屏蔽 (Block) 所有看多信号**（`is_bull_high = False`）。

#### (2) 方案二：被动吸筹/分发背离规则 (Passive Absorption / Distribution)
当价格与 Delta 发生背离时（即量在暴增但价格不为所动），捕捉机构的被动吃单行为：
- **被动多头吸筹 (`passive_bull_absorption`)**: 
  * 过去 30 分钟 Delta 暴跌 `net_delta_30m < -4000`；
  * 但价格跌不动 `price_change_30m >= -5.0`；
  * 且价格处于日内相对低位 `price_position_pct <= 30.0%`。
  * **动作**: 一旦触发，**直接强制激活看多判定**（即令 `pre_bullish = True`，`cond_c_bull = True`）。
- **被动空头分发 (`passive_bear_distribution`)**:
  * 过去 30 分钟 Delta 暴涨 `net_delta_30m > 4000`；
  * 但价格涨不动 `price_change_30m <= 5.0`；
  * 且价格处于日内相对高位 `price_position_pct >= 70.0%`。
  * **动作**: 一旦触发，**直接强制激活看空判定**。

#### (3) 方案三：时间衰减加权大单评分与相对位置覆盖
基于过去大单的生成时间，采用指数衰减（近期的权重更高）计算大单情感得分：
- **多头覆盖 (Likely Bullish)**: 若大单综合流向判定为 `Bullish`，直接无视微观 delta 走势，令 `is_likely_bullish = True`。
- **低位机构吸筹强行触发 (`inst_bull_accumulation`)**:
  * 若近 2 小时大单净量 `>= 3000` 或大单情绪得分 `>= 1500`；
  * 并且价格处于偏低位置 `price_position_pct <= 45.0%`。
  * **动作**: **无条件强制触发 `is_bull_high = True`**。
- **高位机构出货强行触发 (`inst_bear_distribution`)**:
  * 若近 2 小时大单净量 `<= -3000` 或大单情绪得分 `<= -1500`；
  * 并且价格处于偏高位置 `price_position_pct >= 55.0%`。
  * **动作**: **无条件强制触发 `is_bear_high = True`**。

