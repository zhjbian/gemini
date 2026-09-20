# Implementation Plan - DOM 盘口压力与价格走势图全链路贯通与自适应渲染

在 Research & Pattern Analytics 平台（`http://127.0.0.1:5005/bbt_research_analytics`）的【模块一：Adam 信号逐帖微观验证】与【模块二：订单流形态深度研报】中，全面打通并增强「盘口压力与价格（逐分钟 mid / ±5 失衡 / 买卖挂单比−1 / VWAP·POC）」Highcharts 双轴趋势图表，消除因折叠隐藏导致图表无法初始化或宽度坍缩问题，确保用户展开任一研报或案例时均能秒级自适应渲染呈现。

## User Review Required

> [!NOTE]
> 本次改动涉及前端图表生命周期优化（IntersectionObserver + visibility 检查）及静态研报 iframe 动态资源注入解耦，全部保持白底浅色主题（Light Theme），无破坏性变更。

## Proposed Changes

### 1. 后端注入解耦 (Iframe Deep Reports)

#### [MODIFY] [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py)
- 解耦 `/data/order_flow_deep_report` 中 `copyReportSectionLink` 与 `initDomReportCharts` 的注入逻辑。
- 保证无论静态 HTML 磁盘文件是否已经包含复制按钮，均无条件检查并注入 Highcharts 库与 `initDomReportCharts()` 脚本，确保模块二所有案例（如 `07:55 → 09:55 / BULLISH / P4`）底部的 DOM 压力走势图正常渲染。

### 2. 前端看板图表自适应生命周期增强 (Module 1 & Module 2)

#### [MODIFY] [bbt_research_analytics.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_research_analytics.html)
- 增强 `adamInitDomCharts(root)` 与新增 `adamRenderSingleDomChart(el)`：
  - 针对折叠或隐藏容器（`display: none`，`offsetWidth === 0`），避免提前初始化导致 SVG 宽度为 0；
  - 引入 `IntersectionObserver` 监听，在元素进入可视区域或父容器展开时自动触发图表绘制；
  - 已初始化的图表自动执行 `chart.reflow()` 自适应重绘，保证在任何分辨率与视窗尺寸下完美填充。

## Verification Plan

### Automated Tests
- `python3 -m py_compile bbt_data_web/data_app/bbt_signals.py`
- Node.js 校验 `bbt_data_web/templates/bbt_research_analytics.html` 中全部 `<script>` 标签语法
- curl 校验 `/data/order_flow_deep_report` 是否包含 `initDomReportCharts` 及 Highcharts 脚本
- curl 校验 `/bbt_research_analytics` 是否包含 `adamRenderSingleDomChart`

### Manual Verification
- 提示用户刷新 `http://127.0.0.1:5005/bbt_research_analytics`，展开模块一【09:28 验证帖 -> 5️⃣ 🧱 DOM 深度分析】以及模块二【07:55 → 09:55 -> 4️⃣ 🧱 DOM 深度分析】，确认底部「盘口压力与价格」双轴图表均完整展示。
