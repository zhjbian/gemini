# 验收报告 (Walkthrough)

**模块编号**: 43 · **归档目录**: `43_2026-09-11_Close_Fill_Price_Settlement_Fix` · **日期**: 2026-09-11
**核心模块名称**: 平仓成交价结算修正 —— 以券商实际成交净价结算 PnL

## 1. 交付

| 层 | 文件 | 变更 |
| --- | --- | --- |
| 管理器 | `PyTools/option_seller/option_seller_manager.py` | 新增 `_net_cash_flow_from_order()`（按 `legId` 关联 `orderLegCollection` 的买卖方向）与 `resolve_close_fill_price()`；`close_trade()` 增参 `close_limit_price`，`is_broker_filled` 时以**实际成交净价**结算 PnL，并把委托价写入 `close_limit_price` |
| 模型 | `bbt_data_web/models.py` | `OptionSellerTrade` 新增 `close_limit_price`（委托价留档） |
| Schema | MySQL `order_flow_option_seller_trades` | `ADD COLUMN close_limit_price DECIMAL(10,4) NULL AFTER close_price` |
| 数据访问 | `bbt_data_web/db_query_module/db_query_option_seller.py` | `option_seller_trade_close(..., close_limit_price=None)` |
| 数据回补 | 2 行历史修正 | id231 close 0.15→**0.14**（PnL 0→**1.00**，limit=0.15）；id233 0.17→**0.16**（0→**1.00**，limit=0.17）；id230/232 补 limit=0.08/0.10 |

## 2. 验收结果

**解析逻辑自测（对当日 4 张真实平仓单，框架 Python 3.11）**：

```
id230 #1007893568184 FILLED 净现金流=-0.08 → 0.08 ✓
id231 #1007893569490 FILLED 净现金流=-0.14 → 0.14 ✓
id232 #1007894618071 FILLED 净现金流=-0.10 → 0.10 ✓
id233 #1007895948185 FILLED 净现金流=-0.16 → 0.16 ✓   → PASS
```

**数据核对**：

- 9/11 DB 汇总：4 笔 LIVE 合计 **$16.00**（原 $14.00）→ 与 TOS `P/L Day $16.00` **完全一致**；
- `calendar_pnl` 接口：9/11 = `{pnl: 16.0, live: {pnl: 16.0, trades: 4, win: 4}}`；
- 9 月月度：**LIVE 103.00 / DRY 347.00 / All 450.00**（修正前 101.00 / 347.00 / 448.00）；
- 逐笔表已带 `close_limit_price`：id230 0.08 / id231 0.15 / id232 0.10 / id233 0.17。

## 3. 说明与边界

- **仅影响记账/统计**（`realized_pnl` → 日历、月度、统计面板）；真实持仓与风控以券商为准（`_reconcile_broker_positions` 独立对账）。
- `realized_pnl` 仍为**毛额**，不含佣金/费用（TOS 的 `P/L Day` 本次亦为毛额口径）。若需净额，可在结算时另记 `commission`（本次未做，属可选项）。
- 状态标签（如 `CLOSED_BREAKEVEN_L1_H1`）表达的是**触发的规则**，不因成交价价格改善而改动（该笔实际以更优价成交 → 实得 +$1.00）。

## 4. 回滚

```sql
UPDATE order_flow_option_seller_trades SET close_price=0.1500, realized_pnl=0.00, close_limit_price=NULL WHERE id=231;
UPDATE order_flow_option_seller_trades SET close_price=0.1700, realized_pnl=0.00, close_limit_price=NULL WHERE id=233;
UPDATE order_flow_option_seller_trades SET close_limit_price=NULL WHERE id IN (230,232);
ALTER TABLE order_flow_option_seller_trades DROP COLUMN close_limit_price;
```
代码侧：移除 `resolve_close_fill_price()` 调用（回到用委托价结算），并删除 `_net_cash_flow_from_order()` 与 `close_limit_price` 参数。
