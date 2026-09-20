# 策略研究与模式分析独立解耦平台 (Lab 页面) 验收报告

## 1. 交付概述
根据用户对交易系统页面架构的重构需求，本次实施将分散在两个生产核心看盘页面的 5 大数据积累与模式提取卡片进行彻底解耦，统一整合至全新的专属研究平台：
- **新平台访问入口**：`http://127.0.0.1:5005/bbt_research_analytics`
- **整合的 5 大卡片**：
  1. `Adam 信号研究进展（每日 / 每周）`（来自大周期信号页）
  2. `Order Flow 深度分析（pattern 匹配）`（来自大周期信号页）
  3. `微观订单流 DOM 250ms 特征跟踪`（来自大周期信号页）
  4. `PAW 墙-吸收-收复 累积统计（研究标定）`（来自大周期信号页）
  5. `条件单统计 (Conditional Order Statistics · 挂单 / 触发)`（来自期权卖家控制台）

同时，源页面保留优雅的浅色跳转横幅与直达按钮，相关不必要的冗余 JS 脚本被全量剔除，显著降低了生产页面的 DOM 复杂度与内存开销。

---

## 2. 核心改动清单

### 2.1 后端路由与服务注册
- **新建 Blueprint 模块**：`bbt_data_web/data_app/bbt_research.py`
  - 注册 `bp_research`，提供 `/bbt_research_analytics` 视图函数。
- **主应用注册**：`bbt_data_web/bbt_data_app.py`
  - 导入并注册 `bp_research`。
  - 在系统主索引页（`/`）的 `Research & Analytics` 分组中新增“策略研究与模式分析”入口卡片。

### 2.2 全新独立模板构建 (`bbt_data_web/templates/bbt_research_analytics.html`)
- **设计风格**：严格践行 Rule 12，全站 Light Theme 浅色调（白底 `#ffffff`、冷灰 `#f8fafc`、边框 `#e2e8f0`、点缀蓝 `#2563eb` 与青绿 `#0f766e`）。
- **顶栏与快捷导航**：
  - 固定顶部导航（Brand、回跳链接）。
  - 吸顶 Anchor 导航条，支持一键平滑滚动直达 5 个独立卡片板块。
- **功能完整继承与增强**：
  - **Adam 信号研究**：支持每日研报与每周复测报告 Tab 切换，继承 Section 9 大原生 HTML 表格化垂直对齐排版。
  - **Order Flow 深度分析**：支持 pattern 案例表格化列表、置信度徽章、前向收益染色、行内展开自适应高度 iframe（无内部滚动条）、一键提取 15s/30s/60s 微观 250ms 特征，支持案例核心要点拷贝与删除。
  - **DOM 250ms 特征跟踪**：独立渲染极值槽位特征、四分位分桶分布与次日判定检验。
  - **PAW 墙体标定**：三档 30 分钟表现、行权价 90% 持稳安全距离、逐日可用性表格。
  - **条件单统计**：包含 7 大核心 KPI 指标卡、5 张统一像素列宽对齐的分组表（按方向双向对称、按来源、按子场景、按小时段、按日趋势），支持来源下拉切换与一键刷新。

### 2.3 生产页面减负瘦身
- **`bbt_data_web/templates/bbt_signals_large_timeframe.html`**：
  - 移除原 Adam 卡片、OF 深度卡片、DOM 特征跟踪卡片和 PAW 标定卡片 DOM 节点。
  - 替换为浅色风格的轻量重定向通知横幅，并附带直达按钮。
  - 移除已迁移的 JS 函数（`ofDeep...`, `domFeat...`, `adamMarkNonSignal`, `PAW_STATS_...` 等），页面净瘦身约 700 行。
- **`bbt_data_web/templates/bbt_option_seller.html`**：
  - 移除原 `#condStatsSection`，替换为条件单统计归档引导横幅。
  - 移除 `_csBuildTable`, `_csRows`, `loadConditionalOrderStats`, `toggleCondStats` 及 60s 定时轮询器。
  - 在页面头部 Brand 区域增设“条件单统计 Lab”与“策略研究 Lab”直达按钮。

---

## 3. 验收验证结果

### 3.1 语法编译测试
```bash
python3 -m py_compile bbt_data_web/bbt_data_app.py bbt_data_web/data_app/bbt_research.py
```
**结果**：0 错误，通过。

### 3.2 路由与服务可用性测试
```bash
curl -s -o /dev/null -w "research_lab: %{http_code}\n" http://127.0.0.1:5005/bbt_research_analytics
curl -s -o /dev/null -w "signals_large_timeframe: %{http_code}\n" http://127.0.0.1:5005/bbt_signals_large_timeframe
curl -s -o /dev/null -w "option_seller: %{http_code}\n" http://127.0.0.1:5005/bbt_option_seller
curl -s -o /dev/null -w "index: %{http_code}\n" http://127.0.0.1:5005/
```
**结果**：全部端点均返回 `200 OK`，服务正常运行。

### 3.3 规则遵守情况检查
- **Rule (1)**：保持严谨专业中性表述。
- **Rule (5)**：未自动调用浏览器测试，由用户后续在网页端直接体验与确认。
- **Rule (7)**：纯文本公式与度量，不包含 LaTeX 符号。
- **Rule (10)**：已在 `system_modules/96_2026-09-18_Research_And_Pattern_Analytics_Lab_Page_Decoupling/` 完成文档归档，并在 `bbt_trading_modules.html` 增补 M19 模块记录。
- **Rule (12)**：新页面及引导横幅全部严格采用清晰护眼的 Light Theme 浅色主题。
