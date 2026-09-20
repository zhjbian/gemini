# 策略研究与模式分析独立解耦平台 (Lab 页面) 实施计划

## 1. 需求与背景
用户在现有 trading 信号系统日常使用中积累了多项用于后续分析、策略研究与模式提取的卡片模块：
1. `Adam 信号研究进展（每日 / 每周）`（原位于 `bbt_signals_large_timeframe.html`）
2. `Order Flow 深度分析（pattern 匹配）`（原位于 `bbt_signals_large_timeframe.html`）
3. `微观订单流 DOM 250ms 特征跟踪`（原位于 `bbt_signals_large_timeframe.html`）
4. `PAW 墙-吸收-收复 累积统计（研究标定）`（原位于 `bbt_signals_large_timeframe.html`）
5. `条件单统计 (Conditional Order Statistics · 挂单 / 触发)`（原位于 `bbt_option_seller.html`）

### 存在的问题
- **生产看盘页面负载重**：实盘与日内看盘核心页面（大周期信号页与期权卖家控制台）混杂了大量离线或复盘标定卡片，页面 DOM 体积庞大、代码行数多（达数千甚至九千行），且包含了许多针对研究报告自适应计算、DOM 特征请求的逻辑，分散了实盘交易员注意力。
- **定位与分析割裂**：5 个卡片分散在不同页面，无法一站式横向对比“宏观研报 vs 订单流微观 Pattern vs 250ms 盘口特征 vs 墙体吸收率 vs 自动单触发率”。

### 解决思路
新建专属策略研究与模式分析页面 `http://127.0.0.1:5005/bbt_research_analytics`，统一托管上述 5 大研究卡片；在源页面留下清晰优雅的浅色跳转横幅与快捷导航，大幅为生产看盘页面减负瘦身。

---

## 2. 架构设计与技术方案

### 2.1 后端路由与 Blueprint 解耦
- 新建模块 `bbt_data_web/data_app/bbt_research.py`，定义 `bp_research = Blueprint('bp_research', __name__)`。
- 暴露 `/bbt_research_analytics` 路由，渲染 `bbt_research_analytics.html`。
- 在 `bbt_data_web/bbt_data_app.py` 中注册 `bp_research`。
- 在系统首页（`/` 导航卡片列表）的“Research & Analytics”分组下新增“策略研究与模式分析”卡片。

### 2.2 前端独立模板设计 (`bbt_research_analytics.html`)
严格遵守 Rule 12（全 Light Theme 浅色主题），采用现代清爽设计：
- **Header 与导航条**：固定顶部栏，提供到大周期信号页、期权卖家系统、BBT Signals 首页的快速回跳链接。
- **页面锚点导航栏 (Anchor Nav Bar)**：提供 4 大板块一键直达跳转（`#module-adam-research`, `#module-order-flow-deep`, `#module-dom-features`, `#module-paw-calibration`, `#module-conditional-order-stats`）。
- **Module 1：Adam 信号研究进展**：
  - 每日信号研究报告与每周复测报告切换 Tab。
  - 9 大部分原生 HTML 表格化呈现（垂直列对齐）。
  - 支持单条报告折叠/展开、全选/反选与批量操作。
- **Module 2：Order Flow 深度分析（pattern 匹配）**：
  - 案例表格（方向、模式、置信度、入场价、前向 15/30/60m 胜负、核心看点）。
  - 点击 `+` 行内展开独立报告 iframe（同源自动量取高度，无内部滚动条）。
  - 内嵌 15s/30s/60s 微观 DOM 250ms 四大核心特征（吸收量比、压单持久度、撤单率、追价强度）。
  - 提供单案例一键拷贝与删除功能。
- **Module 3：微观订单流 DOM 250ms 特征跟踪**：
  - 独立卡片，展示 250ms 盘口槽位跟踪、特征分桶与判定力检验。
- **Module 4：PAW「墙-吸收-收复」累积统计（研究标定）**：
  - E1/E2/E3 三档 30 分钟表现、行权价安全距离（E1 基础率目标 90% 持稳）、逐日数据日状态。
- **Module 5：条件单统计 (挂单 / 触发 / 时段截断)**：
  - 汇总 KPI（挂单、触发、触发率、平均等候、偏差、撤销截断）。
  - 5 张共用等宽列网格的分组表（按方向双向对称、按来源、按子场景、按小时段、按日趋势）。
  - 来源筛选器与 60 秒可选自动轮询。

### 2.3 源页面精简瘦身
- **`bbt_signals_large_timeframe.html`**：
  - 顶部导航栏增加直达“策略研究 Lab”链接。
  - 移除原 4 个卡片 DOM，替换为优雅的浅色跳转横幅。
  - 移除已迁移的 JS 代码（`ofDeep...`、`domFeat...`、`adamMarkNonSignal`、`pawStats...` 等），页面净减约 700 行。
- **`bbt_option_seller.html`**：
  - 顶部 Brand Group 增加“条件单统计 Lab”与“策略研究 Lab”快捷按钮。
  - 移除 `#condStatsSection`，替换为条件单归档引导横幅。
  - 移除 `_csBuildTable`, `_csRows`, `loadConditionalOrderStats`, `toggleCondStats` 等不再需要的辅助函数与 60s 定时器。

---

## 3. 验证与交付计划
1. Python 语法编译检测（`python -m py_compile`）。
2. HTTP 状态码验证（`/bbt_research_analytics`, `/bbt_signals_large_timeframe`, `/bbt_option_seller`, `/`）。
3. 归档至 `system_modules/96_2026-09-18_Research_And_Pattern_Analytics_Lab_Page_Decoupling/` 并更新 `bbt_trading_modules.html`（添加 M19 模块历史）。
