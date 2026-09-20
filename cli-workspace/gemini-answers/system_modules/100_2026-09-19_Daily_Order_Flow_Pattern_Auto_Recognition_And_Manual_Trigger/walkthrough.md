# 验收报告：每日订单流微观形态自动识别（13:10）与研究看板手动触发功能

## 概述与交付目标

本次升级成功落地了**订单流微观形态全自动识别、局部窗口分析与研究看板手动触发系统**，达成以下核心业务与工程目标：
1. **统一 SPY 标尺与全景判定**：废除仅基于短窗（30m）容易产生的假形态误判，统一采用美西 06:30 至 13:00 RTH 的 SPY 1 分钟走势，依据极值发生时刻 $T$ 到收盘（13:00）的全程路径，客观裁决形态真值。
2. **四大形态量化标准落地**：建立并验证了【低位彻底反转 (Low Clean Reversal)】、【维持在低位震荡 (Low Consolidation)】、【高位彻底反转 (High Clean Reversal)】、【维持在高位震荡 (High Consolidation)】的严谨数学阈值。
3. **每日 13:10 自动化流水线**：盘后 10 分钟全自动执行，识别极值、裁决形态、截取局部转折窗口 $[ \max(06:30, T - 90\text{min}), \min(13:00, T + 30\text{min}) ]$，调用 `order-flow-deep-analysis` 进行 TICK/DOM 交叉机检并生成浅色主题 HTML 研报与存库 `of_deep_pattern_cases`。
4. **Lab 看板手动触发交互卡片**：在 `http://127.0.0.1:5005/bbt_research_analytics` 模块二顶部新增卡片，支持手动指定任意日期、时间点与形态一键分析与建档。

---

## 交付文件清单

| 文件路径 | 模块 / 角色 | 改动性质 | 说明 |
| :--- | :--- | :--- | :--- |
| `PyTools/jobs/daily_order_flow_pattern_auto.py` | 核心引擎 / 定时任务 | **[NEW]** | SPY 分钟走势抓取、全景形态裁决、局部窗口计算及分析流水线主程序 |
| `PyTools/jobs/run_daily_order_flow_pattern.sh` | 调度包装 / 自动化 | **[NEW]** | 供 cron / launchd 调用的可执行包装脚本（含标准路径与日志重定向） |
| `bbt_data_web/data_app/bbt_signals.py` | 后端 API | **[MODIFY]** | 新增 `POST /api/order_flow_deep/trigger_analysis` 路由，提供异步/同步触发支持 |
| `bbt_data_web/templates/bbt_research_analytics.html` | 前端界面 | **[MODIFY]** | 模块二卡片顶部嵌入浅色手动触发控制面板与实时状态反馈，更新初始化逻辑 |
| `system_modules/100_.../implementation_plan.md` | 知识归档 | **[NEW]** | 规范化技术实施计划归档 |
| `system_modules/100_.../walkthrough.md` | 知识归档 | **[NEW]** | 规范化功能交付验收报告 |

---

## 核心技术与量化规则实现细节

### 1. SPY 全程走势判定指标与阈值
所有指标均使用美西 06:30 - 13:00 RTH 的 SPY 1 分钟 K 线：
- **低位彻底反转 (Low Clean Reversal)**：
  - 低点后最大反弹: $Rebound\_Pts \ge 2.2$ 点 且 $Rebound\_Ratio \ge 50\%$；
  - 收盘分位: $Close\_Pos\_Pct \ge 50.0\%$（收在上半区，如 2026-09-18 达到 91.06%）；
  - 反弹保留率: $Rebound\_Held\_Ratio \ge 50.0\%$；
  - 中枢站稳: $P_{close} \ge VWAP_{close}$。
- **维持在低位震荡 / 回踩均线后回落震荡 (Low Consolidation)**：
  - 收盘受制低位: $Close\_Pos\_Pct \le 35.0\%$（如 2026-09-15 为 29.3%）；
  - 反弹受限或尽数回吐: ($Rebound\_Pts \le 2.0$ 且 $Rebound\_Ratio \le 45\%$) 或 ($Rebound\_Held\_Ratio \le 35\%$);
  - 均线下行受阻: $P_{close} < VWAP_{close}$。
- **高位反转与震荡**：按上述逻辑取反，镜像对称执行。

### 2. 自动化调度配置
配置每日 13:10 PST（美西交易日盘后 10 分钟）自动触发：
```bash
10 13 * * 1-5 /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/run_daily_order_flow_pattern.sh
```

---

## 验证与验收记录

