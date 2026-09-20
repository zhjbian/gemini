# 测试进程真实发信事故：通知隔离守卫 + 生产侧邮件总闸 验收报告 (Walkthrough)

- **日期**：2026-09-17（PT）
- **归属模块**：**M18. 交易基础设施与开发环境工具链**（交叉引用 M11 通知器徽标）
- **用户指令原文**：「刚才有这 2 有邮件 但实际上 TOS 里仓位并没有 close 请 fix」
- **结论**：**已定位并修复** —— 事故邮件是**测试夹具**经 `close_trade() ⇒ notify_trade_closed()` 真实发出的（不是实盘平仓事件）；真实仓位、真实 DB、券商侧**均未被影响**；已加"测试静音 + 生产总闸"两层防护，重跑当初泄漏的测试**新增真实发送 0 次**，契约测试 **8/8 PASS**。

---

## 1. 一句话结论（回答用户）

| 用户疑问 | 事实 |
| :--- | :--- |
| "仓位并没有 close"？ | **对，没有关。** 那两封邮件与你的真实仓位无关：邮件里是 `SPY-560.0+558.0`、`#103/#104` —— 那是**测试夹具**的合约与编号 |
| 那邮件是谁发的？ | **我（AI）刚才跑测试套件时**，测试进程里的 `close_trade()` 调用触发了真实 SMTP 发信（06:54:21–06:54:22） |
| 系统把我的仓位平了吗？ | **没有。** 今日实盘状态：`active=2`、`broker_option_positions=2`、`drift=false`、无"系统认为已平/券商仍持有"的幽灵记录 |
| 真实 DB 被测试改了吗？ | **没有。** DB 写被测试守卫 no-op；真实 `#103/#104`（2026-09-02，DRY-RUN，760/758）状态原封不动 |
| 会再发生吗？ | **不会。** 通知咽点在测试进程内被静音（三层保险：守卫替换 + `EMAIL_ENABLED=False` + 环境变量总闸） |

---

## 2. 交付清单

### 2.1 代码改动（3 改 + 1 新增测试）

| 文件 | 改动 |
| :--- | :--- |
| `PyTools/option_seller/option_seller_notifier.py` | 新增邮件总闸：`EMAIL_ENABLED`（默认 True）/ `EMAIL_DISABLE_ENV='BBT_OPTION_SELLER_EMAIL_DISABLED'` / `muted_count` / `email_allowed()` / `mute()` / `unmute()`；闸门加在 `send_async()` 与 `_send_email_thread()`（**连线程都不起、绝不建 SMTP 连接**，静音时记 WARNING）；`import os`；类 docstring 记录事故 |
| `PyTools/option_seller/test_isolation.py` | 新增第 E 类隔离：`NOTIFIER_MUTE_METHODS=('send_async','_send_email_thread')`、`MUTED_NOTIFICATIONS`、`ORIGINAL_METHODS`、`reset_muted_notifications()`、`call_original_notification()`（**硬性要求 smtplib.SMTP 已 mock，否则拒绝执行**）；`install_guard()` 设环境变量 + 静音咽点，横幅打印"静音 2 个通知方法" |
| `PyTools/option_seller/test_option_seller_notifier_badges.py` | 信封/主题用例改走受控入口 `call_original_notification('_send_email_thread', ...)`（原本直接调 `_send_email_thread`，正是泄漏点之一） |
| `PyTools/option_seller/test_no_test_notifications.py` | **新增 8 项契约测试**（见 §3.1） |

### 2.2 文档改动（规则 (10)）

| 文件 | 改动 |
| :--- | :--- |
| `system_modules/84_2026-09-17_Test_Isolation_Notification_Guard_No_Test_Emails/implementation_plan.md` | 本归档 Plan |
| `system_modules/84_2026-09-17_Test_Isolation_Notification_Guard_No_Test_Emails/walkthrough.md` | 本归档 Walkthrough |
| `system_modules/bbt_trading_modules.html` | M18 卡片：职责/技术栈补写 + 「累计演进历程」**6 → 7**；M18 历史表新增 1 行（2026-09-17）；TOC 徽标 `6次演进 → 7次演进`；总览表 M18 行 `badge-count 6 次 → 7 次`、最后更新 `2026-09-15 → 2026-09-17` |

> 规则 (11) 判定：本改动是**工程实现层**（测试隔离 + 开关），不构成趋势/交易决策规则 ⇒ 不写入决策规则手册 ✓

---

## 3. 验收清单逐条核对

### 3.1 契约测试 8/8 PASS

```console
$ /usr/local/bin/python3 PyTools/option_seller/test_no_test_notifications.py
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、13 个数据库写方法、静音 2 个通知方法；测试日志 -> $TMPDIR/bbt_option_seller_test.log
test_entry_points_are_muted ... ok
test_guard_sets_env_kill_switch ... ok
test_notify_business_methods_still_render_html ... ok            # 静音只掐外发、不废业务（HTML 仍组装）
test_email_allowed_semantics ... ok                              # 总闸 + '1'/'true'/'YES'/'on' 全识别
test_original_sender_is_noop_when_muted ... ok                   # 绕过守卫直调原始发送器 ⇒ 仍 0 次 SMTP
test_original_sender_still_works_when_enabled ... ok             # 反向对照：总闸开着确实进 SMTP 链路（生产发信未被开关打死）
test_stop_loss_close_sends_no_email ... ok                       # ★ 事故回归：560/558 · close 0.51 全链 0 次 SMTP
test_take_profit_close_sends_no_email ... ok                     # ★ 事故回归：close 0.12（is_broker_filled）0 次 SMTP
----------------------------------------------------------------------
Ran 8 tests in 0.072s

OK
```

