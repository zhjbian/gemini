# 期权卖家系统「一键全平」结果可解释化（0 closed 必须自证原因） 验收报告 (Walkthrough)

## 1. 任务概述

交易员报障：TOS 有仓位、系统无仓位时点击「一键全平」，弹窗只提示
`Emergency panic close executed: 0 positions closed.`，无法判断"按钮没找到仓位"还是"确实没有仓位"。

## 2. 复盘：11:38 那两次点击为什么是 0

生产日志给出确切证据（`grep "Panic close" bbt_option_seller.log`）：

```text
2026-09-16 11:38:24,561 WARNING: Panic close executed: 0 positions closed. [in option_seller_manager.py:2801]
2026-09-16 11:38:05,528 WARNING: Panic close executed: 0 positions closed. [in option_seller_manager.py:2801]
```

- 行号 `:2801` 属**替换前的旧实现**：`panic_close_all()` 只遍历内存 `self.active_trades`；
- 当时系统无在管交易（#288/#289 已于 11:35:24/25 `CLOSED_STOP_LOSS`），
  而券商侧的反向价差（long 1×754P / short 1×752P，`1007952049235` 于 11:35:26 反向成交建出）
  **从未被系统跟踪** ⇒ 名单为空 ⇒ 该路径**根本没有读取券商持仓** ⇒ 0；
- 该仓位由人工于 11:39:23/33 分腿平掉。

即：**"没找到"的原因是旧实现的数据源只有系统内存，而不是券商账户** —— 已在同日归档 75 中修复
（`flat_uncovered_broker_positions()`：读券商 POSITIONS → 算未覆盖敞口 → 配对 → 平仓）。

## 3. 本次交付：让 `0` 自己说清原因

| 位置 | 变更 |
| :--- | :--- |
| `option_seller_manager.py` | `flat_uncovered_broker_positions()` 每次写入 `last_untracked_report`（found / spreads / closed / leftover_legs / query_failed）；`panic_close_all()` 汇总 `last_panic_report` 并写同明细 WARNING；新增 `panic_report_detail()` 生成可读明细 |
| `data_app/bbt_option_seller.py` | `POST /api/option_seller/panic_close` 响应新增 `report` 字段，`message` 追加明细 |
| `bbt_option_seller.html` | 「一键全平」确认框明示清算范围（在管持仓 + 券商未跟踪敞口） |

明细判定顺序：查询失败 → 「⚠ 券商持仓查询失败，未盲目下单」；
无未跟踪腿 → 「券商侧当前无未跟踪敞口」；
有 → 「券商未跟踪持仓 N 腿 / M 组 → 平仓 K 组」+ 剩余单腿数。

现在的弹窗示例：

```text
Emergency panic close executed: 0 positions closed.（在管交易平仓 0 笔；券商未跟踪持仓 0 腿 / 0 组 → 平仓 0 组；券商侧当前无未跟踪敞口）
```

而 11:38 那种场景（零在管 + 券商反向价差）现在会是：

```text
Emergency panic close executed: 1 positions closed.（在管交易平仓 0 笔；券商未跟踪持仓 2 腿 / 1 组 → 平仓 1 组）
```

## 4. 验证

### 4.1 新增 4 条用例（全部通过）

```bash
PYTHONPATH=PyTools:bbt_data_web /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  -m unittest test_monitor_single_instance_lease test_orphan_position_reconcile test_live_resting_limit_order
```

```text
Ran 51 tests in 4.917s
OK
```

| 用例 | 断言 |
| :--- | :--- |
| `test_panic_report_explains_flat_account` | 空账户 → 明细含「券商侧当前无未跟踪敞口」「在管交易平仓 0 笔」，`found=0` |
| `test_panic_report_counts_untracked_positions` | 零在管 + 反向价差 → 明细含「券商未跟踪持仓 2 腿 / 1 组 → 平仓 1 组」，`tracked_closed=0` |
| `test_panic_report_flags_query_failure` | 持仓查询失败 → 明细含「⚠ 券商持仓查询失败，未盲目下单」，且**不发任何平仓单** |
| `test_panic_report_flags_leftover_single_legs` | 只有单腿 → 明细含「剩余 1 条单腿需人工在券商端处置」，且不发单腿订单 |

### 4.2 全量回归

期权卖家套件全量执行，仅剩既有、与本次改动无交集的
`test_absorption_reversal_module` 门槛样本失败；页面 200。

## 5. 使用与回滚

- **使用**：硬刷新页面（⌘⇧R）后点击「一键全平」，确认框会先说明清算范围，弹窗会给出明细；
  同时 `bbt_option_seller.log` 会留下同明细的 WARNING，便于事后审计"当时到底找到了什么"。
- **回滚**：删除 `panic_report_detail()` 与两个 report 字段（`★ 2026-09-16` 注释可定位），
  API 恢复单句 message，前端确认框恢复原文案。
