# 期权卖家系统「作废后延迟成交」孤儿仓位防护与券商持仓对账数量化 验收报告 (Walkthrough)

## 1. 任务概述

页面「活跃持仓监控」的券商对账卡片报出「券商有但系统未跟踪: 2」（SPY 260916 753/751 Put 双腿）。
逐笔还原券商订单后确认：这是 **2026-09-16 08:50 的一次正确作废 + 09:25 的一次延迟成交**
共同造成的**孤儿仓位**——系统已放弃该交易，但那张仍挂在券商侧的 DAY entry 单在一个半小时后成交，
建出一个**系统不跟踪、无止盈、无止损**的真实价差。

本次交付：(1) 从机制上杜绝该竞态再次发生；(2) 使券商持仓对账具备**数量级精度与归因能力**；
(3) 修掉对账告警每 ~4s 刷屏的噪声问题。**不对存量孤儿仓位做任何自动资金处置**（遵守「仅观测不处置」）。

## 2. 竞态根因（复盘点）

| 环节 | 旧行为 | 结论 |
| :--- | :--- | :--- |
| 作废幽灵仓位 | 只写 `VOID_NO_POSITION` + 移出内存表 | ✗ 未撤销在途 entry 挂单 ⇒ 挂单可随时成交 |
| 持仓校验 | `get_positions()` 失败返回 `[]` | ✗ 「查询失败」被读成「确认无持仓」 |
| 对账判定 | 只比符号是否出现在在管交易腿集合 | ✗ 同 strikes 的未成交新挂单会掩盖孤儿仓位 |
| 告警 | 每次轮询都 WARNING | ✗ 日志 23 万行，真实告警被淹没 |

## 3. 修改文件与核心实现

| 文件 | 关键改动 |
| :--- | :--- |
| `PyTools/option_seller/option_seller_manager.py` | `_live_entry_orders_for_trade()`（新增）、`_cancel_live_entry_orders()`（新增）、`_void_phantom_trade()`（重写为三步闸门）、`_adopt_late_filled_trade()`（新增）、`_maybe_void_unfilled_trade()`（追加第三道保险）、`_broker_holds_position()`（strict）、`_trade_has_broker_position()`（失败保守 True）、`_reconcile_broker_positions()`（数量化 + 归因 + 去重）、`_ledger_trades_matching_symbols()`（新增）、`_trade_expected_on_broker()`（新增）、`_reset_reconcile_dedup()`（新增） |
| `PyTools/tos_api/bb_tos.py` | `get_positions(only_option_positions=True, strict=False)`：`strict=True` 失败返回 `None`，默认行为不变 |
| `bbt_data_web/templates/bbt_option_seller.html` | `renderBrokerReconcile()`：查询失败态、孤儿仓位归因标签与处置提示块、抑制计数徽章 |
| `PyTools/option_seller/test_orphan_position_reconcile.py` | 新增 17 条回归用例（含实盘同 strikes 挂单掩盖场景） |

### 3.1 作废三步闸门（核心不变量）

```text
作废(phantom) ==  券商确认无持仓
              AND 券商侧无该交易的在途开仓单
撤单未确认 / 撤单期间成交  ->  拒绝作废；交易留 OPEN 继续监控（成交后自动补挂 TP/SL）
```

- 撤单确认为**终态确认**（`CANCELED/CANCELLED/REJECTED/EXPIRED`），最长约 2.9s，仍在 8s 监控周期内。
- 撤单匹配排除其它在管交易的 `order_id` / `client_order_id` ⇒ 不会误撤兄弟批次（tranche 2）的挂单。

### 3.2 对账数量化（可直接覆盖实盘掩盖场景）

期望敞口只统计「应当已在券商侧存在」的交易（entry 已成交 / `CLOSING` / 历史老行），
未成交挂单交易的期望值为 0；未跟踪持仓 = 券商净数量 − 期望净数量。

## 4. 验证结果

### 4.1 新增回归测试（17 项全通过）

```bash
PYTHONPATH=PyTools:bbt_data_web /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  -m unittest test_orphan_position_reconcile
```

```text
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、10 个数据库写方法
................
----------------------------------------------------------------------
Ran 17 tests in 0.978s
OK
```

覆盖点：