### 1. 自动执行全链路验证 (以 2026-09-18 真实行情为例)
执行测试命令：
```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/daily_order_flow_pattern_auto.py \
  --date 2026-09-18
```
**输出日志与判定结果**：
- **数据提取**：抓取 390 根 SPY 1 分钟完整 RTH K 线（开盘 761.19，收盘 761.64，全天振幅 4.029 点）；
- **极值识别**：精准捕获全天最低点 757.971（发生时刻 09:25）；
- **全景裁决**：
  - 低点后最大反弹 4.029 点（100% 反弹）；
  - 收盘 761.64，收盘分位 91.06%，收在 VWAP 760.38 之上；
  - 自动裁决结论：`low_clean_reversal`（低位彻底反转，评分 181.35）；
- **订单流窗口与报告**：
  - 局部窗口自动锁定：`07:55`（09:25 前 90m）至 `09:55`（09:25 后 30m）；
  - 调用 `run_analysis.py` 执行双数据源（逐笔 TICK + 挂单 DOM）交叉机检；
  - 成功写入研报：`order_flow_analysis_ES_2026-09-18_0955_low_clean_reversal_2026-09-19_1722.html`；
  - 成功落库 Case：`ES_2026-09-18_0955`。

### 2. Web API 接口验证
执行 curl 模拟前端发起调用：
```bash
curl -s -X POST http://127.0.0.1:5005/api/order_flow_deep/trigger_analysis \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-09-18","at":"09:25","pattern":"low_clean_reversal"}'
```
**返回报文**：
```json
{
  "ok": true,
  "result": {
    "bias": "bullish",
    "case_id": "ES_2026-09-18_0955",
    "date": "2026-09-18",
    "pattern_name": "低位彻底反转",
    "pattern_slug": "low_clean_reversal",
    "pivot_time": "09:25",
    "report_file": "order_flow_analysis_ES_2026-09-18_0955_low_clean_reversal_2026-09-19_1723.html",
    "status": "ok",
    "window_end": "09:55",
    "window_start": "07:55"
  }
}
```
并且在 `http://127.0.0.1:5005/data/order_flow_deep_analysis?limit=1` 中立即可见新生成的报告与案例映射！

### 3. 前端交互界面就绪
- 在 `http://127.0.0.1:5005/bbt_research_analytics` 模块二「Order Flow 深度分析」表格上方成功嵌入了极简白底、浅蓝风格的手动触发卡片；
- 支持用户手动选择日期、填写极值点（留空则全天自适应）、选择形态、配置回看/验证时长并一键执行；
- 执行过程中显示 Loading 状态，成功后直接弹出对应研报查看链接，并自动刷新下方历史案例表格。

---

## 新增功能：多级深层链接复制（3 级及以上多行格式）

根据用户需求，将 `http://127.0.0.1:5005/bbt_research_analytics` 看板的复制按钮拓展至 3 级（案例行）及 4 级（研报内部章节），并在 3 级及以上自动采用多行换行格式：

### 1. 各层级复制输出格式规范
- **1 级与 2 级（单行模式）**：
  `http://127.0.0.1:5005/bbt_research_analytics -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)`
- **3 级（多行模式 · 案例级）**：
  ```text
  http://127.0.0.1:5005/bbt_research_analytics 
  -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)
  -> ES / 2026-09-18 / 08:25 → 09:45 / BULLISH / P4
  ```
- **4 级（多行模式 · 研报内章节级）**：
  ```text
  http://127.0.0.1:5005/bbt_research_analytics 
  -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)
  -> ES / 2026-09-18 / 08:25 → 09:45 / BULLISH / P4
  -> 0️⃣ 订单流形态识别与判定 (Order Flow Pattern Recognition)
  ```
  ```text
  http://127.0.0.1:5005/bbt_research_analytics 
  -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)
  -> ES / 2026-09-18 / 08:25 → 09:45 / BULLISH / P4
  -> 1️⃣ 合并时间线
  ```
  ```text
  http://127.0.0.1:5005/bbt_research_analytics 
  -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)
  -> ES / 2026-09-18 / 08:25 → 09:45 / BULLISH / P4
  -> 2️⃣ 🧭 DOM × TICK 合并结论
  ```
  ```text
  http://127.0.0.1:5005/bbt_research_analytics 
  -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)
  -> ES / 2026-09-18 / 08:25 → 09:45 / BULLISH / P4
  -> 3️⃣ 系统 order flow 指标解读
  ```
  ```text
  http://127.0.0.1:5005/bbt_research_analytics 
  -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)
  -> ES / 2026-09-18 / 08:25 → 09:45 / BULLISH / P4
  -> 4️⃣ 🧱 DOM 深度分析
  ```
  ```text
  http://127.0.0.1:5005/bbt_research_analytics 
  -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)
  -> ES / 2026-09-18 / 08:25 → 09:45 / BULLISH / P4
  -> 5️⃣ 📈 TICK 深度分析
  ```