### 3.2 事故回归：重跑当初泄漏的那支测试 ⇒ **新增真实发送 0 次**

```console
$ TL=$TMPDIR/bbt_option_seller_test.log
$ B=$(grep -c "Email notification dispatched successfully" "$TL")     # before = 61
$ /usr/local/bin/python3 PyTools/option_seller/test_live_resting_limit_order.py
Ran 14 tests in 4.507s
OK
$ grep -c "Email notification dispatched successfully" "$TL"          # after = 61
新增真实发送日志行: 0

# stderr 逐条取证（守卫确实拦下了派发）
$ /usr/local/bin/python3 PyTools/option_seller/test_live_resting_limit_order.py 2>&1 | grep "通知已静音"
[TEST GUARD] 通知已静音（绝不真实发送）: OptionSellerNotifier.send_async()      ← ×5（本用例 5 次平仓/通知）
```

> 取证纪律：`Email notification dispatched successfully` 只允许由**真实发送**产生；
> 因此"总闸打开仍能发信"的对照用例改为让 mock 的 `login()` 抛哨兵异常
> （断言 SMTP 被调用、`sendmail` 未被调用），不制造假的"发送成功"日志来污染该口径。

### 3.3 相关回归（8 支测试模块）

```console
test_no_test_notifications.py       :: Ran  8 tests  OK   ← 本次新增
test_option_seller_notifier_badges.py :: Ran 5 tests  OK   ← 信封/主题用例已改走受控入口
test_live_resting_limit_order.py    :: Ran 14 tests  OK   ← 事故源用例
test_force_dry_degrade.py           :: Ran 18 tests  OK
test_direction_suppress.py          :: Ran 15 tests  OK   ← 同日「方向抑制」特性
test_journal_filter_catalog.py      :: Ran 11 tests  OK
test_orphan_position_reconcile.py   :: Ran 22 tests  OK
test_monitor_single_instance_lease.py :: Ran 15 tests OK
```

### 3.4 生产侧未受污染（发信能力与配置均正常）

```console
# ① 生产进程（5005）环境变量未被静音污染 ⇒ 计数应为 0
$ for P in $(lsof -nP -iTCP:5005 -sTCP:LISTEN -t | sort -u); do ps eww $P | tr ' ' '\n' | grep -c BBT_OPTION_SELLER_EMAIL_DISABLED; done
0
0

# ② 生产侧今天唯一一封邮件是 06:43 的**开仓**通知（与事故无关）
2026-09-17 06:43:39,170 INFO: Email notification dispatched successfully under subject 'Re: BBT_LiveOptionSeller'.

# ③ 真实仓位无漂移
$ curl -s .../api/option_seller/status | python3 -c "..."
active_positions_count=2 | broker_option_positions=2 | drift=false
known_but_missing_on_broker=[] | unknown_positions=[] | untracked_spreads=[]
```

### 3.5 真实数据未被测试改动（反证）

```console
$ curl -s ".../trades_by_date?date=2026-09-02"        # 真实 #103/#104 所在日
{'id': 104, 'status': 'CLOSED_TAKE_PROFIT_T1', 'is_dry_run': True, 'short_strike': 760.0, ...}   # 原封不动
{'id': 103, 'status': 'CLOSED_TAKE_PROFIT_T2', 'is_dry_run': True, 'short_strike': 760.0, ...}
```

---

## 4. 影响范围量化（如实报告）

- 测试进程真实发信**至少持续两天**：`$TMPDIR/bbt_option_seller_test.log` 统计
  → **2026-09-16：52 封**、**2026-09-17：9 封**（合计 61 封，含本次事故中的 2 封）。
- 邮件内容全部是**测试夹具**（id 101–104 / 201 / 202 / 208 等合成编号），
  与真实交易编号体系（今日为 #290/#291）不重叠 ⇒ 收到此类邮件时**不要据此判断实盘仓位**。
- 本修复后，任何测试进程再次运行都不会外发邮件；生产进程的发信能力保持不变。

---

## 5. 结论与给用户的建议

1. **请忽略** 2026-09-17 06:54 那两封 `SPY-560.0+558.0` 的止盈/止损邮件 —— 它们是测试夹具，不是你的仓位；
   你今日的真实仓位（`SPY 757/755` put spread，`#290/#291`，06:43 手动开仓）**仍然在管**，
   两腿皆有券商侧止盈挂单，`drift=false`。
2. 若今后再收到"编号很小（100 左右）、strike 明显不合理（如 560）"的平仓邮件，可直接判定为测试残留
   （本修复后应彻底消失）；判据是：**以 TOS 实际持仓为准，以页面「活跃持仓监控」为准**。
3. 修复后重跑事故源测试**新增真实发送 0 次**；新增 8 项契约测试把该不变量锁死，
   并保留"总闸打开时仍能发信"的反向对照，避免把生产通知打死。
