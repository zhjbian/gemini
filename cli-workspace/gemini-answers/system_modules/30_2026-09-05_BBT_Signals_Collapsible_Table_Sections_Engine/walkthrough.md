# BBT Signals 实时信号表格折叠/收起交互引擎验收报告 (Walkthrough)

## 1. 概述与交付成果
针对引入 5 分钟微观信号后 Order Flow 与 SPX Gamma 两大数据表格高度过大、页面上下滑动繁琐的体验痛点，成功上线了**高质感整段折叠/收起 (Collapsible Section)** 功能：
1. **板块卡片化与一键折叠**：
   - 将“Order Flow 实时信号”与“SPX Gamma 实时信号”重构为可点击的卡片式折叠头部；
   - 标题栏右侧配有胶囊式折叠控制按钮（“收起”/“展开”文字 + 180度旋转的箭头图标），点击整行标题栏或按钮均可即时收起或展开；
2. **实时数量徽章实时映射**：
   - 在折叠栏标题右侧嵌入了轻量级徽章 (`.section-count-badge`)；
   - 深度接入 DataTables 的 `drawCallback` 生命周期，无论用户如何切换日期或多周期（30m/5m），标题栏实时展示当前显示的记录条数（例如 `90 条记录` 或 `18 / 90 条记录`），即使处于收起状态也能快速获取盘面信号统计。
3. **DataTables 宽度自适应与防错位**：
   - 在展开动画结束回调中自动调用 `$.fn.dataTable.tables({ visible: true, api: true }).columns.adjust();`，保证展开后表格列宽与表头完美对齐，无任何重叠挤压。
4. **用户偏好记忆 (LocalStorage)**：
   - 通过 `localStorage` 自动记录用户的收起/展开操作状态，页面刷新或重新打开后自动维持之前的布局结构。
5. **浅色主题规范严格遵循**：
   - 背景统一采用纯白 (`#ffffff`)，边框采用细腻柔和的 `#e2e8f0`，交互按钮采用高雅的海蓝微透明态（`#eff6ff`, border `#bfdbfe`, text `#2563eb`），完全遵循系统浅色规范。

---

## 2. 交互验证结果

### 2.1 页面加载与结构呈现
- 访问 `http://127.0.0.1:5005/bbt_signals`，HTTP 返回 200 OK；
- 页面正确渲染 `#orderFlowSectionWrapper` 与 `#spxGammaSectionWrapper`，两板块默认展开并优雅显示当前记录数。

### 2.2 折叠与展开联动
- 点击“Order Flow 实时信号”栏：整个过滤面板与数据表格以 200ms 平滑收起，文字切换为“展开”，箭头向上旋转为向下；页面高度大幅缩减逾 1500 像素，下方板块直接上提；
- 再次点击：平滑展开，DataTables 自动重新计算列宽，表头和各列数据对齐精准；
- 点击“SPX Gamma 实时信号”栏：同理支持独立平滑收起与展开，两板块互不干扰；
- 刷新页面后：收起偏好被准确恢复。

---

## 3. 修改文件清单
1. **前端模板**：`bbt_data_web/templates/bbt_signals.html`（注入折叠组件样式，重构两板块容器与标题，升级版本号至 `v=1.2.25`）。
2. **交互逻辑**：`bbt_data_web/static/js/bbt_signals.js`（实现 `toggleSignalSection`、接入 `localStorage` 记忆恢复、在 `signalsTable` 与 `gammaTable` 的 `drawCallback` 中绑定数量徽章）。
3. **系统归档**：
   - `system_modules/30_2026-09-05_BBT_Signals_Collapsible_Table_Sections_Engine/implementation_plan.md`
   - `system_modules/30_2026-09-05_BBT_Signals_Collapsible_Table_Sections_Engine/walkthrough.md`
   - 更新 `system_modules/bbt_trading_modules.html`
