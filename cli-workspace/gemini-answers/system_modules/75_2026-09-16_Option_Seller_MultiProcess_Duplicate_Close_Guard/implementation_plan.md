# 期权卖家系统「平仓单被反向执行为开仓」多进程重复平仓事故 实施计划 (Plan)

## 1. 事故经过 (2026-09-16 11:35–11:39 PT, SPY 0DTE)

交易员报障：**11:38:58 卖家系统「活跃持仓监控」为空，但 TOS 里有仓位**。

逐笔还原券商订单 + 生产日志后，事故链完全确定：

| 时刻 (PT) | 事件 | 券商事实 |
| :--- | :--- | :--- |
| 11:15:16 / 11:15:18 | 系统开出 **#288 / #289** 两笔 754/752 Bull Put（各 1 张，net credit 0.17） | 成交：`1007950915849` / `1007950915854`（`SELL_TO_OPEN 754P` + `BUY_TO_OPEN 752P`） |
| 11:35 前后 | 止损触发。**两个进程各自跑了一遍退出判定**（见 §2） | — |
| 11:35:24 | 进程 A 为 #289 提交平仓单 `1007952049224`（NET_DEBIT 0.38） | FILLED — 正常平掉 #289 |
| 11:35:25 | 进程 A 为 #288 提交平仓单 `1007952049229`（NET_DEBIT 0.38） | FILLED — 正常平掉 #288（账户已归零） |
| 11:35:26 | **进程 B 又为 #288 提交平仓单 `1007952049235`**（NET_DEBIT 0.38） | 券商侧已无持仓 ⇒ Schwab 把它当**开仓**执行：**legs = `SELL_TO_OPEN 752P` + `BUY_TO_OPEN 754P`**，凭空建出**反向价差**（TOS: long 1×754P / short 1×752P） |
| 11:38:05 / 11:38:24 | 操作员两次点击「恐慌平仓」 | 日志：`Panic close executed: 0 positions closed` —— 旧实现只遍历 `self.active_trades`（当时为空），**一张单都不发** |
| 11:39:23 / 11:39:33 | 人工在券商端**分腿**平掉反向价差（`BUY_TO_CLOSE 752P` @0.35 / `SELL_TO_CLOSE 754P` @0.59） | 账户恢复干净 |

结果：系统账本中 #288/#289 均为 `CLOSED_STOP_LOSS`，在管列表为空 ⇒「活跃持仓监控」空白；
而券商侧（11:35:26–11:39:23 之间）握着一个**无跟踪、无止盈、无止损**的反向价差。

### 1.1 日志侧铁证：同一笔交易被两个**模块版本**同时平仓

```text
11:35:25,945 INFO: Live Schwab closing order submitted for trade #288 ... [in option_seller_manager.py:2224]  ← 旧版本代码
11:35:26,251 INFO: Live closing order 1007952049229 CONFIRMED FILLED for trade #288. [in ...:2232]
11:35:26,939 INFO: Live Schwab closing order submitted for trade #288 ... [in option_seller_manager.py:2665]  ← 当前版本代码
11:35:27,461 INFO: Live closing order 1007952049235 CONFIRMED FILLED for trade #288. [in ...:2674]
```

同一消息在当日日志里出现于 `:546 / :1206 / :1227 / :2224 / :2472 / :2665` 等多个行号 ⇒
**多个不同代码版本的进程在同一时刻管理同一批交易**。

## 2. 根因

1. **Flask debug reloader 双进程**（`bbt_data_app.py`）
   `start_monitor()` 写在 `if __name__ == '__main__':` 块内 —— Werkzeug reloader 的**父进程与子进程都会执行该块**，
   于是两个进程各跑一个风控监控线程。更关键的是：父进程自 9/15 起常驻，**永不重载代码**，
   长期以旧逻辑运行；每次改 `.py` 只重启子进程 ⇒ 新旧两版代码长期并存、共同管理同一批持仓。
2. **单飞锁只在进程内有效**
   `close_trade()` 用 `status='CLOSING'` 占位防止重复提交，但该状态在**各进程的内存表**里，
   两个进程互不可见 ⇒ 同一笔止损被提交两次平仓单。
3. **Schwab 会把"无持仓可平的 NET_DEBIT 单"反向执行为开仓**
   （2026-09 已有同类事故记录在 `_broker_holds_position()` 注释中）——
   持仓校验与订单执行之间存在 TOCTOU 窗口，第二个进程校验时仓位尚在、下单落市时已消失。
4. **紧急平仓不覆盖券商侧真实持仓**
   `panic_close_all()` 只遍历 `self.active_trades`；当系统零在管、券商却有孤儿仓位时，
   按钮返回 0 —— 恰恰是最需要它的场景失效。

## 3. 修复方案

### 3.1 跨进程单实例仲裁（核心）

