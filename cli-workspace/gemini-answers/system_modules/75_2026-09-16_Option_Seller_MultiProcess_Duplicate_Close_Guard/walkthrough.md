# 期权卖家系统「平仓单被反向执行为开仓」多进程重复平仓事故 验收报告 (Walkthrough)

## 1. 任务概述

交易员报障：**11:38:58 卖家系统「活跃持仓监控」为空，但 TOS 里有仓位**。
要求：查清成因，并阻止其再次发生。

结论：这不是显示问题，而是一次**多进程重复平仓**事故——两个进程各跑一遍退出判定，
第二次平仓单在券商侧已无持仓，被 Schwab **反向执行为开仓**，凭空建出一个
系统不跟踪、无止盈、无止损的反向价差（long 1×754P / short 1×752P）。

## 2. 事故链（券商订单逐笔还原，可复现核对）

| 时刻 (PT) | 事件 | 券商订单/事实 |
| :--- | :--- | :--- |
| 11:15:16 / 11:15:18 | 开出 #288 / #289（754/752 Bull Put，各 1 张，credit 0.17） | `1007950915849` / `1007950915854` FILLED（`SELL_TO_OPEN 754P` + `BUY_TO_OPEN 752P`） |
| 11:35:24 | 进程 A 平 #289 | `1007952049224` NET_DEBIT 0.38 FILLED |
| 11:35:25 | 进程 A 平 #288 | `1007952049229` NET_DEBIT 0.38 FILLED（账户归零） |
| **11:35:26** | **进程 B 再平 #288** | `1007952049235` **legs = `SELL_TO_OPEN 752P` + `BUY_TO_OPEN 754P`** FILLED ⇒ 反向价差诞生 |
| 11:38:05 / 11:38:24 | 操作员点「恐慌平仓」×2 | `Panic close executed: 0 positions closed`（在管列表为空，一张单都不发） |
| 11:39:23 / 11:39:33 | 人工在券商端分腿平掉反向价差 | `BUY_TO_CLOSE 752P` @0.35 / `SELL_TO_CLOSE 754P` @0.59 |

日志侧同时给出"两个模块版本并发"的铁证：同一笔 #288 的平仓提交被
`option_seller_manager.py:2224`（旧代码）与 `:2665`（当前代码）各记录一次，
两张不同的平仓单号（…229 / …235）在 1.2 秒内先后成交。

## 3. 根因

1. **Flask debug reloader 双进程**：`start_monitor()` 位于 `bbt_data_app.py` 的
   `if __name__ == '__main__':` 块内，父/子进程都会执行 ⇒ 两个风控监控线程；
   父进程自 9/15 21:20 常驻且**永不重载代码**，于是新旧逻辑长期并存。
2. **单飞锁只在进程内有效**：`status='CLOSING'` 占位存在于各进程自己的内存表，互不可见。
3. **Schwab 把无持仓可平的 NET_DEBIT 单反向执行为开仓**（2026-09 已记录同类事故），
   持仓校验与订单落市之间存在 TOCTOU 窗口。
4. **紧急平仓不覆盖券商真实持仓**：`panic_close_all()` 只遍历在管交易，
   零在管时按钮形同虚设 —— 恰是最需要它的场景。

## 4. 修改文件与实现要点

| 文件 | 关键改动 |
| :--- | :--- |
| `bbt_data_app.py` | 仅在 `is_running_from_reloader()` 为真（子进程）时 `start_monitor()` |
| `db_query_module/db_query_option_seller.py` | 租约表 DDL + `option_seller_monitor_claim()` / `option_seller_monitor_heartbeat()` |
| `option_seller_manager.py` | `_claim_monitor_lease()` / `_monitor_lease_check()`（最新进程优先、陈旧可抢占、DB 抖动 fail-open）；监控循环与 UI 刷新路径的非 leader 只读化；`panic_close_all()` 覆盖未跟踪敞口；`flat_uncovered_broker_positions()` / `_submit_flat_pair()`；`_expected_broker_exposure()`；`_ledger_trades_matching_symbols()` 增加 `REVERSE_OF_CLOSED_TRADE` 归因 |
| `bbt_option_seller.html` | 对账卡片新增「监控实例 leader / 只读待命」徽章；孤儿仓位按「反向执行为开仓 / 作废后延迟成交」两类成因分别提示 |
| `test_monitor_single_instance_lease.py` | 新增 11 条回归用例 |
| `test_isolation.py` | 新增 3 个 DB 写拦截（测试进程不得写真实租约表，避免把自己写成 leader 干扰实盘仲裁） |

### 4.1 单实例仲裁语义

