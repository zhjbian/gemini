# 实施计划：每日订单流微观形态自动识别（13:10）与研究看板手动触发功能（v2）

## 目标概述

构建一套端到端的**订单流微观形态自动识别、深度分析与归档系统**，服务于最终提取量化判定规则并在盘中实时应用的目标。

系统主要包含两个核心功能模块：
1. **功能模块 1（每日 13:10 自动执行）**：在美西 13:10（RTH 盘后 10 分钟），统一使用 **SPY 1 分钟价格**及 **T 后到收盘（13:00）的全程走势**，自动识别当日关键极值点并判定形态归类（「低位彻底反转」、「低位维持震荡/回踩均线震荡」、「高位彻底反转」、「高位维持震荡/回落震荡」或「无合格形态」）；随后自动确定局部订单流分析窗口（前 90m + 后 30m）并调用 `order-flow-deep-analysis` skill 生成深度研报存库，呈现在 `bbt_signals_large_timeframe` 和 `bbt_research_analytics` 看板中。
2. **功能模块 2（看板手动触发交互卡片）**：在 `http://127.0.0.1:5005/bbt_research_analytics` 的「模块二：订单流微观结构与形态案例」表格上方新增手动触发控制卡片，支持手动指定日期、时间点、形态及窗口参数，一键生成深度分析报告并回填数据库与列表。

---

## 修正后的形态判定量化规则设计（SPY 统一标尺 + T 到收盘全程判定）

### 1. 核心设计原则修正
- **统一使用 SPY 价格计算**：基于美西 06:30 - 13:00 RTH 的 SPY 1 分钟 K 线（从 Schwab API 获取或本地缓冲）。
- **取消「低点未被实质跌破」检验**：在盘后 13:10 执行时，当日最低点 $P_{day\_low}$（发生时刻 $T_{low}$）和最高点 $P_{day\_high}$（发生时刻 $T_{high}$）已经是全天确定的全局极值，T 之后价格绝不可能再创新低/新高，因此无需检验跌破。
- **依据「T 后到收盘（13:00）」全程走势判定形态真值**：彻底避免前向仅看 30 分钟导致的误判（例如 2026-09-18 低点 09:25 后经过 2 小时筑底才全面反转暴涨，T+30m 处于基地内，必须看至收盘才能客观定型）。
- **形态分类真值与研报局部窗口解耦**：
  - **形态标签（Label）**：由 $T \to 13:00$ 收盘的全景走势给出（客观真实）；
  - **订单流研报分析窗口（OF Window）**：聚焦于拐点局部 $[T - 90\text{min}, T + 30\text{min}]$（前 90m 挖掘用于未来盘中预测的订单流异动/吸收特征，后 30m 观察右侧即时盘口反应）。

---

### 2. 基础量化指标定义 (基于 SPY 1 分钟 RTH 数据)

- $P(t)$: SPY 1 分钟价格
- $P_{open}$: 06:30 开盘价；$P_{close}$: 13:00 收盘价
- $P_{day\_low}$, $T_{low}$: 全天最低价及发生时刻（美西）
- $P_{day\_high}$, $T_{high}$: 全天最高价及发生时刻（美西）
- $Day\_Range = P_{day\_high} - P_{day\_low}$（全天总振幅，SPY 点数）
- $VWAP_{close}$: 13:00 收盘时全天成交量加权平均价
- 低点后最大反弹高点: $P_{hi\_post} = \max_{t \in [T_{low}, 13:00]} High(t)$
- 低点后最大反弹位移: $Rebound\_Pts = P_{hi\_post} - P_{day\_low}$
- 低点后反弹相对总振幅占比: $Rebound\_Ratio = Rebound\_Pts / Day\_Range$
- 收盘相对低点的净回升点数: $Net\_Close\_Pts = P_{close} - P_{day\_low}$
- 收盘价在全天振幅中的分位位置: $Close\_Pos\_Pct = (P_{close} - P_{day\_low}) / Day\_Range \times 100\%$
- 反弹成果保留率: $Rebound\_Held\_Ratio = Net\_Close\_Pts / Rebound\_Pts \times 100\%$