| 用例 | 守护的不变量 |
| :--- | :--- |
| `test_void_phantom_trade_cancels_working_entry_order_first` | 作废前先撤在途 entry 单，确认终态后才写 VOID |
| `test_void_phantom_trade_without_live_order_still_voids` | 无在途挂单时**不发任何撤单请求**（零行为变更） |
| `test_void_refused_when_entry_order_cannot_be_cancelled` | 撤不干净 ⇒ 不作废，交易保持 OPEN 在管 |
| `test_void_refused_when_entry_fills_during_cancel` | 撤单期间成交 ⇒ 放弃作废 + 立即补挂 TP/SL |
| `test_void_refused_when_position_appears_after_cancel` | 第二道闸：复检出现持仓 ⇒ 不作废 |
| `test_broker_holds_position_returns_none_on_query_failure` | 查询失败 = 「无法确认」≠「无持仓」 |
| `test_trade_has_broker_position_conservative_on_query_failure` | 作废双保险在无法确认时保守为「有持仓」 |
| `test_get_positions_strict_returns_none_on_failure` | `strict` 语义 + 默认行为向后兼容 |
| `test_reconcile_flags_late_filled_orphan` | 未跟踪腿归因到当日已作废交易（#282） |
| `test_reconcile_flags_orphan_even_when_working_trade_shares_legs` | **关键**：同 strikes 未成交挂单不得掩盖孤儿仓位 |
| `test_reconcile_clean_when_filled_trade_matches_broker_exactly` | 修复不得引入误报 |
| `test_reconcile_reports_partial_excess` / `test_reconcile_reports_missing_when_quantity_short` | 超额按数量报出；**数量不足只报「系统有但券商缺」，不得混入「券商有但系统未跟踪」** |
| `test_reconcile_reports_direction_mismatch_as_untracked` | 券商持仓方向与系统期望相反 -> 整笔计为未跟踪敞口 |
| `test_reconcile_dedupes_repeated_identical_drift` | 同一漂移只告警一次 + 静默计数 |
| `test_reconcile_query_failure_is_not_treated_as_flat` | 查询失败不产出漂移结论 |
| `test_trade_expected_on_broker_gate` | 期望敞口闸门口径 |

### 4.2 全量回归（571 项）

```text
Ran 571 tests in 253.020s
FAILED (failures=1)
```

唯一失败项 `test_absorption_reversal_module.TestAnchors.test_gate_blocks_structurally_a_like_failures`
为**既有失败**（ES 吸收反转投票门槛的测试样本得分 5 < 断言 6），与本次改动无任何代码交集
（本次未触碰 `auto_mechanisms.py` / 判定引擎）。另一项既有失败
`test_live_resting_limit_order.test_batch_quotes_and_order_map_used` 已随本次交付修正：
该用例的 `entry_evidence` 未记录 `filled_at`，导致实现中「首次见到 FILLED 时捕获成交时刻」的
有界单次 `get_order_status` 调用触发断言；用例数据补齐 `filled_at` 后恢复其本意
（验证「批量报价 + 批量订单映射」优化路径）。

```text
Ran 30 tests in 4.915s   （test_live_resting_limit_order + test_orphan_position_reconcile）
OK
```

### 4.3 实盘只读验证（2026-09-16 10:17 PT）

```bash
curl -s http://127.0.0.1:5005/api/option_seller/status
```

```json
{"broker_option_positions": 2, "drift": true,
 "drift_key": "USPY   260916P00751000:1:LATE_FILLED_ENTRY_SUSPECT|USPY   260916P00753000:-1:LATE_FILLED_ENTRY_SUSPECT",
 "unknown_positions": [
   {"symbol": "SPY   260916P00753000", "quantity": -1, "broker_quantity": -3, "expected_quantity": -2,
    "matched_trade_id": 282, "matched_trade_status": "VOID_NO_POSITION", "reason": "LATE_FILLED_ENTRY_SUSPECT"},
   {"symbol": "SPY   260916P00751000", "quantity": 1, "broker_quantity": 3, "expected_quantity": 2,
    "matched_trade_id": 282, "matched_trade_status": "VOID_NO_POSITION", "reason": "LATE_FILLED_ENTRY_SUSPECT"}]}
```

语义说明（这正是修复生效的证据）：

