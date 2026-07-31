# Gemini Answer - whale_trade_analysis_rules_reinforcement

## Question
whale-trade-analysis 技能库法则强化：

固化 空头离场不等于多头进场法则 (Short Covering vs. Active Long Accumulation Rule)：明确 Put 归零/平仓仅代表下行推力解除（中性），无主动多头 Call/现货扫货不得盲目判定看多。
固化 近期优先/近期多空决定综合判定法则 (Near-Term Dominance Rule)：明确跨期斜向组合中，DTE <= 60 天的近期腿多空对综合判定（Final Verdict）具备最高决定权。
固化 Pivot 枢轴与超大市值 Order Flow 规模法则 (Mega-Cap Order Flow Pivot Rule)：对于 META 等万亿市值巨头，独立现货大单不足以判定全局方向，强制定性为 Neutral 筹码枢轴 (Pivot Levels)。
固化 暗池大宗交割不得做买卖判定法则 (Dark Pool Non-Directionality Rule)：暗池 SingleTickDarkTrade 的 Side 标签仅为清算对扣记账，绝对不能据此判为买入或砸盘出货，同一价格成交的天量暗池定性为 Neutral 筹码枢轴点。
明确 个股 Order Flow 意图判定引擎 与非 AUTO 期权的适用边界差异。


## Answer
# Whale Trade Analysis 技能库五大核心法则强化与边界定义报告

本文档汇总并整理了 `whale-trade-analysis` 技能库中强化的五大核心法则、技术物理机制、案例纠偏逻辑以及边界判定条件。

---

## 一、 五大核心法则定义与物理机制

### 1. 空头离场不等于多头进场法则 (Short Covering vs. Active Long Accumulation Rule)
* **物理机制**：
  - **Put 持仓归零/大幅萎缩 (Put OI Zeroing/Reduction)**：仅仅代表原有看空期权平仓离场或获利了结（Short Covering / Profit Taking），在物理上**仅代表“下行砸盘推力的解除”，绝对不能等同于“主动多头资金进场 (Active Long Buying)”**。
* **判定规则**：
  - 若次日清算数据证实大额 Put 发生了平仓归零（OI 骤降），但在期权端和现货端**没有观察到明确的主动多头 Call 建仓 (+Call OI) 或低位现货大宗吸筹 (Buy Block)**，系统**严禁**盲目将其判定为看多 (Bullish)，**必须严格判定为中性 (Neutral)**（表示空头退场，但缺乏主动上行动能）。
* **看多 (Bullish) 的唯一触发条件**：
  - 只有在 Put 平仓离场的同时，伴随着明确的**主动多头 Call 扫盘建仓 (+Call OI) 或现货大宗吸筹买单**，才能定性为看多 (Bullish)。

---

### 2. 近期优先/近期多空决定综合判定法则 (Near-Term Dominance Rule)
* **物理机制**：
  - 在分析包含跨期/斜向组合（Diagonal / Calendar Spreads，近期腿与远期腿方向相反）的期权与现货大单时，**近期（Near-Term, DTE <= 60 天）的多空方向对综合判定（Final Verdict）具备最高决定权**。
* **交易决策导向 (Rationale)**：
  - 交易员需要根据近期多空方向来决定当前的开仓/平仓与风控决策。即使远期布局看多，但若近期通过卖出 Call 封死涨幅上限、或伴随着近期卖现货/买 Put 压制，当前盘面在近期维度上即属于**看空/受限压制 (Bearish / Capped)**。
* **综合判定规范**：
  - 报告中须清晰分别标注：
    - **近期方向 (Near-Term)**: 看空 (Bearish)
    - **远期方向 (Far-Term)**: 看多 (Bullish)
    - **综合判定 (Final Verdict)**: **看空 (Bearish - 近期优先)**

---

### 3. Pivot 枢轴与超大市值 Order Flow 规模法则 (Mega-Cap Order Flow Pivot Rule)
* **物理机制**：
  - 对于 META, NVDA, AAPL, MSFT, TSLA 等万亿美元级别的超大市值个股，若出现的现货大宗大单（如 250,000 ~ 500,000 股级）**没有在 1 分钟内发现与期权大单秒级对锁**，其规模相较于万亿总市值仅为日常流动性对敲与机构盘中再平衡。
* **判定规则**：
  - **单凭此等规模的独立 Order Flow 绝对不足以判定全局趋势方向，其方向性权重必须强制归为中性 (Neutral)**！
  - 报告中须明确标注：此等大单成交价格（如 META $594.72, $593.39）构成了市场重要的**关键筹码枢轴 (Pivot Levels)**，而非方向性驱动信号。

---