---

### 3. 低点两大形态判定准则

#### 【低位彻底反转 (Low Clean Reversal)】
**核心定义**：低点后走出持续性反转，反弹空间巨大，且收盘稳固守在中高位区，未被打回底部。
- **准则 1（反弹幅度显著）**：
  $Rebound\_Pts \ge 2.2$ 点（SPY，相当于 ES 约 22 点以上），且 $Rebound\_Ratio \ge 50\%$；
- **准则 2（收盘收在中高位区）**：
  收盘分位 $Close\_Pos\_Pct \ge 50\%$（收盘位于全天振幅的上半区，如 2026-09-18 达到 91.0%，2026-09-14 达到 50.8%）；
- **准则 3（反弹成果保留度良好）**：
  $Rebound\_Held\_Ratio \ge 50\%$（尾盘未出现崩塌式回撤）；
- **准则 4（均线/中枢收复）**：
  $P_{close} \ge VWAP_{close}$。

#### 【维持在低位震荡 / 回踩均线后回落震荡 (Low Consolidation)】
**核心定义**：低点后反弹疲弱（或仅回抽均线诱多），随后再度回落并持续胶着于底部区域，收盘依然处于低位。
- **准则 1（收盘被压制在低位区）**：
  收盘分位 $Close\_Pos\_Pct \le 35\%$（收盘徘徊在全天振幅底部三分之一，如 2026-09-15 仅为 29.3%）；
- **准则 2（反弹空间受限 或 冲高成果被彻底蚕食）**：
  满足以下二者之一：
  (a) 反弹本身空间狭小：$Rebound\_Pts \le 2.0$ 点（SPY）且 $Rebound\_Ratio \le 45\%$；
  (b) 曾有小幅冲高但几乎全数回吐：$Rebound\_Held\_Ratio \le 35\%$（打回低位震荡）；
- **准则 3（受制于均线/中枢）**：
  $P_{close} < VWAP_{close}$。

---

### 4. 高点两大形态判定准则（完全对称镜像）

- 高点后最大下跌低点: $P_{lo\_post} = \min_{t \in [T_{high}, 13:00]} Low(t)$
- 最大下跌位移: $Drop\_Pts = P_{day\_high} - P_{lo\_post}$
- 下跌占比: $Drop\_Ratio = Drop\_Pts / Day\_Range$
- 收盘净跌点数: $Net\_Drop\_Pts = P_{day\_high} - P_{close}$
- 下跌成果保留率: $Drop\_Held\_Ratio = Net\_Drop\_Pts / Drop\_Pts \times 100\%$

#### 【高位彻底反转 / 派发暴跌 (High Clean Reversal)】
- **准则 1（跌幅显著）**：$Drop\_Pts \ge 2.2$ 点（SPY），且 $Drop\_Ratio \ge 50\%$；
- **准则 2（收盘收在中低位区）**：收盘分位 $Close\_Pos\_Pct \le 50\%$；
- **准则 3（下跌成果保留度好）**：$Drop\_Held\_Ratio \ge 50\%$；
- **准则 4（中枢破位）**：$P_{close} \le VWAP_{close}$。

#### 【维持在高位震荡 / 冲高回落震荡 (High Consolidation)】
- **准则 1（收盘依然高位抗跌）**：收盘分位 $Close\_Pos\_Pct \ge 65\%$；
- **准则 2（跌幅狭窄 或 跌下去被再度拉起）**：
  满足 $Drop\_Pts \le 2.0$ 点且 $Drop\_Ratio \le 45\%$，或 $Drop\_Held\_Ratio \le 35\%$；
- **准则 3（中枢支撑有效）**：$P_{close} > VWAP_{close}$。

---

