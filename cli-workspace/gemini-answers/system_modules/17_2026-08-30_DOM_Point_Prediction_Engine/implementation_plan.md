# 基于深度 DOM 200 档与 Delta 效率的日内顶底预判引擎实施计划

## 概述与设计背景
通过分析专业交易员 DOM 读盘机制（YouTube: *How To Read the Depth of Market*），结合 Adam Set（@Adaamset）日内提前预判高低点与捕捉流动性陷阱（Liquidity Traps）的实战特征，我们在现有 DOM 200 档原生采集的基础上，构建**日内关键顶底预判引擎（DOM-Driven Turning Point & Range Predictor）**。

针对“5分钟内 Delta > 1000 手，价格位移条件”的核心参数设计：
* 原先激进的 `<= 1.0 点`（仅 4 个 Tick）易导致将分层摆单的真实机构吸收误判；
* 本计划采纳更加贴合微观市场结构与机构算法单分层铺设的**梯级吸收体系（<= 3.0 点为主流基准，<= 1.0 点为极致死守加权）**与**双向对称性设计**。

---

## User Review Required

> [!IMPORTANT]
> 1. **分层吸收阈值设计**：
>    * **极致冰山 (Extreme Pin / Wall)**：`Abs(Delta) > 1,000` 且 `Abs(Price_Change) <= 1.0` 点（极高置信度，单档死守）；
>    * **主流波段吸收 (Standard Churn / Absorption)**：`Abs(Delta) > 1,000` 且 `Abs(Price_Change) <= 3.0` 点（主力基准，兼顾微观波段震荡洗盘）；
>    * **广义拦截 (Broad Absorption)**：`Abs(Delta) > 1,500` 且 `Abs(Price_Change) <= 5.0` 点（动能被消耗大半，进入反转准备区）。
> 2. **多空双向通用对称性 (Rule 6 约束)**：
>    * 看跌顶部吸收（Bearish Absorption at Highs）：`Delta >= +1,000` 手，价格冲高受阻回落且位移 `<= 3.0 点`，锁定机构被动限价派发；
>    * 看涨底部吸收（Bullish Absorption at Lows）：`Delta <= -1,000` 手，价格下砸衰竭且位移 `<= 3.0 点`，锁定机构被动限价吸筹。
> 3. **挂单持久度 (Wall Persistence)**：
>    * 50 点静态大挂单（超过平均 3 倍以上）若在价格逼近时撤单率 < 15% 确认为真实磁铁阻力/支撑，若撤单率 > 50% 标记为假挂单（Spoofing Trap）。

---

## 实施范围与文件变更

### 1. Python 特征工程层 (`BBTrading`)

#### [MODIFY] [order_flow_feature_generator.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_feature_generator.py)
* **新增 DPER (Delta-Price Efficiency Ratio) 计算**：
  * `dper = price_change / delta_vol`，并标记 DPER 归零的极度吸收区间；
* **新增 5 分钟梯级冰山吸收识别**：
  * `absorption_extreme`: `abs(delta_vol) > 1000 & abs(price_change) <= 1.0`
  * `absorption_standard`: `abs(delta_vol) > 1000 & abs(price_change) <= 3.0`
  * `absorption_broad`: `abs(delta_vol) > 1500 & abs(price_change) <= 5.0`
* **新增 50 点深层静态大挂单壁垒定位 (Liquidity Walls Detector)**：
  * 在当前 200 档内扫描挂单量大于均值 3 倍的价格，记录为潜在磁吸与防守点位。

### 2. Python 决策与哨兵层 (`BBTrading`)

#### [MODIFY] [dom_sentinel_evaluator.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/dom_sentinel_evaluator.py)
* 在 5 分钟网格判定中引入梯级吸收判定与 DPER 衰竭校验；
* 整合买卖盘深度比率翻转（The Book Flip Rate: `Bid_Depth_Near / Ask_Depth_Near` 骤变）作为顶底反转的确认信号。

#### [MODIFY] [ai_tape_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/ai_tape_analyst.py)
* 在系统 Prompt 与摘要中新增 **`[DOM 预判日内支撑与阻力位 (Predicted S/R via DOM)]`**：
  * 阻力位（Target High）：综合上行真实大挂单壁垒 + 高位看跌冰山吸收点；
  * 支撑位（Target Low）：综合下行真实大挂单壁垒 + 低位看涨冰山吸收点；
  * 第一止盈目标：根据被动打穿留下的单边流动性真空带（Vacuum Pockets / Zero Prints）给出反手回补价格。

### 3. 系统模块归档与规则手册同步 (System Modules & Rules Manual)

#### [NEW] [implementation_plan.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/17_2026-08-30_DOM_Point_Prediction_Engine/implementation_plan.md)
* 建立 Module 17 目录并归档实施计划；

#### [MODIFY] [bbt_trading_modules.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/bbt_trading_modules.html)
* 新增 Module 17 条目；

#### [MODIFY] [gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html)
* 在 Order Flow 板块下增加 **【DOM 梯级冰山吸收与点位预判决策法则】**。

---

## 验证计划

### 1. 特征与指标自动化测试
* 使用今天刚开盘录得的实盘数据 `2026-08-30` Globex 运行特征生成；
* 验证梯级吸收指标 `absorption_standard` 在 3.0 点阈值下能否准确捕捉到此前 `7706.00` 和 `7723.50` 的吸收带。

### 2. 顶底预判与 AI 输出验证
* 运行 `ai_tape_analyst.py` 并在输出中验证是否成功识别出预判支撑阻力位与 DPER 效率。
