# 期权卖家系统「作废后延迟成交」孤儿仓位防护与券商持仓对账数量化 实施计划 (Plan)

## 1. 事故背景 (2026-09-16 实盘)

页面 `http://127.0.0.1:5005/bbt_option_seller` → 「活跃持仓监控 (Active Spread Monitor)」的
「券商端真实持仓 / 保护单对账」卡片报出漂移：

```text
对账 ⚠ 漂移   券商期权持仓: 2   系统有但券商缺: 0   券商有但系统未跟踪: 2
券商持有但系统未跟踪：
  SPY 260916P00753000 ×-1 (09/16/2026 $753 Put)
  SPY 260916P00751000 ×1  (09/16/2026 $751 Put)
```

逐笔还原券商订单后，事故链完全确定（时间均为 PT，标的 SPY 2026-09-16 到期 0DTE 价差 753/751）：

| 时刻 | 事件 | 券商事实 |
| :--- | :--- | :--- |
| 07:58:43 | tranche 1（trade **#282**）下 entry 单 `1007944741077`（NET_CREDIT 0.21，DAY 单） | 下单瞬间状态 WORKING（限价未到） |
| 07:58:45 | tranche 2（trade **#283**）下 entry 单 `1007944741092` | 1 秒内成交 |
| 08:09:24 | 操作员平掉 #283（平仓单 `1007945300793` 成交 1 组） | 该合约组合归零（**#282 的挂单仍在途**） |
| 08:50:46 | 操作员对 #282 下平仓指令 | 持仓校验**正确地**报「券商侧无此持仓」⇒ 系统标记 `VOID_NO_POSITION` 并移出监控；**但从未撤销 #282 那张仍在途的 entry 挂单** |
| 09:25:16 | 该 DAY 挂单被动成交（`closeTime=16:25:16Z`） | 券商建出 1 组真实价差：系统不跟踪、无止盈、无止损 |

即：**作废（VOID）与「在途挂单延迟成交」之间存在竞态** —— 系统放弃了交易，却没有放弃那张单。

## 2. 根因分析（三个独立缺陷）

1. **作废不撤单（主因）**
   `_void_phantom_trade()` 只做「标记 VOID + 移出内存表」，从不清理该交易在券商侧仍活跃的
   entry 挂单。只要挂单是 DAY 单且限价未到，它可以在作废后任意时刻成交，建出无人管理的裸价差。
2. **「查询失败」与「确认无持仓」不可区分（放大器）**
   `BBTOS.get_positions()` 在账户哈希缺失 / 非 200 / 异常时统一返回 `[]`。
   风控侧把 `[]` 读成「券商确认没有持仓」，于是限流或网络抖动会直接触发误作废；
   `_broker_holds_position()` docstring 里写的 `None -> 按存在处理` 防线实际上是**死代码**。
3. **对账只比符号、不比数量（掩盖器）**
   `_reconcile_broker_positions()` 用「符号是否出现在在管交易腿集合里」判断是否未跟踪。
   实证：10:08 操作员在同 strikes 新开两笔挂单中（#284/#285，entry 仍 WORKING、券商侧尚无持仓）
   后，孤儿仓位的两条腿符号与这两个交易的腿**完全相同** ⇒ 纯符号比对把孤儿仓位判成「已跟踪」，
   页面由「⚠ 漂移」变「✓ 一致」，真实敞口被静默掩盖。

此外，对账在页面每 ~4 秒轮询一次 `status` 时都会执行，同一漂移每轮刷一条 WARNING
（生产日志已累积 23 万行），真实告警被淹没。

## 3. 修复方案

### 3.1 核心不变量：作废 = 无持仓 **AND** 无在途开仓单

- 新增 `_live_entry_orders_for_trade(trade)`：列出该交易在券商侧**仍活跃的开仓挂单**。
  匹配口径「宁可漏杀，绝不误杀别的交易」：
  1. 交易自己的 `order_id`（精确匹配）；
  2. 券商替换过 order id 时按同腿开仓单重链接，但**排除**其它在管交易的 `order_id` / `client_order_id`
     （避免撤掉兄弟批次 tranche 2 的挂单）。
- 新增 `_cancel_live_entry_orders(trade)`：逐单调用 `cancel_order` 并**轮询确认终态**
  （`WORKING -> PENDING_CANCEL -> CANCELED`），最后复检活跃挂单列表。
  新增类常量 `ENTRY_CANCEL_CONFIRM_MAX_CHECKS=3` / `ENTRY_CANCEL_CONFIRM_SLEEP_SEC=1.0`
  （最长 ≈2.9s，仍在一轮 8s 监控周期内）。
- `_void_phantom_trade()` 改为三步：
  1. 撤单；撤不干净 ⇒ **拒绝作废**，交易留在在管列表（`status` 复位 `OPEN`）继续被监控；
  2. 撤单期间成交（或复检发现持仓已出现）⇒ **放弃作废、转为在管**，新增
     `_adopt_late_filled_trade()` 刷新订单状态并补挂止盈/止损；
  3. 两个条件都成立才写 `VOID_NO_POSITION`，并在日志中留档被清理的挂单 id。
