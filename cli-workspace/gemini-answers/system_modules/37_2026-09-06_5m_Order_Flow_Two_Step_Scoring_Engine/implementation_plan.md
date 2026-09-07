# 5分钟周期 Order Flow 规则化信号系统深度重构实施计划

## 一、背景与现存问题深度剖析 (Problem Analysis)

### 1. 历史数据实测统计与畸形分布
通过对数据库 `order_flow_signals` 表的历史数据实测统计（以 2026-09-03 与 2026-09-04 为例）：
- **2026-09-03 全天 79 组 5m 信号**：`Bullish` 占 45.6%，`Bearish` 占 51.9%，**`Neutral`（中性）仅有 1 次 (1.3%)**；
- **2026-09-04 全天 78 组 5m 信号**：`Bullish` 占 39.7%，`Bearish` 占 57.7%，**`Neutral` 同样仅有 1 次 (1.3%)**。

系统在 **98.7%** 的时间里都在不停地报“看多”或“看空”。稍有一点反弹就报多，稍有一点回调就翻空，中性信号几近消亡。

### 2. 核心代码病灶：粗糙的“动量滞后跟随”
在 `order_flow_sentinel.py` 第 566-591 行中，原系统设置了极低的兜底逻辑：
```python
is_bull_trend = (net_delta_30m > 0 and price_change_30m >= 0)
# 兜底 else:
if net_delta_30m > 500 or price_change_30m >= 2.0:
    rule_dir = "Bullish"
```
**严重弊端**：
- **流动性陷阱**：在上涨行情的末端，散户追高市价买单涌入导致 Delta 持续为正，但机构主力正在高位出货（即“有毒集会” Poisoned Rally）。此时系统由于仅看 `net_delta_30m > 0`，依然在行情的绝对最高点持续给出 `Bullish`。
- **期权卖方致命风险**：若期权卖方自动引擎在接近顶部时收到 `Bullish` 信号而开仓卖出 Bull Put Spread，一旦行情冲顶回落，直接被套在天花板。

---

## 二、规则手册第一部分 (Order Flow Rules) 的评估与继承

经过对系统规则手册 [gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html) 第一部分的逐行审计，系统将全面继承并提炼已有的优秀微观规则，同时坚决纠正旧规则中的硬伤：

### 1. 深度继承与融合的五大经典规则
1. **DOM 盘口买卖比率极速大翻转 (The Book Flip at Key Levels，手册第 175-182 行)**：
   - 监控 600 个 500ms 步长内近端买卖比率 `Book_Ratio`。前半段压制 `early_ratio < 0.85`，后半段翻盘 `late_ratio > 1.40` 且处于低位 `Pos <= 40%`，确认买方夺得盘口主导权；
   - **吸纳**：直接作为 **底部被动吸收反转 (Setup 1A)** 的核心确认判据。
2. **DPER 价格推进效率与极值区被动吸筹 (Zone DPER & Absorption，手册第 25-41 行 & 65-73 行)**：
   - `DPER = 价格变动 / (净Delta / 1000)`。底部 25% 极值区承受大额抛盘，但 `bottom_zone_dper > -1.5`（每打压 1000 手跌幅不足 1.5 点），确认被动筑底；
   - **吸纳**：作为 **Setup 1 量价背离与被动吸收** 的量化判定内核。
3. **梯级冰山单密集吸收 (Tiered Iceberg Burst，手册第 191-194 行)**：
   - `Tier 1 极致死守`（单根 Bar 内 Delta 冲击超 1000 手但价格移动 <= 1.0 点，发生 1 次即可高置信度确认）与 `Tier 2 主流波段`；
   - **吸纳**：作为 **加分项 7（DOM 盘口被动冰山护盘/压盘）** 的核心打分源。
