# Gemini Answer - day_type_and_scoring_rules

## Question
请详细记录现在day type的判断规则和强度计算规则 用@gem-doc


## Answer
## Day Type (日终定性) 判断规则

系统在盘尾依据盘前 (PM) 和常规交易时段 (RTH) 的 Delta 累积、价格变动以及吸收信号的统计，将盘面划分为五种基调（Day Type），默认为 **Balanced（均衡震荡）**。

### 1. Passive Buying (被动买方吸收)
判定满足以下**任意一条**即可：
- `total_delta < -15,000` 且 `rth_price_change >= -5.0`
  *(全天大额净卖出，但 RTH 价格抗跌)*
- `pm_delta < -500,000` 且 `pac >= 0.9` 且 `pm_price_change > 10.0` 且 `rth_price_change >= -10.0`
  *(盘前极强的主动抛压被全部吸收且价格逆势大涨，且 RTH 时段没有出现严重回调)*
- `total_delta < 0` 且 `rth_price_change >= 20.0` 且 `bull_absorb_count > bear_absorb_count`
  *(全天净卖出，但价格大涨超过 20 点，且看多吸收信号多于看空)*
- `bottom_zone_delta < -10,000` 且 `bottom_zone_dper > -1.5`
  *(在价格全天振幅底部的 25% 区间内，遭受超过 1 万手的抛压，但其底部 DPER 大于 -1.5，即每 1000 手净卖单向下推低价格的效率不足 1.5 点，表明被冰山买单有效拦截)*

### 2. Passive Selling (被动卖方拦截)
判定满足以下**任意一条**即可：
- `total_delta > 15,000` 且 `rth_price_change <= 5.0`
- `pm_delta > 500,000` 且 `pac >= 0.9` 且 `pm_price_change < -10.0` 且 `rth_price_change <= 10.0`
- `total_delta > 0` 且 `rth_price_change <= -25.0` 且 `bear_absorb_count > bull_absorb_count`
- `top_zone_delta > 10,000` 且 `top_zone_dper < 1.5`

### 3. Active Buying (主动买方推进)
- `total_delta > 15,000` 且 `rth_price_change >= 20.0` 且 `dper >= 1.5`
  *(大额净买入，价格大幅上涨，且全天价格效率达到至少 1.5 点 / 1000手)*

### 4. Active Selling (主动卖方推进)
- `total_delta < -15,000` 且 `rth_price_change <= -20.0` 且 `dper >= 1.5` 
  *(大额净卖出，价格大幅下跌，且由于是向下推进，DPER 公式计算出的绝对效率需要大于等于 1.5)*

---

## 强度定量评分计算规则 (Scoring Breakdown)

系统基于 5 个核心维度对盘口强弱进行打分，总计 100 分。该评分用于量化当前 Day Type 趋势逻辑的可靠程度。

### 1. Zone DPER Score (40% 权重)
此项考核当前 Day Type 定性逻辑的专属关键微观区域内（如 Passive Buying 考量底部区间）的价格效率背离。
- **Passive Buying**: `min(max(-bottom_zone_dper, 0.0) / 2.0, 1.0) * 40.0`
  *(底部 DPER 越偏负代表买方拦截越强，达到 -2.0 及以下即为满分 40)*
- **Passive Selling**: `min(max(-top_zone_dper, 0.0) / 2.0, 1.0) * 40.0`
- **Active / Selling**: `min(abs(dper) / 2.0, 1.0) * 40.0`

### 2. Delta Score (20% 权重)
考核全天的净动能体量。
- **公式**: `min(abs(total_delta) / 30000.0, 1.0) * 20.0`
- *(全天绝对净 Delta 达到 30,000 手即满分)*

### 3. Volume Score (20% 权重)
考核全天的市场参与度。
- **公式**: `min(total_volume / 2000000.0, 1.0) * 20.0`
- *(全天总成交量达到 200 万手即满分)*