- 券商实持 **3 组** 753/751 空头价差（`broker_quantity = -3 / +3`）；
- 系统在管 **2 组**（#284 / #285，10:08 开仓并于 10:12 成交，`expected_quantity = -2 / +2`）；
- 差额 **1 组** 被精确识别为 **#282（`VOID_NO_POSITION`）作废后延迟成交的孤儿仓位**；
- 若按修复前的纯符号比对，这 1 组会被 #284/#285 的腿符号掩盖（页面显示「✓ 一致」）——数量化对账杜绝了该假阴性。

日志侧同样验证：`grep RECONCILE` 显示同一漂移只在指纹变化时输出一次 ERROR（含孤儿仓位说明），
`log_suppressed` 计数递增，不再每 ~4s 刷屏。

### 4.4 页面渲染验证（headless Chrome DOM 快照）

以独立 `--user-data-dir=/tmp/os_headless_<pid>` 启动 headless Chrome 抓取
`http://127.0.0.1:5005/bbt_option_seller` 的渲染后 DOM，确认对账卡片实际输出：

```html
<span class="tag tag-red">对账 ⚠ 漂移</span>
<span class="tag tag-blue">券商期权持仓: <strong>2</strong></span>
<span class="tag tag-gray">系统有但券商缺: <strong>0</strong></span>
<span class="tag tag-red">券商有但系统未跟踪: <strong>2</strong></span>
<span class="tag tag-gray">重复告警已抑制: <strong>31</strong></span>
券商持有但系统未跟踪：
  SPY 260916P00753000 ×-1 … <span class="tag tag-red">疑似作废后延迟成交 · 关联流水 #282 (VOID_NO_POSITION)</span>
  SPY 260916P00751000 ×1  … <span class="tag tag-red">疑似作废后延迟成交 · 关联流水 #282 (VOID_NO_POSITION)</span>
孤儿仓位（无止盈/无止损）：… 按「仅观测不处置」原则，系统不会自动平仓或自动重建跟踪；请在券商端人工核对后手动平仓。
```

（headless 进程在抓取完成后由 `kill <pid>` 精确终止，profile 目录已清理，未影响用户浏览器会话。）

## 5. 存量孤儿仓位的处置（人工决策，未自动执行）

截至验证时刻，券商账户比系统多持有 **1 组** SPY 2026-09-16 753/751 Bull Put（净收入 $21，最大风险 $179），
**无预埋止盈、无保护止损**，且当日到期。三条可选路径（均属资金操作，须由操作员决定）：

1. **立即平掉**（买入 753P + 卖出 751P，当前组合 mark ≈ 0.23 ⇒ 约 -$2 兑现离场，恢复到 08:50 的「清仓」意图）；
2. **重建跟踪**（在流水账本补建一笔 OPEN 交易并补挂止盈/止损，使其纳入本地风控，但与其 08:50 的平仓意图相反）；
3. **持有到期**（SPY 现价显著高于 753，大概率作废并保留全部 $21 权利金，但存在盘中跌破 753 的尾部风险）。

另需注意：10:08 新开的 #284 / #285 使该 strikes 的组合敞口达到 3 组（含孤儿仓位），
合计最大风险 3 × $179 = $537；#285 的预埋止盈单被券商以「同合约重复挂单」取消（`tp_order_status=CANCELED`），
仅由本地监控线程按退出规则管理（#284 的止盈单 `1007949546139` 正常 WORKING）。

### 5.1 事件收尾（2026-09-16 17:14 PT 复查）

- #284 于 11:04:44 触发预埋止盈成交（0.14，+$9）；#285 于 11:07:25 手动平仓（0.12，+$11）；
  该 strikes 的持仓随当日 0DTE 到期结算归零。
- 复查 `GET /api/option_seller/status`：`drift=false`、`broker_option_positions=0`
  —— **存量的 1 组孤儿仓位已随到期日结束而消除**，无需再人工处置。
- 修复期间（10:17–11:04）「券商 3 组 vs 系统在管 2 组」的敞口差额持续以
  `LATE_FILLED_ENTRY_SUSPECT` 形式可见（`log_suppressed` 一度累计 720 次），
  杜绝了「页面显示一致、实际多一组裸敞口」的假阴性。

## 6. 交付物清单

- 生产代码：`option_seller_manager.py`、`bb_tos.py`、`bbt_option_seller.html`
- 测试：`test_orphan_position_reconcile.py`（新增 17 项）、`test_live_resting_limit_order.py`（用例数据补齐）
- 归档：`74_2026-09-16_Option_Seller_Orphan_Position_Late_Fill_Guard/`