4. **2小时机构大单净流安全网与衰减加权评分 (手册第 139-158 行)**：
   - 过去 2 小时机构大单（>= 100 手）累计净量 `>= +3000` 屏蔽做空，`<= -3000` 屏蔽做多；得分超 1500 确认主力吸筹/分发；
   - **吸纳**：作为 **加分项 8（2小时机构大单净流）** 及反向信号刚性安全网。
5. **虚假撤单诱多/诱空陷阱过滤 (Spoofing Trap Filter，手册第 199-206 行)**：
   - 买方撤单占比 >= 70% 且比值超 2:1 判定为假托单诱多，卖方反之；
   - **吸纳**：作为新系统 **第一步（基本规则方向判定）的刚性一票否决项 (Hard Veto)**。

### 2. 扬弃与修正的两大旧规则硬伤
1. **废除 `Delta%Vol <= 1.5%` 判定多头（手册第 117-123 行）**：
   - 强趋势大牛市中 `Delta%Vol` 全天维持在 `+3% ~ +6%`，旧规则会将真正的趋势日顺势回踩起飞点误杀；在新系统中全面废除，顺大势而为。
2. **修正条件 D“过去 30 分钟涨 >= 15 点且净 Delta > 0 判定多头”（手册第 134-137 行）**：
   - 涨了 15 点往往已处于日内 85%~100% 极高位，无脑报多必然诱导追天花板；新系统必须严格前置 **`price_position_pct <= 65%` 的反追高过滤器**，高位必须转入 `Neutral:High-Boundary` 防守。

---

## 三、核心技术方案：两步判定法与 1 ~ 10 强度打分体系

```
                       [5分钟 Order Flow 规则研判引擎]
                                      │
           ┌──────────────────────────┴──────────────────────────┐
           ▼                                                     ▼
   【第一步：基本规则方向判定】                                 【未跨越门槛 / 处于禁区】
           │                                                     │
 ┌─────────┴─────────┐                                           ▼
 ▼                   ▼                                      输出: Direction = Neutral
判定为: 看多 (Bullish) 判定为: 看空 (Bearish)                       强度值 = 0 (常态中性防守)
 │                   │
 └─────────┬─────────┘
           │
           ▼
   【第二步：底层数据强度打分】
   • 基准起跑分: 符合基本规则即得 1 分
   • 9 大客观底层数据加分项层层累加 (+1 ~ +9)
           │
           ▼
 输出: 方向 (Bullish/Bearish) + 强度值 (1 ~ 10 分)
```

### 第一步：基本规则方向准入判定 (Direction Qualifying Rules)

必须首先通过严格的结构准入与反追单过滤器，任何 5 分钟节点默认状态均为 `Neutral`：

#### 🟢 判定为看多 (Direction = Bullish，强度起跑分 = 1)
必须满足以下三大高确信结构之一，且未触发高位追多与虚假撤单拦截：
1. **结构 A (大级别底部被动吸收反转 Setup 1A)**：
   - 现价处于日内低位区（`price_position_pct <= 35.0%`，或下探测试 Smashelito S1/S2、QuantPivot L1/L2）；
   - 出现大额负 Delta 价格跌不动的底背离（`last_15m_delta <= -2000` 且跌幅 <= 2.0 点 / `DPER > -1.5`），或 DOM 检出 `dom_bull_book_flip`，或 DOM 买方冰山护盘，或机构低位吸筹；
2. **结构 B (趋势日 10m 双柱回踩重燃 Setup 2A)**：
   - SPY 全局统一趋势日引擎确认多头（`is_bullish_trend_day == True`）；
   - **反追高刚性约束**：现价处于健康回调区间（`price_position_pct <= 65.0%`，实盘验证 09-03 紫圈回踩处于 33%~47%，完全放行；**绝对禁止在 >= 75% 顶部报顺势多头**）；
   - 均线承接：价格回踩测试 15m EMA 13/21 支撑带企稳（`[EMA13-2.5, EMA21+2.0]`）；
   - **10分钟双柱复合微观确认**：近 10m 复合净买盘 `last_10m_delta >= +600`，且最新 5m 主动买盘放量确认（`Delta >= +300`）；
