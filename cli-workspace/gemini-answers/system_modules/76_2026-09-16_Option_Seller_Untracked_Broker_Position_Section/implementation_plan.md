# 期权卖家系统「券商未跟踪持仓」独立成区展示（价差配对 + 单腿列出） 实施计划 (Plan)

## 1. 需求（用户指令）

> 券商有但系统未跟踪时，把券商的仓位显示在
> `http://127.0.0.1:5005/bbt_option_seller` → 活跃持仓监控 (Active Spread Monitor) 下面一个新的 section 里，
> 尝试匹配成 spread，单腿仓位也要列出。

背景：2026-09-16 连续发生两起「券商有、系统无」的真实敞口
（① 09:25 作废后延迟成交的 753/751 孤儿价差；② 11:35 平仓单被反向执行为开仓建出的 754/752 反向价差）。
此前这些仓位只在「券商端真实持仓 / 保护单对账」卡片里以**两行文字腿**的形式出现
（`SPY 260916P00753000 ×-1 …`），既看不出它们其实组成了一个价差，也没有成本/市价/浮盈，
操作员必须自己去 TOS 对照——在 11:38 那次事故中，这直接导致判断滞后。

## 2. 方案设计

### 2.1 后端：把未跟踪腿配对成价差（与恐慌平仓共用同一实现）

- `_broker_symbol_map(positions)`：券商期权持仓按 OSI 符号合并，并富化展示字段
  （`avg_price` / `market_value` / `mark` / `pnl` / `put_call` / `strike` / `expiration` / `multiplier`）。
  - 标记价由市值反推：`mark = |marketValue| / (|quantity| × multiplier)`；
  - 浮盈按 `(mark − avgPrice) × 带符号数量 × multiplier`（实证：反向价差 long 754P@0.85/mark 0.685、
    short 752P@0.47/mark 0.375 ⇒ −16.5 + 9.5 = **−$7.00**，与 TOS 完全一致）。
- `_leg_excess(broker_qty, expected_qty)`：统一的「未跟踪部分」口径
  （期望 0 → 全量；同向更多 → 只算多出；同向更少 → 0，属「系统有但券商缺」；方向相反 → 整笔）。
- `_uncovered_legs(broker_by_sym, expected)`：券商侧未被系统期望覆盖的腿。
- `_pair_untracked_legs(legs)`：按 **同一合约族**（root+YYMMDD+C/P）分组，
  组内以**最近行权价贪心配对**多腿与空腿，产出：
  - `spreads`：`spread_type` / `spread_label` / `short_*`（实际持空的腿）/ `long_*` / `expiration` /
    `quantity` / `net_mark` / `net_avg` / `pnl` / `market_value` / `reason` / `matched_trade_id` / 双腿明细；
  - `singles`：配不上的**单腿**（必须列出）。
  数量守恒：空 2 张 / 多 1 张 ⇒ 1 组价差 + 1 张剩余空腿。
- `_reconcile_broker_positions()` 结果新增 `untracked_spreads` / `untracked_legs`
  （`unknown_positions` 保留，附带 `avg_price` / `mark` / `market_value` / `pnl` 等展示字段）。
- `flat_uncovered_broker_positions()`（恐慌平仓）重构为复用 `_pair_untracked_legs` +
  `_submit_flat_pair(spread)` —— **页面展示与强制平仓共用同一套配对结果**，避免两处逻辑漂移。

### 2.2 前端：活跃持仓监控下方的独立 section

新增 `<section id="untrackedBrokerSection">`「券商未跟踪持仓 (Untracked Broker Positions)」，
位于「活跃持仓监控 (Active Spread Monitor)」之下；无未跟踪仓位时**整区隐藏**。内容：

1. 两个计数徽章：`N 组价差` / `M 单腿`，右上角标注
   `来源: Schwab get_account(POSITIONS) · 仅观测不处置`；
2. **配对价差卡片**：类型（看跌/看涨价差）、到期、×数量、成因标签
   （`疑似平仓单被反向执行为开仓` / `疑似作废后延迟成交` / `未跟踪`）、
   双腿表格（方向 空/多、行权价、合约、开仓均价、标记价、浮盈）、
   底部汇总（组合净市价、组合开仓净价、浮动盈亏、市值、关联流水 #N）；
3. **未配对单腿表格**：合约、说明、方向 多/空、数量、开仓均价、标记价、市值、浮盈、成因；
4. 底部提示：这些仓位不在系统跟踪范围内（无止盈/止损、不会被自动平仓），
   可用「恐慌平仓」强制清算或券商端人工处置。

浅色主题（Rule 12）：白底卡片 + 浅红/浅黄告警边框，红/绿仅用于方向与盈亏着色。

## 3. 涉及文件

| 文件 | 变更 |
| :--- | :--- |
| `PyTools/option_seller/option_seller_manager.py` | `_broker_symbol_map` / `_uncovered_legs` / `_leg_excess` / `_pair_untracked_legs` / OSI 解析工具（`_osi_strike` / `_osi_put_call` / `_osi_expiration` / `_osi_family`）；对账结果新增 `untracked_spreads` / `untracked_legs`；`flat_uncovered_broker_positions` 与 `_submit_flat_pair` 重构为共用配对结果 |
| `bbt_data_web/templates/bbt_option_seller.html` | 新增 `untrackedBrokerSection` + `renderUntrackedBrokerPositions()`，在状态刷新流程中调用 |
| `PyTools/option_seller/test_orphan_position_reconcile.py` | 新增 5 条用例（配对、单腿、跨族不误配、数量守恒、payload 键恒在） |

## 4. 测试与验证策略

1. 单元测试：反向价差配成 1 组且 `net_mark=0.31 / net_avg=0.38 / pnl=−7.00 / market_value=31.00`
   （与 TOS 实测一致）；单腿落 `untracked_legs`；看涨价差 + 多余腿分列；数量守恒；
   空数据时 payload 仍含两个键。
2. 前端渲染：以 Node 桩 DOM 直接调用 `renderUntrackedBrokerPositions()`，
   校验徽章、双腿表格、汇总数字、成因标签与「空数据隐藏」行为。
3. 实盘只读验证：`GET /api/option_seller/status` 返回
   `broker_reconcile.untracked_spreads / untracked_legs`。
4. 全量回归期权卖家测试套件，确认 `purge`/平仓/租约等相关用例零回归。

## 5. 边界

- 本区**只展示**：不自动平仓、不自动认领跟踪（遵守「仅观测不处置」）。
- 单腿仓位不提供单腿下单通道，仍需券商端人工处置；配对结果同时供「恐慌平仓」使用。