### 5. 当日形态候选筛选与决策机制
- 在 13:10 执行时，脚本同时对当日 $T_{low}$ 与 $T_{high}$ 进行上述准则评估；
- 若低点符合「低位反转」或「低位震荡」，高点符合「高位反转」或「高位震荡」，根据**形态显著度得分**（基于位移幅度与结构纯度）选出最具代表性的**单个主形态**；
- 若当日为窄幅无序拉锯或单边顺势不给拐点（两端都不满足阈值），判定为 `NONE`（无合格形态），记录日志但不强行出研报。

---

## 实施步骤与文件清单

### 1. 后台核心分析与判定脚本 (Python)
- **[NEW]** `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/daily_order_flow_pattern_auto.py`
  - 使用 Python 3.11 运行环境；
  - 核心逻辑：
    - 读取当日 SPY 1 分钟 K 线（从 Schwab API 获取，附带本地缓存/降级回退）；
    - 计算全天振幅、VWAP、识别 $T_{low}$ 与 $T_{high}$；
    - 执行 $T \to 13:00$ 全程走势评估，判定形态（Low Reversal / Low Consolidation / High Reversal / High Consolidation / None）；
    - 若命中形态，确定局部订单流分析窗口 $[ \max(06:30, T - 90\text{min}), \min(13:00, T + 30\text{min}) ]$；
    - 调用 `order-flow-deep-analysis/scripts/run_analysis.py` 生成浅色主题研报，并将 case 入库 `of_deep_pattern_cases`；
    - 支持 CLI 参数手动覆盖（如 `--date`, `--at`, `--pattern`, `--force`），供 Web 触发器复用。

### 2. 定时任务调度 (Cron)
- 配置每日 13:10 PST 定时任务（美西交易日盘后 10 分钟）：
  - `10 13 * * 1-5 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/daily_order_flow_pattern_auto.py >> /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/logs/daily_order_flow_pattern.log 2>&1`

### 3. Web 后端 API 与前端控制面板 (功能模块 2)
- **[MODIFY]** `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py`
  - 新增 API 路由：`POST /api/order_flow_deep/trigger_analysis`
  - 接收参数：`date`, `time` (HH:MM), `pattern_type` (low_reversal / low_consolidation / high_reversal / high_consolidation / auto), `lookback_min`, `forward_min`
  - 调用后台执行器，返回任务状态与报告文件名。
- **[MODIFY]** `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_research_analytics.html`
  - 在「模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)」卡片（`id="ofDeepCard"`）顶部表格上方，新增浅色现代卡片：**「手动触发订单流形态分析」**：
    - 输入项：日期选择器、极值点时间（HH:MM）、形态归类选择、窗口配置（默认前90后30）；
    - 操作项：「立即分析并生成报告」按钮、进度提示条；
    - 完成后自动触发 `loadOrderFlowDeepAnalysis()` 刷新列表。

### 4. 系统模块归档 (Rule 10, 11, 12)
- 建立归档目录：
  `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/100_2026-09-19_Daily_Order_Flow_Pattern_Auto_Recognition_And_Manual_Trigger/`
- 保存 `implementation_plan.md` 与 `walkthrough.md`；
- 更新总索引 `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/bbt_trading_modules.html`；
- 将形态量化判据同步记入 `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html`（及对应 `.md` 文件）。

---

## 验证计划

### 1. 历史案例回溯精准检验
- 用真实 SPY 历史分钟数据运行验证：
  - **2026-09-18**：验证自动识别 09:25 低点，经 $T \to 13:00$ 判定准确归类为【低位彻底反转 (Low Reversal)】；
  - **2026-09-15**：验证自动识别 07:53 低点，经 $T \to 13:00$ 判定准确归类为【低位维持震荡 (Low Consolidation)】；
  - **2026-09-14**：验证自动识别 07:55 低点，准确归类为【低位彻底反转 (Low Reversal)】；
  - **2026-09-16**：验证自动识别 08:47 高点，准确归类为【高位彻底反转 (High Reversal)】。

### 2. 接口与界面验证
- 测试 `POST /api/order_flow_deep/trigger_analysis` 接口；
- 由用户在浏览器打开 `http://127.0.0.1:5005/bbt_research_analytics` 测试手动触发卡片（遵循 Rule 5）。
