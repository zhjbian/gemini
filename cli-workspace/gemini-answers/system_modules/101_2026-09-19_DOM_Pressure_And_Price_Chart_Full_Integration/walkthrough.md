# 验收报告：DOM 盘口压力与价格走势图全链路贯通与自适应渲染

## 概述与交付目标

本次升级在 Research & Pattern Analytics 平台（`http://127.0.0.1:5005/bbt_research_analytics`）中，彻底解决了【模块一：Adam 信号逐帖验证】与【模块二：订单流形态深度研报】中 DOM 深度分析底部「盘口压力与价格」双轴图表无法展示或宽度异常的问题：

1. **模块一（Adam 研报）生命周期与自适应渲染**：
   - 解决因研报默认收起（`display: none`）导致 Highcharts 提前初始化导致容器宽度坍塌为 0 的问题；
   - 引入 `adamRenderSingleDomChart(el)` 与 `IntersectionObserver` 视口监听，确保不论是点击单个帖子标题展开、点击“展开深度分析”按钮、还是点击“全部展开”，均能在 DOM 容器可见时自动绘制图表，并自适应 `reflow()` 适配完整视宽。
2. **模块二（Order Flow 深度研报 iframe）资源注入解耦**：
   - 修复 `/data/order_flow_deep_report` 中因 `copyReportSectionLink` 与 `initDomReportCharts` 嵌套判断导致的脚本漏注入问题；
   - 无论磁盘上的静态研报 HTML 是否已包含复制链接功能，均能独立检测并无条件注入 Highcharts 核心库与 `initDomReportCharts()` 渲染脚本，使案例（例如 `07:55 → 09:55 / BULLISH / P4`）底部的盘口压力图表即开即用。

---

## 修改文件清单

| 文件路径 | 模块 / 角色 | 改动性质 | 说明 |
| :--- | :--- | :--- | :--- |
| `bbt_data_web/data_app/bbt_signals.py` | 后端 API | **[MODIFY]** | 解耦 `/data/order_flow_deep_report` 注入逻辑，保证 Highcharts 与 `initDomReportCharts` 独立注入 |
| `bbt_data_web/templates/bbt_research_analytics.html` | 前端界面 | **[MODIFY]** | 增加 `adamRenderSingleDomChart`，引入 `IntersectionObserver` 监听与 `reflow()` 自适应，避免隐藏初始化崩溃 |
| `system_modules/101_.../implementation_plan.md` | 知识归档 | **[NEW]** | 规范化技术实施计划归档 |
| `system_modules/101_.../walkthrough.md` | 知识归档 | **[NEW]** | 规范化功能交付验收报告 |

---

## 核心图表指标与呈现规范

图表严格遵循白底浅色主题（Light Theme），统一展示以下四维数据：
- **左 Y 轴（价格）**：
  - `mid 中间价`（黑灰深色折线 `#0f172a`）；
  - `Session VWAP`（紫色虚线 `#7c3aed`）；
  - `POC 最密集价`（琥珀色点线 `#b45309`）。
- **右 Y 轴（失衡 / 比值 - 1，区间 -1.0 到 +1.0）**：
  - `±5 失衡`（蓝色折线 `#2563eb`）；
  - `买/卖挂单比 - 1`（翠绿折线 `#047857`）；
  - `0 平衡基准线`（浅灰虚线 `#cbd5e1`）。

---

## 验证与验收记录

1. **Python 语法校验**：
   ```bash
   python3 -m py_compile bbt_data_web/data_app/bbt_signals.py
   ```
   *结果：校验通过，返回码 0。*

2. **JavaScript 语法校验**：
   ```bash
   node -e "... new Function(code) ..."
   ```
   *结果：`bbt_research_analytics.html` 内所有 `<script>` 标签解析无任何语法错误。*

3. **模块二 iframe 接口注入检验**：
   ```bash
   curl -s "http://127.0.0.1:5005/data/order_flow_deep_report?file=order_flow_analysis_ES_2026-09-18_0955_low_clean_reversal_2026-09-19_1723.html" | grep "initDomReportCharts"
   ```
   *结果：成功包含 Highcharts 库引用与 `initDomReportCharts()` 自动初始化函数。*

4. **模块一看板服务检验**：
   ```bash
   curl -s "http://127.0.0.1:5005/bbt_research_analytics" | grep "adamRenderSingleDomChart"
   ```
   *结果：成功输出增强版渲染与视口监听函数。*