3. **结构 C (30m 价值区蓄势突破点火 Setup 3A)**：
   - 经历至少 30 分钟密集筹码盘整，处于突破启动初中期（`price_position_pct 45%~65%`）；
   - 近 30m 净 Delta 大额放量突破（`net_delta_30m >= +5000`），最新 10m 双柱持续加速（`last_10m_delta >= +1200`），且 DOM 出现 Ask 档位真空推力。

#### 🔴 判定为看空 (Direction = Bearish，强度起跑分 = 1，严格对称)
必须满足以下三大高确信结构之一，且未触发低位杀跌与虚假撤单拦截：
1. **结构 A (大级别顶部被动派发反转 Setup 1B)**：
   - 现价处于日内高位区（`price_position_pct >= 65.0%`，或上冲测试 Smashelito R1/R2、QuantPivot H1/H2）；
   - 散户买单激增价格推不动的顶背离（`last_15m_delta >= +2000` 且涨幅 <= 2.0 点 / `DPER < 1.5`），或 DOM 检出 `dom_bear_book_flip`，或 DOM 卖方冰山压制，或机构高位出货；
2. **结构 B (趋势日 10m 双柱回抽再跌 Setup 2B)**：
   - SPY 趋势日引擎确认空头（`is_bearish_trend_day == True`）；
   - **反杀跌刚性约束**：现价处于健康回抽区间（`price_position_pct >= 35.0%`，**绝对禁止在 <= 25% 地板报顺势空头**）；
   - 均线承压：价格回抽测试 15m EMA 13/21 阻力带受阻（`[EMA21-2.0, EMA13+2.5]`）；
   - **10分钟双柱复合微观确认**：近 10m 复合净卖盘 `last_10m_delta <= -600`，且最新 5m 主动卖盘放量打压（`Delta <= -300`）；
3. **结构 C (30m 价值区破位下杀点火 Setup 3B)**：
   - 经历至少 30 分钟盘整，处于破位下杀初中期（`price_position_pct 35%~55%`）；
   - 近 30m 净 Delta 大额下杀（`net_delta_30m <= -5000`），最新 10m 双柱持续砸盘（`last_10m_delta <= -1200`），且 DOM 出现 Bid 档位支撑塌陷真空。

#### ⚪ 判定为中性 (Direction = Neutral，强度值 = 0)
凡不满足上述看多或看空基本规则（如处于无序中枢、买卖胶着，或处于高位 `Pos >= 75%` 禁追多、低位 `Pos <= 25%` 禁杀跌禁区），直接输出 `Direction = Neutral`，**强度值 = 0**。

---

### 第二步：底层数据强度打分 (Strength Scoring 1 ~ 10 分)

一旦第一步判定为看多或看空：
- **基准起步分**：符合基本规则即赋予 **初始强度值 = 1**；
- **9 大底层客观数据加分项（每满足 1 项 +1 分，最高累计至 10 分满分）**：

