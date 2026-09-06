# 期权卖方流水账本类型过滤器与 TradingView 筛选导出引擎 实施计划 (Implementation Plan)

## 背景与目标
在期权卖方交易平台（`http://127.0.0.1:5005/bbt_option_seller`）中，交易流水账本已记录包含自动 5m共振、条件单、极值耗竭、震荡边界、盘前大单以及交易员手动实盘单在内的多种不同类型交易。
为了提升交易复盘与策略分析效率，需要：
1. 在流水账本顶栏提供清爽、直观的【类型 Filter】选择器，支持实时按“全部”、“全部自动”、“5m共振”、“条件单”、“边界/耗竭”、“盘前大单”、“纯手动”快速筛选过滤表格流水，并动态统计显示笔数；
2. 强化【复制 TradingView 指标 (Copy TV Pine)】功能，使其严格且仅导出当前 Filter 过滤后展示的交易记录，在 TradingView 图表上实现按策略分类的精准复盘。

---

## 架构设计与改动范围

### 1. 前端交互与过滤渲染 (`bbt_data_web/templates/bbt_option_seller.html`)
- **顶栏控件增设**：在 `journalSectionTitle` 操作栏内增设浅色主题微型筛选控制条：
  - 包含图标、文字标签、原生 `<select id="journalTypeFilter">` 下拉框与高亮计数字段 `#journalFilterCount`；
  - 适配浅色模式规范（采用白底 `#ffffff`、淡蓝/浅灰描边 `#cbd5e1` 与高对比文字）。
- **分类识别算法**：新增 `getTradeCategory(trade)` 与 `isTradeMatchingFilter(trade, filterVal)`，基于 `trade_mode` 与 `entry_evidence` 内的 `trigger`、`debug_info.sub_scenario` 等元数据精准映射归类。
- **动态渲染流水线**：
  - 全局维护 `window.__currentRawTrades` 与 `window.__currentFilteredTrades`；
  - 过滤变更触发 `applyJournalFilterAndRender()`，同步刷新计数字段并交由 `renderHistoryTable()` 进行分组呈现；
  - 表格为空时针对筛选状态提示“当前类型筛选下暂无交易记录”。
- **TV 指标导出联动**：
  - `copyTradingViewPineScriptForCurrentDate` 提取 `window.__currentFilteredTrades` 中的 `id` 列表；
  - 以 POST JSON 发送 `{ date, trade_ids }`，并给予包含筛选名称和单数的明确 Toast 视觉反馈。

### 2. 后端路由与指标生成器 (`bbt_data_web/data_app/bbt_option_seller.py` & `PyTools/trading_view/tv_option_seller_trades.py`)
- **API 路由升级**：
  - `/api/option_seller/generate_tv_script` 支持 POST JSON 载荷解析 `trade_ids`；
  - 将过滤目标 ID 集合下发至指标生成器。
- **Pine Script 生成器改造**：
  - `build_option_seller_pine_script(date_str, trades_list=None, trade_ids=None)` 接受 `trade_ids` 过滤参数；
  - 数据库查询后基于 ID 过滤入参，确保 TradingView 生成脚本仅打包选中的交易。

---

## 验证与验收方案
1. **语法与类型检查**：使用 `py_compile` 校验后端与生成器 Python 源码。
2. **生成器过滤单元测试**：使用不同日期的真实交易 ID 进行全量与单/多单筛选比对，确保输出 Pine Script 代码仅含目标交易。
3. **接口端到端验证**：使用 curl / HTTP client 测试 POST `/api/option_seller/generate_tv_script` 载荷响应。
4. **前端交互与边界防护**：验证空筛选、切换类型、双批次合并单、历史日历点击及复制状态。
