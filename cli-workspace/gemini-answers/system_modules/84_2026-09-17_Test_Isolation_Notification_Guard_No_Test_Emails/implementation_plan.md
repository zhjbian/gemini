# 测试进程真实发信事故：通知隔离守卫 + 生产侧邮件总闸 实施计划 (Plan)

- **日期**：2026-09-17（PT）
- **归属模块**：**M18. 交易基础设施与开发环境工具链**（能力域 = 测试隔离 / 开发工具链安全性；交叉引用 **M11. Option Seller 本地风控、持仓监控与止盈止损系统** —— 通知器 `option_seller_notifier` 的徽标体系此前记于 M11，本次只修"测试不得外发"这一条，不重复在 M11 建行）
- **触发场景**：用户报障（附两封邮件截图）——「刚才有这 2 有邮件 但实际上 TOS 里仓位并没有 close 请 fix」
  - 邮件 ①：`批次1 已成功止盈 (+$8.00)` · `SPY-560.0+558.0` · `#103` · `CLOSED_TAKE_PROFIT_T1` · 开仓时间 07:00:00
  - 邮件 ②：`批次1 触及 2.2x 硬止损线，已强制平仓 (−$31.00)` · `SPY-560.0+558.0` · `#104` · `CLOSED_STOP_LOSS`
- **性质**：**测试隔离缺口修复 ×1（严重：测试进程向用户真实发信）＋ 通知层总闸新增 ×1 ＋ 契约测试 8 项**
- **技术栈**：Python 3.11 · `PyTools/option_seller/test_isolation.py`（守卫）· `PyTools/option_seller/option_seller_notifier.py`（EMAIL_ENABLED / 环境变量总闸）· unittest · `bbt_trading_modules.html`（M18）

---

## 1. 取证链（先证明"是谁发的"，再动手）

### 1.1 生产侧（`Config/bbt_option_seller.log`，最新在上）今天只发了 1 封邮件，且与事故无关

```text
2026-09-17 06:43:39,170 INFO: Email notification dispatched successfully under subject 'Re: BBT_LiveOptionSeller'.
```
（那是 06:43 手动开仓 `#290/#291` 的开仓通知；今天**没有任何** `CLOSED` 事件。）

### 1.2 事故邮件来自**测试进程**（测试日志被守卫重定向到 `$TMPDIR`，故生产日志查无此事）

```text
$TMPDIR/bbt_option_seller_test.log
2026-09-17 06:54:21,697 INFO: Live Resting Limit TP filled by broker for trade #103 (批次1) @ 0.12
2026-09-17 06:54:21,697 INFO: Trade #103 CLOSED (CLOSED_TAKE_PROFIT_T1) @ 0.12 (Credit=0.2) Realized PnL=$8.0
2026-09-17 06:54:21,766 INFO: Trade #104 CLOSED (CLOSED_STOP_LOSS) @ 0.51 (Credit=0.2) Realized PnL=$-31.0
2026-09-17 06:54:22,996 INFO: Email notification dispatched successfully under subject 'Re: BBT_LiveOptionSeller'.
```

- 夹具来源：`test_live_resting_limit_order.py`（`short_strike 560.0 / long_strike 558.0`、`SPY_083126P560/P558`、` Credit 0.20`）—— 与邮件中的 `SPY-560.0+558.0`、`+$8.00`、`−$31.00`、`开仓时间 07:00:00` 完全对应；
- 触发链路：测试 `close_trade()`（`is_dry_run=False` 夹具）⇒ `OptionSellerNotifier.notify_trade_closed()` ⇒ SMTP；
- **同一进程里其余出口都已被隔离**：券商写被 `BROKER_WRITE_METHODS` 拦截、DB 写被 no-op（假 id `900001+`）、日志被重定向到临时文件 —— **唯独邮件没有任何守卫**。

### 1.3 影响范围量化（测试日志计数）

```text
$ grep "Email notification dispatched successfully" $TMPDIR/bbt_option_seller_test.log | awk '{print $1}' | sort | uniq -c
  52 2026-09-16
   9 2026-09-17
```