- 新增租约表 `option_seller_monitor_lease`（单行，`DbQuery.ensure_option_seller_monitor_lease_table()` 幂等建表）：
  `leader_pid / leader_started_ms / heartbeat_ms / updated_at`。
- `DbQuery.option_seller_monitor_claim(pid, started_ms)`：**无条件抢占**（最新启动的进程胜出）；
  `DbQuery.option_seller_monitor_heartbeat(pid, started_ms)`：仅 leader 刷新心跳并回读租约行。
- `OptionSellerManager`：
  - `start_monitor()` 启动即抢占租约（新子进程立刻接管）；
  - `_monitor_loop()` 每轮先做 `_monitor_lease_check()`：**非 leader 不做任何券商写操作**
    （下单/平仓/撤单全停），每 `MONITOR_LEASE_POLL_SEC=10s` 复查；发现**更新启动**的 leader 即让位；
    leader 心跳超过 `MONITOR_LEASE_STALE_SEC=45s` 可被抢占（leader 崩溃自动接管）；
  - 租约查询异常时 **fail-open**（按 leader 运行并大声记录）—— 风控绝不因一次 DB 抖动全面停摆，
    且券商侧预埋止盈/止损单仍在。
  - `refresh_active_positions_now()`（UI 刷新路径）同样受约束：非 leader 强制 `apply_exit_rules=False`；
  - `panic_close_all()` 先确认/抢占租约，抢不到则**拒绝执行**（防重复下单）。
- `bbt_data_app.py`：仅在 reloader **子进程**（`werkzeug.serving.is_running_from_reloader()`）里
  `start_monitor()`，父进程不再承载业务线程。

### 3.2 紧急平仓覆盖券商侧未跟踪敞口

- 新增 `OptionSellerManager.flat_uncovered_broker_positions(reason)`：
  以「券商净敞口 − 系统期望敞口」（`_expected_broker_exposure()`，与对账同口径）定位未跟踪腿，
  按**实际持仓方向**配对（空腿 = `excess<0`、多腿 = `excess>0`）后复用既有已审计的
  `BBTOS.close_vertical_spread` 平仓；无法配对的单腿**不下单**，只大声留痕待人工处置。
- `panic_close_all()` = 在管交易标准平仓 + 上述未跟踪敞口清理。

### 3.3 反向成交指纹可归因

`_ledger_trades_matching_symbols()` 扩展为两类归因：
- `LATE_FILLED_ENTRY_SUSPECT`：命中当日**已作废**交易（作废后挂单延迟成交，09:25 事故）；
- `REVERSE_OF_CLOSED_TRADE`：命中当日**已平仓**交易、且券商腿方向与其持仓方向**相反**
  —— "平仓单被反向执行为开仓"的指纹（本次 11:35 事故）。
前端对账卡片按成因分别给出处置提示，并新增「监控实例 leader / 只读待命」状态徽章。

## 4. 涉及文件

| 文件 | 变更 |
| :--- | :--- |
| `bbt_data_web/bbt_data_app.py` | 仅 reloader 子进程启动监控线程 |
| `bbt_data_web/db_query_module/db_query_option_seller.py` | 租约表 DDL + claim / heartbeat |
| `PyTools/option_seller/option_seller_manager.py` | 租约仲裁、非 leader 只读化、紧急平仓覆盖未跟踪敞口、反向成交归因、`_expected_broker_exposure()` |
| `bbt_data_web/templates/bbt_option_seller.html` | 租约状态徽章 + 两类孤儿仓位成因提示 |
| `PyTools/option_seller/test_monitor_single_instance_lease.py` | 新增 11 条回归用例 |
| `PyTools/option_seller/test_isolation.py` | 测试进程不得写真实租约表（新增 3 个 DB 写方法拦截） |

## 5. 测试与验证

1. 新增 `test_monitor_single_instance_lease.py`：租约抢占/让位/陈旧接管/fail-open、
   UI 刷新降级只读、未跟踪敞口平仓方向与配对、已覆盖持仓不重复平仓、
   恐慌平仓覆盖孤儿仓位、租约不可用时拒绝下单、反向成交归因。
2. 全量回归期权卖家套件（含既有的 30 项平仓/风控用例），确认零回归。
3. 实盘只读验证：`GET /api/option_seller/status` 返回 `monitor_lease` 字段（leader pid / 心跳）；
   启动自检脚本确认租约 claim/heartbeat 与租约表建表在真实 MySQL 上可用。

## 6. 部署要求（重要）

租约只能约束**加载了新代码的进程**。当前环境中仍有一个自 2026-09-15 21:20 起常驻、
加载旧代码的进程（reloader 父进程）——**必须重启 5005 服务一次**，让父/子进程都换上新代码，
单实例仲裁才真正生效。重启后应看到：
`[OptionSeller] reloader 父进程: 跳过 start_monitor()` 且仅有一个进程输出
`监控租约: ... leader=本进程`。
