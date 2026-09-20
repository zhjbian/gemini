# 期权卖家系统「一键全平」结果可解释化（0 closed 必须自证原因） 实施计划 (Plan)

## 1. 问题（用户报障）

> 今天在 TOS 有仓位、系统没有仓位的时候，点击「一键全平」提示 `0 closed`，为什么没有找到？

复盘结论（券商订单 + 生产日志逐条核对）：

| 时刻 (PT) | 事实 |
| :--- | :--- |
| 11:35:24 / 11:35:25 | 两个进程各提交一次平仓单，正常平掉 #289 / #288，账户归零 |
| **11:35:26** | 第二个进程多提交的那张 NET_DEBIT 单在无持仓可平的情况下被 Schwab **反向执行为开仓** → 券商侧建出 long 1×754P / short 1×752P 反向价差（系统完全不跟踪） |
| **11:38:05 / 11:38:24** | 用户两次点击「一键全平」→ 日志 `Panic close executed: 0 positions closed`（`option_seller_manager.py:2801`，**替换前的旧实现**） |
| 11:39:23 / 11:39:33 | 人工在券商端分腿平掉该反向价差 |

`0 closed` 的直接原因：**旧实现只遍历内存中的 `self.active_trades`**；
当时系统已无在管交易（#288/#289 都已 CLOSED），而反向价差从未被系统跟踪 ⇒
那份名单为空 ⇒ 按钮**根本没有去读券商持仓**，一张单也没发。

该行为已在当日后续交付中修复（见归档 75：`flat_uncovered_broker_positions()` 覆盖券商侧未跟踪敞口）。
本次交付解决**剩余的可观测性问题**：`0 positions closed` 本身无法区分
「本来就没有仓位」与「有仓位但没找到」—— 正是这两种情况的混淆，让操作员在 11:38 无法判断按钮是否失效。

## 2. 方案设计

### 2.1 记录并回传「恐慌平仓报告」

- `flat_uncovered_broker_positions()` 每次执行都写入 `self.last_untracked_report`：
  `found`（找到多少条未跟踪腿）/ `spreads`（配成多少组价差）/ `closed`（实际平掉多少组）/
  `leftover_legs`（配不成价差、需人工处置的单腿数）/ `query_failed`（券商持仓是否查询失败）。
- `panic_close_all()` 汇总为 `self.last_panic_report = {'tracked_closed': N, 'untracked': {...}}`，
  并把同一份明细写进 WARNING 日志（事后审计可查"当时找到了什么"）。
- 新增 `panic_report_detail()` 生成可读明细字符串（供 API 弹窗与日志复用，避免两处格式漂移）。

### 2.2 明确回答"为什么是 0"

`panic_report_detail()` 的判定顺序：

1. `query_failed=True` → 追加「⚠ 券商持仓查询失败，未盲目下单」；
2. 否则 `found == 0` → 追加「券商侧当前无未跟踪敞口」（即"确实没有仓位可平"）；
3. `found > 0` → 显示「券商未跟踪持仓 N 腿 / M 组 → 平仓 K 组」；
4. `leftover_legs > 0` → 追加「剩余 L 条单腿需人工在券商端处置」。

### 2.3 接口与前端

- `POST /api/option_seller/panic_close` 响应新增 `report` 字段，`message` 追加上述明细；
- 前端「一键全平」确认框改为明示**按钮现在会做什么**（① 平在管持仓 ② 清算券商未跟踪敞口），
  弹窗继续使用后端 `message`（已含明细）。

## 3. 涉及文件

| 文件 | 变更 |
| :--- | :--- |
| `PyTools/option_seller/option_seller_manager.py` | `last_untracked_report` / `last_panic_report` / `panic_report_detail()`；`panic_close_all` 明细日志 |
| `bbt_data_web/data_app/bbt_option_seller.py` | panic_close 响应新增 `report` + message 明细 |
| `bbt_data_web/templates/bbt_option_seller.html` | 「一键全平」确认框明确清算范围 |
| `PyTools/option_seller/test_monitor_single_instance_lease.py` | 新增 4 条用例（无仓位 / 有未跟踪价差 / 查询失败 / 只剩单腿） |

## 4. 测试与验证策略

1. 单测断言四种情形下 `panic_report_detail()` 的措辞与计数（含"必须出现明确原因"）。
2. 全量回归期权卖家套件。
3. 实盘只读一致性：账户无持仓时，明细为「券商侧当前无未跟踪敞口」；有未跟踪价差时明细必须给出腿数/组数/平仓数。

## 5. 边界

- 本次只改**可解释性**与文案，不改变下单语义；是否下单仍由「一键全平」的确认框与租约仲裁决定。
- 单腿仓位仍不提供单腿下单通道（需券商端人工处置），但会在明细与页面新 section 中明确列出。