即：该泄漏已持续至少两天、累计 **61 封**测试邮件（09-16 一天 52 封）。用户今天看到的 2 封只是其中最近的。

### 1.4 反证：真实系统与真实仓位均未被影响

| 检查项 | 结果 |
| :--- | :--- |
| 真实 DB 行 `#103/#104`（`trade_date=2026-09-02`，**DRY-RUN**，strikes `760/758`） | 状态仍为 `CLOSED_TAKE_PROFIT_T1 / T2`，与事故无关 ⇒ **未被测试改动**（DB 写被守卫 no-op） |
| 券商侧 | 测试内 `BBTOS.close_vertical_spread` 被 mock（`777333` 为假单号），守卫亦拦截真实下单 ⇒ **未向 Schwab 发过任何平仓单** |
| 今日实盘状态（`GET /api/option_seller/status`） | `active_positions_count=2`、`broker_option_positions=2`、`drift=false`、`known_but_missing_on_broker=[]`、`unknown_positions=[]` ⇒ **无幽灵/漂移状态** |

**结论**：这是**通知层的测试隔离缺口**，不是交易逻辑缺陷；真实仓位既未被平掉、也未被误标记。

---

## 2. 修复设计（两层，互不依赖）

### 2.1 层一：生产侧总闸 —— `OptionSellerNotifier`

```python
class OptionSellerNotifier:
    EMAIL_ENABLED = True                                   # 总闸（默认开）
    EMAIL_DISABLE_ENV = 'BBT_OPTION_SELLER_EMAIL_DISABLED'  # 环境变量总闸
    muted_count = 0                                         # 静音计数（可观测）

    @classmethod
    def email_allowed(cls) -> bool: ...                     # 总闸 + 环境变量（'1'/'true'/'yes'/'on'）
```

- 闸门加在**唯一两个咽点**上：`send_async()`（派发线程入口）与 `_send_email_thread()`（唯一 SMTP 调用点）；
  静音时**连线程都不起、绝不建立 SMTP 连接**，并记 WARNING 日志（可审计）。
- 选择"两个咽点"而非替换 `notify_*`：三个 `notify_*` 全部经 `cls.send_async(...)` 派发
  （`option_seller_notifier.py:327 / 503 / 593`）⇒ 掐咽点即 100% 阻断，同时保留 `notify_*` 的 HTML 组装能力
  （`test_option_seller_notifier_badges` 需要断言邮件内容/徽标）。

### 2.2 层二：测试守卫 —— `test_isolation`（第 E 类隔离）

```python
NOTIFIER_MUTE_METHODS = ('send_async', '_send_email_thread')   # 只掐咽点
MUTED_NOTIFICATIONS = []          # 静音记录（用例可断言）
ORIGINAL_METHODS = {...}          # 保留原始方法引用（供受控验证生产侧行为）

def install_guard():
    os.environ[OptionSellerNotifier.EMAIL_DISABLE_ENV] = '1'   # 环境变量总闸（双保险）
    OptionSellerNotifier.EMAIL_ENABLED = False
    ... 替换两个咽点为 _make_notifier_guard(...)
```

- `GuardedTestCase.setUp` 同时重置静音记录；
- 新增受控入口 `call_original_notification(name, *args)`：仅供"必须验证信封/主题"的用例调用原始实现，
  且**硬性要求 `smtplib.SMTP` 已被 mock**，否则直接抛错拒绝执行（杜绝"为测信封头而真发一封信"）。

### 2.3 为什么不做成"违规即失败"

`close_trade()` 在业务上本来就会调用通知；若把静音记为 VIOLATION，会让大量合理的既有用例失败。
正确处理是**静音 + 记录 + 可观测**（`MUTED_NOTIFICATIONS` / `muted_count` / stderr 逐条打印）。

---

## 3. 改动清单