### 4. 暗池大宗交割不得做买卖判定法则 (Dark Pool Non-Directionality Rule)
* **物理机制**：
  - 暗池大单 (`SingleTickDarkTrade`) 盘面上打印的 `Side` (如 Sell/Buy) 属于非公开交易所双向对扣协议的清算记账标识，**绝对不能据此认定机构是在砸盘抛售 (Sell) 还是主动买入 (Buy)**！
* **判定规则**：
  - 盘后连续在同一精准价格（如 ORCL $119.96、INTC $81.88）成交的天量暗池大单（如 536 万股 / 1442 万股），物理本质是机构间的**暗池场外交割与筹码过户 (Dark Pool Off-Exchange Block Crossing)**。
  - 此类暗池天量成交仅确立了市场极度关键的**暗池筹码枢轴点 (Dark Pool Block Pivot Level)**。其方向性权重**必须严格强制定性为中性 (Neutral)**，绝对不能死板判定为“天量出货压制”。

---

### 5. 个股 Order Flow 意图判定引擎 与非 AUTO 期权的适用边界差异

| 资产 / 交易类型 | 适用的判定法则 | 核心逻辑与边界条件 |
| --- | --- | --- |
| **个股 Order Flow (现货/暗池)** | **20日高低点区间判定引擎** | 现货为线性资产 ($Delta = +1.0$)。成交价格处于 **Top 30%** (分位数 $\ge$ 70%) 强制覆写为主动卖出/看空 (Distribution)；处于 **Bottom 30%** (分位数 $\le$ 30%) 强制覆写为主动买入/看多 (Accumulation)。 |
| **非 AUTO/AUCT 期权 (FLR/CROSS)** | **非 AUTO 执行类型 & DITM 中性对锁法则** | 属于衍生品协议对敲记账，权利金 99%+ 为纯内含价值。物理本质为场内 Delta 中性合成转换对锁 (Synthetic Reversal/Conversion)，**严禁直接套用 20日价格区间引擎，必须强制定性为 Neutral（中性）**。 |
| **次日清算 OI 数据** | **OI 清算最高表决权法则** | 若次日官方清算数据证实 OI 骤降或 100% 归零，说明为提前行权或盘中轧平，方向性动能归零，**强制判定为 Neutral（中性）**。 |

---

## 二、 实战案例纠偏与数据库更新记录

1. **TSLA 2026-07-23 ($7.86 亿美元 DITM Put 案例)**：
   - **原判定**：Bullish
   - **修正后**：**`Neutral`**
   - **依据**：次日（07-24）清算数据显示所有 DITM Put 的 OI **100% 暴跌归零 (-2,055 ~ -2,745 手)**。确证为中性清算轧差，盘面无持久买盘支撑，完美解释了 TSLA 随后持续阴跌的走势。

2. **INTC 2026-07-27 ($5.19 亿美元斜向对锁案例)**：
   - **原判定**：Bullish
   - **修正后**：**`Bearish`**
   - **依据**：依据近期优先法则，近期 (DTE 53) 卖出 97.50 Call ($65.45M) 封死涨幅，并套现 -$161.10M 现货。近期看空优先，指导交易员近期不盲目追高开多。

3. **META 2026-07-28 ($3.97 亿美元 Order Flow 案例)**：
   - **原判定**：Bullish
   - **修正后**：**`Neutral`**
   - **依据**：依据超大市值 Pivot 法则，META 1.5 万亿市值下独立的 25万~30万股大宗买卖单不足以驱动全局趋势，确立为 **$594.72 & $593.39 筹码枢轴 (Pivot Levels)**。

4. **ORCL 2026-07-28 ($7.96 亿美元案例)**：
   - **原判定**：Bearish
   - **修正后**：**`Neutral`**
   - **依据**：依据暗池交割法则，盘后 536 万股 @ $119.96 属于暗池场外交割，非砸盘出货；补全 8 笔远期 Put 组合对敲分析，确立为 **$119.96 暗池筹码枢轴**。

5. **META 2026-07-30 ($3.0055 亿美元 Options Flow 案例)**：
   - **判定**：**`Neutral`**
   - **依据**：6 笔大单全部为 `FLR` / `M2M_FLR` 场内协议对敲极深实值 DITM Put (800P/710P/1020P)，确证为中性合成转换对锁。

6. **MU 2026-07-29 ($14.567 亿美元案例)**：
   - **判定**：**`Bearish`**
   - **依据**：10:58 单笔 **-$889.10M (115.7万股 @ $768)** 现货天量抛售构建强压，现货净卖出 -$406.30M。

7. **INTC 2026-07-29 ($11.814 亿美元 Order Flow 案例)**：
   - **判定**：**`Neutral`**
   - **依据**：盘后 1442.9 万股在精准 **$81.88** 完成暗池天量过户 ($10.207 亿单笔)，确立 **$81.88 暗池筹码枢轴**。

