# 实施计划 (Implementation Plan)

**模块编号**: 43 · **归档目录**: `43_2026-09-11_Close_Fill_Price_Settlement_Fix` · **日期**: 2026-09-11
**核心模块名称**: 平仓成交价结算修正 —— 以券商实际成交净价结算 PnL (Close Fill-Price Settlement Fix)
**涉及技术栈**: Python / OptionSellerManager 平仓结算路径 / Schwab Orders API 成交腿解析 / MySQL Schema 增量列 / Flask calendar_pnl

## 1. 问题（用户提出：TOS PnL 16 vs 系统 14）

2026-09-11 SPY 11SEP26 759/761 Put 价差共 4 笔（LIVE），**券商实际已实现 $16.00**（与 TOS `P/L Day` 一致），系统仅记 **$14.00**。

## 2. 取证（券商原始成交，`get_working_orders('*')`）

| 轮次 | 开仓成交 | 净收 | 平仓成交 | 净付 | 实际 PnL | 系统原记录 |
| --- | --- | --- | --- | --- | --- | --- |
| A-1 `#…459383` | 0.33 / 0.18 | 0.15 | `#…569490` 0.30 / 0.16 | **0.14** | **+1.00** | close 0.15 → 0.00 ✗ |
| A-2 `#…459376` | 0.34 / 0.19 | 0.15 | `#…568184` 0.20 / 0.12 | 0.08 | +7.00 | +7.00 ✓ |
| B-1 `#…618066` | 0.35 / 0.18 | 0.17 | `#…618071` 0.11 / 0.21 | 0.10 | +7.00 | +7.00 ✓ |
| B-2 `#…618073` | 0.19 / 0.36 | 0.17 | `#…948185` 0.30 / 0.14 | **0.16** | **+1.00** | close 0.17 → 0.00 ✗ |

**根因**：平仓路径传入的是**委托限价**（`target_profit_price` / `stop_loss_price`），当券商发生 **1 美分价格改善**时，系统仍按限价记账 → 每笔低估 $1.00。

## 3. 方案

1. `OptionSellerManager.close_trade(..., is_broker_filled=True)` 时，按 `_close_broker_order_id` → `tp_broker_order_id` → `sl_broker_order_id` 顺序取回券商订单，**解析实际成交腿**得到净支付价，用于 `realized_pnl` 结算；取不到时回退委托价。
2. 成交腿解析：`executionLegs` **不含 instruction**（仅 `legId`+`price`），须按 `legId` 到 `orderLegCollection` 查买卖方向；净现金流 = ΣSELL − ΣBUY，平仓净支付 = −净现金流。
3. 新增列 `order_flow_option_seller_trades.close_limit_price`：留档**委托价**，`close_price` 语义明确为**实际成交净价**，便于统计滑点/价格改善。
4. 历史回补本次 2 笔，使系统与 TOS 一致。

## 4. 验收标准

| # | 项 | 判定 |
| --- | --- | --- |
| 1 | 解析逻辑对真实订单正确 | 4 张平仓单解析出 0.08/0.14/0.10/0.16 |
| 2 | 9/11 汇总 == TOS | 系统合计 $16.00 |
| 3 | 口径留档 | `close_limit_price` 记录委托价；id231=0.15、id233=0.17 |
| 4 | 月度与日历一致 | 9 月 LIVE 由 101 → **103.00**，9/11 单元格 = 16.00 |
| 5 | 可回滚 | 2 行原值已记录，可用 SQL 还原 |
