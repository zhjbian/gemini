# BBT Signals 实时信号表格折叠/收起交互引擎实施计划 (Implementation Plan)

## 1. 概述与背景
在 BBT Signals 看盘页面（`http://127.0.0.1:5005/bbt_signals`）中，随着引入 5 分钟微观周期，Order Flow 与 SPX Gamma 每天产生高达 80~90+ 条高密度信号记录。原有页面中两大信号表格默认全部垂直铺开（每页显示 50 条），导致单个表格高度达到上千像素，两个表格垂直叠加极大占用了页面可视区域，用户在查看上方图表、宏观经济事件或底部综合决策时需要大量滚动鼠标。

为解决这一界面体验痛点，需在保留全部过滤与表格交互的前提下，为“Order Flow 实时信号”与“SPX Gamma 实时信号”两大核心 Section 增加**整段打开/收起 (Collapsible Section)** 功能。

---

## 2. 详细设计与技术方案

### 2.1 UI 结构与浅色风格规范
- **遵循 Light Theme 规则 (12)**：统一采用纯白卡片底色 (`--card-bg: #ffffff`)、微浅灰 hover 状态 (`#f8fafc`)、淡海蓝胶囊按钮 (`#eff6ff`, border `#bfdbfe`, text `#2563eb`)。
- **标题栏卡片化升级**：
  - 左侧：对应业务图标（`fa-stream` / `fa-wave-square`）+ 醒目标题 + 动态记录数微章 (`.section-count-badge`)；
  - 右侧：精致的收起/展开胶囊按钮与旋转箭头图标（`fa-chevron-up` ↔ `fa-chevron-down`）；
  - 点击整行标题栏即可快速触发收起/展开，交互直观顺手。
- **内容容器包裹**：
  - 将过滤栏 (`.filter-panel`) 与表格容器 (`.table-container`) 完整收拢在 `.collapsible-section-body` 容器内。

### 2.2 交互逻辑与 DataTables 列宽自适应
- **状态切换**：通过 jQuery `slideToggle` / `slideUp` / `slideDown` 动画平滑过渡；
- **DataTables 列宽重绘**：在 `slideDown` 展开回调中执行 `$.fn.dataTable.tables({ visible: true, api: true }).columns.adjust();`，根除 DataTables 在隐藏后重新显示时表头错位的顽疾；
- **用户偏好记忆**：利用 `localStorage`（键名 `bbt_collapse_of` 与 `bbt_collapse_gamma`）保存用户当前收起/展开偏好，刷新页面后自动维持用户设定的视图状态；
- **实时数量徽章联动**：在 DataTables 的 `drawCallback` 钩子中，自动读取当前过滤后的显示行数，实时显示在折叠栏标题右侧（如 `90 条记录`），收起状态下依然洞悉盘面信号规模。

---

## 3. 涉及文件明细
1. `bbt_data_web/templates/bbt_signals.html`：新增折叠样式类，重构两大 Section 的 HTML 包装容器，升级静态脚本版本号至 `v=1.2.25`。
2. `bbt_data_web/static/js/bbt_signals.js`：实现全局 `toggleSignalSection` 切换函数，接入 `localStorage` 恢复逻辑与 `drawCallback` 数量徽章绑定。
3. 归档维护：`system_modules/30_2026-09-05_BBT_Signals_Collapsible_Table_Sections_Engine/` 与 `system_modules/bbt_trading_modules.html`。