| 加分项 | 底层数据维度 | 规则手册渊源对应 | 多头加分判据 (Bullish +1) | 空头加分判据 (Bearish +1) |
| :---: | :--- | :--- | :--- | :--- |
| **加分 1** | **30m 持续大单边推进** | 手册条件 C | `net_delta_30m >= +3000` | `net_delta_30m <= -3000` |
| **加分 2** | **30m 极强单边爆发推力** | 手册条件 C 强化 | `net_delta_30m >= +5000` | `net_delta_30m <= -5000` |
| **加分 3** | **最新 10m 双柱持续强动能** | 手册 10m 复合微观 | `last_10m_delta >= +800` (两根 5m 持续放量) | `last_10m_delta <= -800` (两根 5m 持续砸盘) |
| **加分 4** | **最新 5m 单柱脉冲放量** | 手册条件 A 微观 | 最新 5m Delta `> +500` | 最新 5m Delta `< -500` |
| **加分 5** | **DOM 深度加权显著失衡** | 手册 DOM 500ms 加权 | `weighted_imbalance >= +20%` 且 `imb_momentum > 0` | `weighted_imbalance <= -20%` 且 `imb_momentum < 0` |
| **加分 6** | **DOM 阻力档位真空推力** | 手册流动性真空 | Ask 档位真空持续 `vacuum_ask_sec >= 20秒` | Bid 档位真空持续 `vacuum_bid_sec >= 20秒` |
| **加分 7** | **DOM 盘口被动冰山大单** | 手册 Tiered Iceberg | 检出被动冰山护盘 (`iceberg_bull >= 1` 或 Tier 1 死守) | 检出被动冰山压盘 (`iceberg_bear >= 1` 或 Tier 1 死守) |
| **加分 8** | **2小时机构大单净流确认** | 手册方案一/三大单网 | `big_trade_net_2h >= +1500` 或 `inst_bull_accumulation` | `big_trade_net_2h <= -1500` 或 `inst_bear_distribution` |
| **加分 9** | **趋势日均线带大势共振** | 手册趋势日防护罩 | SPY 趋势日引擎确认多头，且价格稳立 15m 均线带顺势侧 | SPY 趋势日引擎确认空头，且价格受压于 15m 均线带逆势侧 |

#### 强度分级与交易映射：
- **强度 1**：仅满足基本规则，无额外加分项（常规基准顺势试盘）；
- **强度 2 ~ 4**：满足 1 ~ 3 项加分（标准顺势推进）；
- **强度 5 ~ 7**：满足 4 ~ 6 项加分（高确信强动能顺势波段，期权卖方高胜率开仓区）；
- **强度 8 ~ 10**：满足 7 ~ 9 项加分（顶格机构级共振大爆发，主升/主跌浪极限确信）。

---

## 四、输出结果规范与全系统集成

### 1. 数据库存储规范 (`order_flow_signals` 表)
- `direction`: 格式定义为 `Bullish_S7:Bullish` 或 `Bearish_S8:Bearish`（中性为 `Neutral:High-Boundary` 等），完全与 SPX Gamma 的 `Bullish_L2:Bullish` 规范保持一致；
- `signal_strength`: 强度 8~10 ➔ `High`；5~7 ➔ `Medium`；1~4 ➔ `Low`；0 ➔ `Neutral`；
- `quantitative_metrics`: 存储详细的打分明细 JSON：
  `{"direction": "Bullish", "strength_score": 7, "base_rule": "Trend-Pullback", "bonus_items": ["30m_delta_3000", "10m_delta_800", "dom_imbalance", "dom_vacuum", "big_trade_net", "trend_day_ema"]}`；
- `verdict`: 生成高度可读的专业定性报告，例如：
  *“看多 (多头主控) - 5分钟规则自动化研判：方向=Bullish，强度值=7/10。触发基准：[趋势日10m双柱回踩重燃]，满足加分项：30m单边推进(+3200), 10m双柱强动能(+950), DOM失衡(+24%), 真空推力(28s), 趋势日共振, 冰山护盘。”*

### 2. 期权卖方开仓引擎 (`option_seller_engine.py`) 维度 1 映射
在期权卖方四维微观共振中，维度 1（满分 40 分）直接根据 Order Flow 强度值（1~10）进行线性/阶梯映射：
- `强度 10`: **40 分 (顶格满分)**
- `强度 9`:  **37 分**
- `强度 8`:  **34 分**
- `强度 7`:  **31 分**
- `强度 6`:  **28 分**
- `强度 5`:  **25 分**
- `强度 4`:  **22 分**
- `强度 3`:  **20 分 (常规顺势门槛)**
- `强度 1~2`: **15 分**
- `中性 (强度 0)`: **0 分**（不贡献分数，由其他三大维度自由合成，无单项硬拦截）。