- `_maybe_void_unfilled_trade()`（entry 终态 0 成交的作废路径）追加同一道「无在途开仓单」保险。

### 3.2 查询失败必须可区分

- `BBTOS.get_positions(only_option_positions=True, strict=False)` 新增 `strict` 形参：
  `strict=True` 时失败返回 `None`（默认仍返回 `[]`，完全向后兼容）。
- `_broker_holds_position()` 改用 `strict=True`：只有拿到**确凿的空持仓列表**才返回 `False`。
- `_trade_has_broker_position()`（作废双保险）在查询失败 / 异常时**保守返回 `True`**（阻止误作废）。

### 3.3 对账数量化 + 漂移归因 + 告警去重

- 券商持仓按 OSI 符号**合并数量**；系统侧按 `_trade_expected_on_broker(trade)` 计算**期望净敞口**：
  - `entry_order_status ∈ {FILLED, FILLED_AND_PENDING}`、`entry_filled_qty ≥ quantity`、
    `status == CLOSING`、或历史老行（entry 字段缺失）⇒ 该交易**应当**在券商侧存在；
  - entry 仍为 `WORKING` / `PENDING_ACTIVATION` ⇒ 尚无持仓，不计入期望。
- `unknown_positions` 改为逐符号报告**超出期望的净数量**（`quantity`=超出量，
  另带 `broker_quantity` / `expected_quantity`），因此「同 strikes 的另一笔未成交挂单」不再掩盖孤儿仓位；
  **数量不足**只计入「系统有但券商缺」（避免把差额误报成方向相反的多头/空头），
  方向与期望相反的持仓整笔计为未跟踪敞口。
- `known_but_missing_on_broker` 改为**数量不足**判定（附 `expected_qty` / `short_qty` / `long_qty`）。
- 漂移归因：新增 `_ledger_trades_matching_symbols()`，把未跟踪持仓关联回**当日**已作废
  （`VOID_NO_POSITION` / `CLOSED_VOID_*`）的交易，标记 `reason=LATE_FILLED_ENTRY_SUSPECT`
  并给出 `matched_trade_id`。
- 查询失败新增 `query_failed=True` 字段，且**不产出任何漂移结论**。
- 告警按 `drift_key` 指纹去重：同一漂移只在首次出现（或内容变化）时告警一次，
  其后静默计数（`log_suppressed`），漂移清零时复位并记录一次「漂移已消除」。

### 3.4 前端呈现（浅色主题，Rule 12）

`bbt_option_seller.html` → `renderBrokerReconcile()`：
- 新增「查询失败」状态（灰、不再误显示为漂移）；
- 未跟踪持仓逐行标注「疑似作废后延迟成交 · 关联流水 #N」；
- 出现孤儿仓位时追加醒目提示块，说明其「无跟踪 / 无止盈 / 无止损」的性质与人工处置要求；
- 显示被抑制的重复告警次数。

## 4. 涉及文件

| 文件 | 变更 |
| :--- | :--- |
| `PyTools/option_seller/option_seller_manager.py` | 作废前置撤单、延迟成交转在管、strict 持仓校验、对账数量化/归因/去重 |
| `PyTools/tos_api/bb_tos.py` | `get_positions(strict=...)` 区分「查询失败」与「确认为空」 |
| `bbt_data_web/templates/bbt_option_seller.html` | 对账卡片新增查询失败态、孤儿仓位归因与处置提示、抑制计数 |
| `PyTools/option_seller/test_orphan_position_reconcile.py` | 新增 17 条回归用例 |

## 5. 测试与验证策略

1. 新增单元测试（`test_orphan_position_reconcile.py`，继承 `test_isolation.GuardedTestCase`）：
   作废前撤单顺序、撤不掉拒绝作废、撤单期间成交转在管、复检出现持仓拒绝作废、
   `strict` 查询失败语义、作废双保险保守性、对账归因、数量化（超额/不足）、告警去重、
   `_trade_expected_on_broker` 闸门。
2. 全量回归期权卖家测试套件（570 项），确保既有 30 项 `test_live_resting_limit_order` 等不受影响。
3. 实盘只读验证：调用 `GET /api/option_seller/status` 检查 `broker_reconcile` 是否精确报出
   孤儿仓位（超额 1 组）并关联到 trade #282；确认日志不再每 4s 重复告警。

## 6. 不予自动处置的边界（遵守「仅观测不处置」）

对账仍**只观测**：不自动平仓、不自动重建跟踪。孤儿仓位的处置（平仓 / 重建跟踪 / 到期自然了结）
属于资金操作，必须由操作员决定；本次修复保证的是**不再产生新的孤儿仓位**且**存量孤儿仓位一眼可见、可归因**。
