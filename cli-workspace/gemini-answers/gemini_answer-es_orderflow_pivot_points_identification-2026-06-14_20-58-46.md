# Gemini Answer - es_orderflow_pivot_points_identification

## Question
对于我的trading系统 下一个功能模块是 通过ES的order flow数据识别日线级别的pivot点位 
比如 Adam Set 的post说
Adam Set Signal:
2026-06-10 10:24:53 Seattle Time
... (ES: 7340 is the most important pivot point).
请推荐方案来识别这些pivot点位


## Answer
为避免 LaTeX 公式渲染导致的乱码问题，以下将所有公式和符号转换为纯文本形式，重新输出定量化分析方案：

# 订单流日线级别枢轴点 (Pivot) 定量识别方案

## 1. 枢轴点 (Pivot) 的微观结构定义
在微观订单流中，一个有效的日K级别枢轴点（如 ES 7340）通常不是单一的支撑或阻力线，而是满足以下特征的价格带：
1. **流动性交汇区**：历史大宗对锁盘口（Crossing Orders）或暗池交易最集中的成交价格。
2. **动能跃迁带**：市价扫盘单（Sweeps）在此点位发生方向性失衡与速度激增。
3. **多空筹码转换线（S/R Flip）**：前序被动冰山单被主动扫盘吞噬后，发生支撑/阻力角色互换的点位。

---

## 2. 4维定量识别模型 (Pivot Identification Model)

通过以下四个维度的订单流指标进行综合评分与物理点位定位，设候选点位为 P。

### 维度 A：大宗大单对锁密集度 (Crossing Volume Profile - CVP)
* **原理**：机构大宗交易（Block Trades）通常在特定中性价格进行对锁，该价格是多空资金共识的平衡点，也是后续突破后的枢轴线。
* **量化方法**：
  在 N 日窗口内，统计每个价格 tick 上的大宗对锁及暗池交易累计量：
  * **CVP_Volume(P)** = Sum(Volume_i) 其中 Price_i = P，且 Type_i 属于 ('SingleTickBigTrade', 'SingleTickDarkTrade')
* **枢轴筛选**：提取 CVP_Volume 局部极大值（Local Peaks）对应的价格作为候选 Pivot，记为 **P_cvp**。

### 维度 B：市价扫盘动能跃迁带 (Aggressive Sweep Jump - ASJ)
* **原理**：当价格突破 Pivot 点时，会引发止损单（Stop Orders）触发与机构追单，表现为市价扫盘单（Sweeps）的成交笔数 and 滑点在极短时间内（如 10 秒内）出现数量级跃迁。
* **量化方法**：
  对于每个突破事件，计算滑点与成交量比率（Slippage-to-Volume Ratio）：
  * **ASJ_Score(P)** = (Price_after_10s - Price_break) / Volume_active
  当价格经过 P 点时，若出现极小的 Volume 却产生极大的价格位移，说明该价格点发生了“流动性空洞”与“主动单吞噬”。
* **枢轴筛选**：ASJ_Score 发生突变信号的价格，记为 **P_asj**。

### 维度 C：被动冰山吸收拦截区 (Passive Iceberg Level - PIL)
* **原理**：枢轴点通常是前序强被动防线（被动吸收看多/看空）。当该防线在后序交易日被市价扫盘有效突破并站稳时，防线即转化为枢轴点。
* **量化方法**：
  提取前序 5-10 个交易日中，被动吸收频次最高的价格水平。
  * **PIL_Volume(P)** = 历史累计被动拦截量。
* **枢轴筛选**：选择历史 PIL_Volume 最大的 Top 3 价格，记为 **P_pil**。

### 维度 D：盘口失衡与 Delta 转换线 (Delta Flip Line - DFL)
* **原理**：CVD（累积净 Delta）在跨越该价格时发生方向性翻转，或者买卖盘口深度（Market Depth Imbalance）在该点位发生逆转。
* **量化方法**：
  监测日内交易中，CVD 从持续负值转为正值（或相反）时，所对应的价格节点。
  * **DFL_Price** = 满足 CVD = 0 且 d(CVD)/dt 达到局部的极值时的标的价格 P。

---

## 3. 双向 Pivot 判定法则与交易逻辑

枢轴点的判定必须包含双向（多头与空头）对称逻辑，以下为具体的量化交易触发规则：

### 规则 1：多头收复枢轴 (Bullish Reclaim Pivot) - 以 ES 7340 为例
* **市场背景**：前序价格在 Pivot（7340）下方运行，7340 累积了大量被动卖盘。
* **量化触发条件**：
  1. **主动收复 (Reclaim)**：价格以单 Tick > 3,000 手的主动 Buy 扫盘单突破 7340。
  2. **回踩站稳 (Stick/Support Confirm)**：价格回踩 7340 附近（如 7338.00 - 7342.00），此时大单明细中在 7340 出现 Sell 属性大单（主动空头砸盘），但价格**拒绝下跌**（V_passive_buy 增加），表明前序阻力位已成功转为被动支撑（S/R Flip）。
* **系统研判**：触发 **"Whale Rally Pending"**，转向多头主控（Bullish Dominance）。

### 规则 2：空头跌破枢轴 (Bearish Breakdown Pivot) - 对称下跌情况
* **市场背景**：前序价格在 Pivot（例如 7300）上方运行，7300 累积了大量被动买盘支撑。
* **量化触发条件**：
  1. **主动跌破 (Breakdown)**：价格以单 Tick > 3,000 手的主动 Sell 扫盘单向下跌破 7300。
  2. **反弹受阻 (Resistance Confirm)**：价格反弹测试 7300 附近（如 7298.00 - 7302.00），大单明细中在 7300 出现 Buy 属性大单（主动多头扫盘拉升），但价格**拒绝上涨**（V_passive_sell 增加），表明前序支撑位已转为被动阻力。
* **系统研判**：触发 **"Whale Dump Pending"**，转向空头主控（Bearish Dominance）。

---

## 4. 落地算法实现路线图 (Implementation Roadmap)

1. **筹码 Profile 聚类 (Clustering)**：
   对 P_cvp 与 P_pil 进行高密度聚类（Binning size = 1.0 点），将多日内重合度最高的价格带（如 7340 +- 2.0点）确立为“系统候选 Pivot 点位”。
2. **实时监测引擎 (Sentinel Engine)**：
   实时订阅盘口数据，当价格接近候选 Pivot 点（距离 <= 5 点）时，启动微观 Delta 监测：
   * 计算突破时的扫盘流速（CVD 变化率）。
   * 计算回踩时的被动吸收量。
3. **信号可视化**：
   在 Web 界面上绘制自动生成的 Pivot 枢轴线，并标注当前的突破与站稳状态。