### 2. 改造范围与技术落地
1. **主页面层 (`bbt_research_analytics.html`)**：
   - 升级 `copyCardLink` 算法：当层级列表元素数 >= 2（即第 3 级及以上）时，自动换行输出为每行一个层级箭头 `-> ...`；
   - 深度分析表格 `ofDeepRenderTable()` 在第 1 列（Ticker）和操作列注入带有完整层级路径属性 `data-path` 的浅色微型复制按钮；
   - 在侧边抽屉 / 弹窗中展示的 DOM 250ms 特征卡片和 Adam 报告列表中均增加了层级复制支持。
2. **研报内嵌层与动态注入 (`bbt_signals.py`)**：
   - 在 `get_order_flow_deep_report` 路由中提供无感知动态注入，支持所有现存与新生成的研报；
   - 研报中各章节标题右侧增加浅色微型复制按钮，点击后自动从 iframe 宿主环境提取上下文并组装完整 4 级路径写入系统剪贴板，同时触发顶层绿色 Toast 提示。
3. **研报生成引擎 (`run_analysis.py`, `adam_dom_analysis.py`, `adam_tick_analysis.py`)**：
   - 在所有分析器 HTML 输出模板中原生内建上述复制按钮与脚本，保证未来生成的所有离线研报开箱即用。
4. **历史报告全量更新**：
   - 对现存全部 38 份 HTML 研报进行了批量升级与格式去重校验。

---

## 优化补充：前向 15m / 30m / 60m 收益与达标标记自动计算与回填

1. **机制说明**：
   - 订单流形态机检引擎遵循严格的**无前视设计**，在落库 Case 时 `fwd_15m_ret, fwd_30m_ret, fwd_60m_ret` 初始置空（待行情走完后回填）；
   - 在每日盘后（13:10）自动化任务及复盘回溯中，未来 60 分钟走势已然完成。为此在 `daily_order_flow_pattern_auto.py` 中增加了 `compute_and_backfill_forward_returns` 模块；
   - 自动对照 T0（如 09:55）时刻 ES 价格与 T0+15m、T0+30m、T0+60m 真实成交价，计算收益点数及是否满足达标门槛（多头 >= 3.0 点 / 空头 <= -3.0 点），并直接回填至 `of_deep_pattern_cases` 与研报头部看板中。

---

## 模块一（宏观与多周期信号跟踪 Macro & Signals Tracking）深层层级拷贝落地

在 `http://127.0.0.1:5005/bbt_research_analytics` 模块一中实现完整的 1~6 级深层拷贝链接体系：
1. **Level 1 (Section)**: `模块一：宏观与多周期信号跟踪 (Macro & Signals Tracking)`
2. **Level 2 (Card)**: `Adam 信号研究进展（每日 / 每周）`
3. **Level 3 (Report Row)**: `日报 / 2026-09-18 / BULLISH`（在报告列与操作列均提供直达拷贝图标）
4. **Level 4 (Major Section)**: `📈 当日 ES 价格走势与关键点位 (5-Minute Candlestick Chart)`、`🔍 Adam今日信号深度分析（order flow 逐帖验证）`、周报各分区分栏等
5. **Level 5 (Signal Post)**: `09:28 BULLISH · None · conv=None · 综合判定 验证`
6. **Level 6 (Post Sub-section)**: `1️⃣ 合并时间线`、`2️⃣ 🧭 DOM × TICK 合并结论`、`3️⃣ 发帖后多时点验证`、`4️⃣ 系统 order flow 指标解读`、`5️⃣ 🧱 DOM 深度分析`、`6️⃣ 📈 TICK 深度分析`

所有 3 级及以上拷贝链接严格统一输出多行回车格式：
```text
http://127.0.0.1:5005/bbt_research_analytics 
-> 模块一：宏观与多周期信号跟踪 (Macro & Signals Tracking)
-> Adam 信号研究进展（每日 / 每周）
-> 日报 / 2026-09-18 / BULLISH
-> 🔍 Adam今日信号深度分析（order flow 逐帖验证）
-> 09:28 BULLISH · None · conv=None · 综合判定 验证
-> 2️⃣ 🧭 DOM × TICK 合并结论（两个数据源交叉印证 ✓）
```
全部遵循浅色主题规范、无 LaTeX 乱码渲染，并自带绿色打勾视觉反馈与平滑 Toast 提示！