| 文件 | 改动 |
| :--- | :--- |
| `PyTools/option_seller/option_seller_notifier.py` | 新增 `EMAIL_ENABLED` / `EMAIL_DISABLE_ENV` / `muted_count` / `email_allowed()` / `mute()` / `unmute()`；两层闸门加在 `send_async` 与 `_send_email_thread`；`import os`；类 docstring 记录本次事故 |
| `PyTools/option_seller/test_isolation.py` | 新增第 E 类隔离（`NOTIFIER_MUTE_METHODS` / `MUTED_NOTIFICATIONS` / `ORIGINAL_METHODS` / `reset_muted_notifications` / `call_original_notification`）；`install_guard` 设环境变量 + 静音咽点 + 打印"静音 N 个通知方法"；docstring 补事故背景 |
| `PyTools/option_seller/test_option_seller_notifier_badges.py` | 信封/主题用例改走 `call_original_notification('_send_email_thread', ...)`（受控、要求 SMTP 已 mock） |
| `PyTools/option_seller/test_no_test_notifications.py` | **新增**：8 项契约测试（咽点静音 / 环境变量总闸语义 / 原始发送器静音即 no-op / 总闸打开确实进入 SMTP 链路 / `notify_*` 仍组装 HTML / 完整 `close_trade()` 事故链路 0 次 SMTP） |
| `system_modules/bbt_trading_modules.html` | M18 历史表新增 1 行 + 计数 6 → 7 + TOC 徽标 + 总览行 |

---

## 4. 验证方法（含"证明没发信"的口径）

```bash
# ① 新增契约测试
/usr/local/bin/python3 PyTools/option_seller/test_no_test_notifications.py

# ② 事故回归：重跑当初泄漏的那支测试，逐字校验（**分层取证**）
TL=$TMPDIR/bbt_option_seller_test.log        # 实际路径见守卫打印
B=$(grep -c "Email notification dispatched successfully" "$TL")
/usr/local/bin/python3 PyTools/option_seller/test_live_resting_limit_order.py
A=$(grep -c "Email notification dispatched successfully" "$TL")
echo "新增真实发送日志行: $((A-B))"          # 必须为 0

# ③ stderr 取证：守卫逐条打印"通知已静音（绝不真实发送）"
/usr/local/bin/python3 PyTools/option_seller/test_live_resting_limit_order.py 2>&1 | grep "通知已静音"

# ④ 生产进程未被静音污染（应为 0）
for P in $(lsof -nP -iTCP:5005 -sTCP:LISTEN -t | sort -u); do ps eww $P | tr ' ' '\n' | grep -c BBT_OPTION_SELLER_EMAIL_DISABLED; done
```

**取证纪律**：`Email notification dispatched successfully` 这行日志**只允许由真实发送产生**；
因此"总闸打开确实有效"的对照用例改为让 mock 的 `login()` 抛哨兵异常（断言 SMTP 被调用但 `sendmail` 未被调用），
避免用 mock 造出一条假的"发送成功"日志、污染本口径。

---

## 5. 回滚方式

```bash
# PyTools 为独立 git 仓库：撤销 4 个文件即可（其中 1 个为新增测试文件，可直接删除）
cd /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools
git checkout -- option_seller/option_seller_notifier.py option_seller/test_isolation.py option_seller/test_option_seller_notifier_badges.py
rm -f option_seller/test_no_test_notifications.py
```

不变式：生产路径默认 `EMAIL_ENABLED=True` 且环境变量未设置 ⇒ 发信行为与改动前**完全一致**
（契约测试 `test_original_sender_still_works_when_enabled` 反向锁定该点）。

---

## 6. 不影响面

- **不改交易逻辑**：`option_seller_manager` 的开/平仓、风控、监控租约零改动；本次只动"通知外发"与"测试隔离"。
- **不改通知内容**：`notify_*` 的 HTML/徽标/主题不变（`test_option_seller_notifier_badges` 5 项全绿）。
- **不改 DB / 券商交互**：无新增写入路径。
- 生产日志格式与条数不变（静音日志只在被静音时出现，生产默认不出现）。
