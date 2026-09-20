# 实施计划 - 微观订单流 DOM 250ms 特征跟踪卡片独立解耦 (方案A)

## 1. 需求背景
在大周期信号研判页面 `http://127.0.0.1:5005/bbt_signals_large_timeframe` 中：
- 用户反馈在「Adam 信号研究进展（每日 / 每周）」卡片展开后的报告列表底部，存在「🧱 DOM 250ms 特征跟踪」与「📅 DOM pattern 的当天 / 次日判定力（短期口径）」两个微观订单流统计板块；
- 经查实，这是 2026-09-15（模块 61）开发过程中将盘口回放数据暂挂在 Adam 卡片内的历史遗留实现，造成了明显的业务语义错位（宏观 Adam 研报 vs 微观 MotiveWave DOM 盘口回放统计混杂）；
- 用户经评估确认采纳**方案 A**：将 DOM 特征跟踪相关内容从 Adam 卡片中彻底剥离，建立独立的微观订单流 DOM 特征跟踪卡片。

## 2. 改造方案
1. **DOM 结构重构 ([bbt_signals_large_timeframe.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals_large_timeframe.html))**：
   - 彻底关闭 `#adamResearchCard` 的内容容器，使其仅包含 Adam 研报列表与分页器；
   - 在 `#adamResearchCard` 下方新建独立卡片 `#domFeatureCard`，标题命名为 `微观订单流 DOM 250ms 特征跟踪`；
   - 包含独立标题栏、复制链接按钮、状态徽章（`只标注 · 不进决策`）、刷新按钮与独立收起/展开控制按钮；
   - 内部包含统计维度切换下拉框（每日/每周）、DOM 槽位收益主表格、特征分桶表以及当天/次日判定力日级检验表格。
2. **交互与状态控制解耦**：
   - 新增 `applyDomFeatureVisibility()` 与 `toggleDomFeatureCard()`，使用独立的 `localStorage('bbt_dom_feature_open')` 进行折叠状态持久化记忆；
   - 移除 `loadAdamResearchReports` 与 `toggleAdamResearchCard` 中对 `loadAdamDomFeatureStats()` 的隐式耦合调用，实现 Adam 报告与 DOM 数据接口加载完全解耦；
   - 在 `DOMContentLoaded` 中统一初始化 `applyDomFeatureVisibility()` 与按需加载。

## 3. 验证方案
1. 检查页面源码，确认 `#domFeatureCard` 与 `#adamResearchCard` 结构同级独立。
2. 访问 `http://127.0.0.1:5005/bbt_signals_large_timeframe` 验证页面正常渲染，两张卡片各自独立折叠/展开。
3. 归档文档至 `system_modules/94_2026-09-18_DOM_250ms_Feature_Tracking_Card_Decoupling/` 并更新 `bbt_trading_modules.html`。