```text
同一时刻只有一个进程拥有「下单/平仓/撤单」权限：
  · start_monitor() 启动即抢占租约（最新进程胜出）
  · 每轮先 _monitor_lease_check()：非 leader -> 不做任何券商写操作，10s 后复查
  · 发现更新启动的 leader -> 立即让位（旧代码常驻进程退场的路径）
  · leader 心跳 > 45s 未刷新 -> 可被抢占（leader 崩溃自动接管）
  · 租约查询异常 -> fail-open（按 leader 运行并大声记录），风控不停摆
```

### 4.2 未跟踪敞口平仓方向（测试锁定的关键点）

`close_vertical_spread(short_symbol = 实际空腿, long_symbol = 实际多腿)` ——
对本次反向价差（多 754P / 空 752P）生成 `BUY_TO_CLOSE 752P` + `SELL_TO_CLOSE 754P`，
与人工平仓逐字一致（**不套用**"卖方价差 = 空高行权"的常规约定）。

## 5. 验证结果

### 5.1 新增用例（11 项全通过）

```bash
PYTHONPATH=PyTools:bbt_data_web /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  -m unittest test_monitor_single_instance_lease test_orphan_position_reconcile
```

```text
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、13 个数据库写方法
............................
----------------------------------------------------------------------
Ran 28 tests in 0.891s
OK
```

覆盖：租约抢占标记 leader / 让位于更新进程 / 心跳陈旧接管 / DB 抖动 fail-open /
待命进程不接管 / UI 刷新路径降级只读 / 反向价差平仓方向与配对 / 已覆盖持仓不重复平仓 /
恐慌平仓覆盖孤儿敞口 / 租约不可用时拒绝下单 / 反向成交归因 `REVERSE_OF_CLOSED_TRADE`。

### 5.2 全量回归（582 项）

```text
Ran 582 tests in 246.597s
FAILED (failures=1, skipped=1)
```

唯一失败项仍为既有、与本次改动无交集的 `test_absorption_reversal_module`
（ES 吸收反转投票门槛样本 5 < 6）。

### 5.3 真实环境自检（租约表 + 仲裁链路）

```text
manager init OK; pid=55189 started_ms=1789604993783
claim -> True
check -> True is_leader= True
status monitor_lease: {'is_leader': True, 'pid': 55189, ..., 'error': None}
reconcile: {'broker_option_positions': 0, 'drift': False, 'query_failed': False, ...}
```

租约表已在真实 MySQL 建好，claim/heartbeat/状态透出链路可用，当前账户无持仓、无漂移。

## 6. 部署要求与善后

1. **必须重启 5005 服务一次**：租约只能约束**加载了新代码的进程**；当前环境仍有
   一个自 2026-09-15 21:20 常驻、加载旧代码的进程。重启后应观察到
   `[OptionSeller] reloader 父进程: 跳过 start_monitor()`，且只有一个进程打印
   `监控租约: ... leader=本进程`；页面「券商端真实持仓对账」卡片会显示
   `监控实例 leader: pid N`（另一进程若存在则显示 `只读待命（非 leader）`）。
2. 事故中的反向价差已于 11:39 人工平掉，账户当日无残留敞口（17:14 复查为 0）。
3. 遗留观察：本次事故的触发前提是"两进程并存"。若重启后页面仍出现
   `只读待命（非 leader）` 且 leader pid 与 5005 服务进程不一致，说明还有其它常驻实例，需要排查其来源。

### 6.1 重启与生效验证（2026-09-16 18:19 PT）

重启 5005 服务后（父进程 78582 / 子进程 78601），启动输出与状态接口确认单实例仲裁已生效：

```text
[OptionSeller] reloader 父进程: 跳过 start_monitor()（风控监控线程只在子进程运行；另有跨进程租约兜底）
 * Running on http://127.0.0.1:5005
18:19:14 WARNING: OptionSeller 监控租约: pid=78601 started_ms=1789607953847 leader=本进程
```

```json
"monitor_lease": {"is_leader": true, "pid": 78601, "leader_pid": 78601,
                  "leader_started_ms": 1789607953847, "heartbeat_ms": 1789607978304, "error": null}
```

即：**只有一个进程承载风控监控线程并持有下单权限**，父进程不再承载业务线程；
账户当时无持仓、无漂移（`drift=false`、`broker_option_positions=0`）。

备注（透明留痕）：17:26:46 曾出现过一条
`监控租约抢占失败 ('OptionSellerManager' object has no attribute '_pid') —— 按 leader 处理 (fail-open)`
——那是热重载恰好落在"租约方法已就位、`_pid` 尚未初始化"的中间态文件上；
也正是 fail-open 设计让它没有中断风控。重启后该错误不再出现。