### 4. Divergence Score (15% 权重)
考核全天整体价格表现与动能的背离程度。
- **Passive 类**: 若 RTH 涨跌幅绝对值 `< 5.0`，则满分 15 分。否则 `max(0.0, 15.0 - abs(rth_price_change) / 2.0)`
  *(Passive 要求价格不应该出现顺势的单边大幅变动，否则背离不成立)*
- **Active 类**: `min(abs(rth_price_change) / 40.0, 1.0) * 15.0`
  *(要求有大级别的顺势价格推进，达到 40 点涨跌幅即满分)*

### 5. Squeeze Score (5% 权重)
考核尾盘时段 (12:45-13:00 PT) 是否出现机构的止损踩踏爆发（Squeeze）。
- **完全爆发**: 若 Passive Buying 且 15分钟 `delta < 0` 且 `price_change >= 15.0`（或 Passive Selling 的反向），满分 `5.0`。
- **局部发酵 (基于 CSM)**: 若出现 CSM 与 Day Type 同向的极端情况，得分 `min(abs(price_change_15m) / 25.0, 1.0) * 5.0`。
- **否则**: 0分。

### 综合等级 (Strength Grade)
- **High**: Total Score >= 75.0
- **Medium**: Total Score >= 45.0
- **Low**: Total Score < 45.0

## dper_examples

### Question
请加入对DPER的实例解释


### Answer
## DPER (Delta-Price Efficiency Ratio) 实例解析

DPER (价格效率比) 用于衡量“每一千手净 Delta 动能，能推升或打压多少点的价格”。它是判断市场中主动买卖（市价单）与被动拦截（限价冰山单）之间博弈强度的核心指标。

- **基础公式**: `DPER = Price_Change / (Delta / 1000.0)`

### 实例 1：正常的顺势推进 (Active Type)
假设在某个趋势向上的日子，RTH 时段内：
- 净 Delta = +15,000 手 (强力的市价买盘)
- 价格上涨 = +30 点
- **计算 DPER** = `30 / (15000 / 1000) = +2.0`
- **解析**: 每一千手主动净买单，成功将价格推升了 2 点。由于 DPER >= 1.5，这表明多头推进效率极高，上方没有太大的被动限价单阻力，这是典型的 **Active Buying (主动买方推进)** 场景。

### 实例 2：底部的被动吸收 (Passive Buying 的常规防守)
假设在某个下跌放量的日子，价格打到了全天振幅底部的 25% 区间，此时我们观察这个底部微观区间 (Bottom Zone)：
- 底部区间 Delta = -10,000 手 (空头在底部仍在用市价单疯狂砸盘)
- 底部区间价格变动 = -5 点 (价格仅微弱下跌)
- **计算 Bottom Zone DPER** = `-5 / (-10000 / 1000) = +0.5`
- **解析**: 正常情况下 1 万手的巨大抛压可能会让价格跌去 15-20 点，但这里只跌了 5 点。说明底部有极厚的被动多头限价单在“托底”。空头的打压效率低下（DPER 仅为正数 0.5），这是多头吸筹的初步迹象，但价格依然在跟随 Delta 顺势下跌。

### 实例 3：底部的极端背离 (Passive Buying 满分场景)
同样是在底部 25% 区间，如果抛压被完全逆转：
- 底部区间 Delta = -10,000 手 (空头同样在疯狂砸盘)
- 底部区间价格变动 = +20 点 (价格不跌反涨！)
- **计算 Bottom Zone DPER** = `+20 / (-10000 / 1000) = -2.0`
- **解析**: 此时 DPER 为负数！说明不仅空头的巨额抛压没有让价格下跌，反而被下方的多头冰山单全数吃掉，并且多头的买气直接将价格逆势推高了 20 点。
- **打分应用**: 在 Zone DPER Score 的 40分满分公式中：`min(max(-bottom_zone_dper, 0.0) / 2.0, 1.0) * 40.0`，带入 `-2.0` 后：`max(-(-2.0), 0) = 2.0`，`2.0 / 2.0 = 1.0`。最终得分 `1.0 * 40.0 = 40.0`。这代表着最完美的、具有极高反转胜率的底部被动吸筹形态，因此系统会给予 40 分满分的权重。

