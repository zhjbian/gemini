# 验收报告 (Walkthrough) - 微观订单流 DOM 250ms 特征跟踪卡片独立解耦 (方案A)

## 1. 任务背景与问题确认
在大周期信号研判页面 `http://127.0.0.1:5005/bbt_signals_large_timeframe` 中：
- 展开「Adam 信号研究进展（每日 / 每周）」卡片后，报告表格下方出现「🧱 DOM 250ms 特征跟踪」与「📅 DOM pattern 的当天 / 次日判定力（短期口径）」；
- 交易员提出疑问：“是 bug 还是 by design？”
- 诊断结果：代码层面为历史 By Design 实现（2026-09-15 模块 61 实施时挂载），但在业务语义与视觉层级上属于明显的“归属错位”（宏观推特研报与本地微观订单流盘口重放混杂）；
- 交易员选择执行**方案 A**：彻底剥离出独立的微观订单流 DOM 特征跟踪卡片。

---

## 2. 核心改动与工程实现

### (1) 卡片 DOM 结构彻底解耦 ([bbt_signals_large_timeframe.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals_large_timeframe.html))
- 将 `#adamResearchCard` 内的原 `#adamDomFeatureStatsWrap` 代码块完全移出；
- 在 `#adamResearchCard` 与 `#ofDeepCard` 之间新增同级独立卡片 `#domFeatureCard`：
  - 卡片标题：`<i class="fas fa-cubes"></i> 微观订单流 DOM 250ms 特征跟踪`
  - 属性标记：带 `copyCardLink` 复制按钮与 `只标注 · 不进决策` 浅色徽章；
  - 独立操作区：包含接口专属 `刷新` 按钮与 `收起/展开` 切换按钮；
  - 内部内容容器 `#domFeatureBodyContainer` 默认收起（`display:none`），包含完整的统计维度切换（每日/每周）、DOM 槽位跟踪表、特征分桶表以及「DOM pattern 当天/次日判定力」日级检验表格。

### (2) 前端控制逻辑与加载生命周期解耦
- **独立折叠状态记忆**：实现 `applyDomFeatureVisibility()` 与 `toggleDomFeatureCard()`，状态持久化保存在 `localStorage('bbt_dom_feature_open')`；
- **接口解耦**：
  - 移除 `loadAdamResearchReports()` 中原先伴随执行的 `try { window.loadAdamDomFeatureStats(); }`；
  - 移除 `toggleAdamResearchCard()` 中首次展开时的伴随拉取；
  - 仅在 `#domFeatureCard` 展开或用户显式点击该卡片右上角“刷新”时，才发起 `/data/dom_feature_stats` 数据请求；
- **报告默认全部折叠（禁止自动展开首项）**：
  - 移除 `loadAdamResearchReports()` 加载完毕后自动将首条报告（`adamReports[0]`）展开（强制 `d0.style.display = 'table-row'`）的历史逻辑；
  - 保持全部周报/日报默认收起（`display:none`），由交易员按需点击各行开头的 `+` 手动展开，避免每次刷新时占用大面积视窗；
- **页面初始化支持**：在 `DOMContentLoaded` 中注册 `applyDomFeatureVisibility()`，若上次会话保持展开态则恢复按需加载。

---

## 3. 验证与交付

### (1) 页面结构检查
通过 curl 与本地渲染管道验证：
- `http://127.0.0.1:5005/bbt_signals_large_timeframe` 正常响应（200 OK，体积 ~213KB）；
- `id="domFeatureCard"` 与 `id="adamResearchCard"` 各自独立存在于主布局中；
- 原 `#adamResearchCard` 展开后仅包含周报/日报列表及分页器，底部无任何无关 DOM 盘口数据混杂；
- 新 `#domFeatureCard` 独立存在，具备完整的折叠/展开与刷新功能。

### (2) 归档文件
- 实施代码：[bbt_data_web/templates/bbt_signals_large_timeframe.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals_large_timeframe.html)
- 实施计划：[implementation_plan.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/94_2026-09-18_DOM_250ms_Feature_Tracking_Card_Decoupling/implementation_plan.md)
- 模块演进索引：[bbt_trading_modules.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/bbt_trading_modules.html#mod-16)