### 3. 前端图表呈现 (`bbt_signals.js`)
- 强度 8~10：呈现大号带金色边框的深绿/深红标记；
- 强度 5~7：呈现鲜亮翡翠绿/鲜红；
- 强度 1~4：呈现标准绿色/浅红；
- 强度 0 (Neutral)：呈现柔和灰色小点。盘面主次极度清晰，彻底消除满屏假信号！

---

## 五、拟修改的文件清单与分步实施流程

### 实施分步流程：

#### 【步骤 1：系统规则手册第一部分独立备份】
- 将 [gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html)（及对应 `.md`）中的「第一部分：Order Flow 订单流分析规则 (Order Flow Analysis Rules)」全部内容单独提取并保存为新备份文件：
  * [NEW] `system_modules/backup_order_flow_rules_legacy_2026-09-06.md`
  * [NEW] `system_modules/backup_order_flow_rules_legacy_2026-09-06.html` (采用清新浅色主题 Light Theme)
- 确保旧版规则的所有定义完整持久化归档。

#### 【步骤 2：核心订单流算法代码重构】
- [MODIFY] `PyTools/order_flow_analysis/order_flow_rules_optimizer.py`：
  * 实现 Setup 1 (反转)、Setup 2 (趋势日10m双柱回踩)、Setup 3 (30m突破点火) 的三大结构准入逻辑；
  * 实现 9 大底层客观数据加分项量化判定函数；
  * 输出多空方向 `direction`（`Bullish`, `Bearish`, `Neutral`）及强度值 `strength_score`（1~10，中性为0）。
- [MODIFY] `PyTools/order_flow_analysis/order_flow_sentinel.py`：
  * 彻底废除第 566-591 行的粗糙动量跟随与 Low/Medium 兜底链条；
  * 接入两步判定法与 1~10 强度打分，落库 `direction` 复合代号（如 `Bullish_S7:Bullish`）与强度；
  * 丰富 `verdict` 文本，详细记录触发基准及满足的具体加分项。

#### 【步骤 3：期权卖方开仓引擎与前端联动适配】
- [MODIFY] `PyTools/option_seller/option_seller_engine.py`：
  * 维度 1（满分 40分）按强度值（1~10）无缝映射（S10=40分，S9=37分...中性=0分）。
- [MODIFY] `bbt_data_web/data_app/bbt_signals.py`：
  * 在 `/data/order_flow_signals` 与 `/data/order_flow_chart_data` 接口中输出 `strength_score`。
- [MODIFY] `bbt_data_web/static/js/bbt_signals.js`：
  * 适配前端图表与数据表格对 `Bullish_S1~S10`、`Bearish_S1~S10` 的精细化渲染及 Tooltip 徽章。

#### 【步骤 4：系统规则手册第一部分全面重写】
- [MODIFY] [gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md) 与 [gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html)：
  * 根据新的「两步判定法」和「1~10 强度打分体系」，**彻底重新编写「第一部分：Order Flow 订单流分析规则 (Order Flow Analysis Rules)」**；
  * 严格维护浅色主题（Light Theme），公式纯文本书写（严禁 LaTeX），更新目录索引（TOC）。
- [MODIFY] `system_modules/bbt_trading_modules.html`：
  * 登记本次模块 36（5分钟 Order Flow 结构化状态机与 1-10 强度评分体系）归档更新。

---

## 六、验证与测试计划

1. **自动化单点测试脚本**：
   - 选取 2026-09-03 与 2026-09-04 的典型时点（早盘 07:45 回踩、08:05 冲顶、09:30 高位震荡、10:45 探底等）运行单点检测，验证：
     * 冲顶时是否稳稳输出 `Neutral:High-Boundary (强度 0)`；
     * 回踩均线带时是否精准输出 `Bullish (强度 6~8)`。
2. **多空全天分布健康度测试**：
   - 验证中性信号占比是否恢复至健康的 **60%~75%** 之间。
3. **（重要约束）数据回填策略**：
   - 在用户明确指示前，**绝对不自动执行历史数据全量重跑回填**。
