# 实施计划：Option Seller 实盘预埋限价止盈 (Resting Limit Order) 与本地守护止损系统

## 概述
为 Option Seller 自动化交易引擎构建“双轨分流执行架构”：
1. **Dry-Run 模式（模拟测试）**：完全与实盘隔离，保持现有的纯本地 10 秒生命周期风控守护线程（`_monitor_loop`），零成本、零污染、无 API 限流与报错风险。
2. **Live-Trading 模式（真实交易）**：开仓成交后，自动向 Schwab/TOS 提交 2 笔限价平仓买单（Limit Buy to Close，即 Tranche 1 40% 衰减与 Tranche 2 75% 衰减），单子直接挂入期权交易所 Order Book 享受最高撮合排队优先权与防断网能力；同时本地 10 秒守护线程持续监控挂单状态，一旦触发 2.2 倍硬止损或 12:30 PST 时间止损，先撤回券商端止盈挂单再执行市价斩仓。

---

## 核心设计与时序规范

### 1. 多腿价差挂单机制与撤单时序说明
1. 期权垂直价差（Vertical Spread）在 CBOE / Schwab API 中原生支持 `LIMIT` 类型的平仓买单（Net Debit Buy-to-Close），不支持直接预埋价差的市价止损（Stop Market Spread）。
2. 实盘开仓后，T1 和 T2 的限价平仓单在 ThinkorSwim (TOS) 客户端的 "Working Orders" 区域立即可见。
3. 当行情逆行触碰 2.2 倍止损或 12:30 PST 时，系统必须先执行 `cancel_order` 撤销挂单，等待撤单确认（释放被锁定的期权腿仓位）后，再执行止损平仓单，避免因仓位锁定导致重复下单拒绝。

---

## 技术实现清单

1. **`PyTools/tos_api/bb_tos.py`**：
   * 新增 `place_vertical_spread_limit_close`：提交限价平仓单并提取 `order_id`；
   * 新增 `get_order_status(order_id)`：查询订单执行状态（`WORKING`, `FILLED`, `CANCELED`, `REJECTED` 等）；
   * 新增 `cancel_order(order_id)`：撤销在途挂单。
2. **`PyTools/option_seller/option_seller_manager.py`**：
   * `_open_single_contract`：实盘开仓后自动预埋限价平仓单；
   * `close_trade`：增加 `is_broker_filled` 标识，避免重复平仓；止损时先撤销预埋挂单；
   * `_evaluate_active_positions`：优先轮询预埋单状态，若 `FILLED` 则结案；
   * `_reload_active_trades`：服务重启时恢复 `tp_broker_order_id`。
3. **`bbt_data_web/db_query_module/db_query_option_seller.py`**：
   * 新增 `option_seller_trade_update_evidence`。
4. **前端看板 (`bbt_option_seller.html`)**：
   * 持仓卡片与历史流水展示 TOS 预挂止盈单号与状态。
5. **单元测试 (`test_live_resting_limit_order.py`)**：
   * 4 项测试 100% 通过。
