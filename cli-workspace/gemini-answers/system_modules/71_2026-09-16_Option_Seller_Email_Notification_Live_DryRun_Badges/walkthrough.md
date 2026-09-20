# 期权卖家系统邮件通知 LIVE 实盘与 DRY-RUN 模拟盘醒目标识改造 验收报告 (Walkthrough)

## 1. 任务概述
根据交易员要求，期权卖家系统（`Option Seller`）发出的所有邮件通知（涵盖开仓、平仓、保本激活等各类型）必须在全链路以极其醒目的视觉元素标识当前是 **LIVE 实盘交易** 还是 **DRY-RUN 模拟/试运行**，杜绝误判混淆风险。

## 2. 核心修改与实现要点

### 2.1 修改文件
- 生产代码：[PyTools/option_seller/option_seller_notifier.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_notifier.py)
- 单元测试：[PyTools/option_seller/test_option_seller_notifier_badges.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/test_option_seller_notifier_badges.py)

### 2.2 视觉与技术改造层级

| 呈现区域 | LIVE 实盘样式 | DRY-RUN 模拟盘样式 | 说明 |
| :--- | :--- | :--- | :--- |
| **邮件主题 (Subject)** | `Re: BBT_LiveOptionSeller` | `Re: BBT_DryOptionSeller` | 邮箱收件箱列表未点开前即可一目了然 |
| **Gmail 会话线程 (Thread-ID)** | `<bbt-live-option-seller-thread@bbtrading.local>` | `<bbt-dry-option-seller-thread@bbtrading.local>` | 会话独立分流，实盘与模拟单不交叉混合 |
| **手机锁屏/推送摘要 (Preheader)** | `【🔴 LIVE 实盘开仓/平仓/保本】...` | `【DRY-RUN 模拟开仓/平仓/保本】...` | 手机锁屏和折叠通知第一时间显示状态 |
| **卡片顶框强调线 (Top Border)** | `border-top: 4px solid #ef4444` (警示红) | `border-top: 4px solid #64748b` (沉稳灰) | 邮件打开瞬间即有顶部色条区分 |
| **横幅标题栏徽章 (Banner Pill)** | `🔴 LIVE 实盘交易` (红底白字立体发光胶囊) | `🧪 DRY-RUN 模拟盘` (半透磨砂徽章) | 右上角大号胶囊徽章，视觉重心极强 |
| **合约副标题行内徽章 (Subtitle)** | `LIVE 实盘` (深红底白字行内 Tag) | `DRY-RUN 模拟` (石板灰底行内 Tag) | 合约代码旁紧随伴标 |
| **详情表格「执行环境」行** | `🔴 LIVE TRADING (Schwab 实盘)` | `🧪 DRY-RUN (纸面模拟盘)` | 开仓、平仓、保本 3 大通知表格全部统一齐备 |
| **页脚审计注脚 (Footer)** | `• 🔴 LIVE 真实资金实盘 •` | `• 🧪 DRY-RUN 模拟盘 •` | 明确底部署名环境 |

## 3. 验证与测试结果

### 3.1 自动化测试全量通过
执行专用单元测试：
```bash
PYTHONPATH=PyTools:PyTools/option_seller /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m unittest PyTools/option_seller/test_option_seller_notifier_badges.py
```
测试结果：
```text
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、10 个数据库写方法；测试日志 -> /var/folders/.../bbt_option_seller_test.log
.....
----------------------------------------------------------------------
Ran 5 tests in 0.006s

OK
```

覆盖点全面验证：
1. `test_is_dry_run_helper`: 校验各种字段（`False`、`True`、`0`、`1`、`'live'`、`'false'`、`None`、空字典）的解析准确性。
2. `test_notify_trade_opened_live_vs_dry`: 验证开仓通知中实盘与模拟盘对应 HTML 与参数传递。
3. `test_notify_trade_closed_live_vs_dry`: 验证平仓通知中（包括止盈、止损、保本、超时平仓、手动平仓）实盘与模拟盘所有徽章及表格行呈现。
4. `test_notify_l1_h1_breakeven_activated_live_vs_dry`: 验证保本通知中实盘与模拟盘的呈现。
5. `test_send_email_thread_subject_and_headers`: 验证底层 SMTP 报文中 Subject（RFC 2047 MIME 解码后确认）及 `In-Reply-To` / `References` 严格独立。

### 3.2 现有测试回归兼容性
运行原有核心集成测试：
```bash
PYTHONPATH=PyTools:PyTools/option_seller /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m unittest PyTools/option_seller/test_l1_h1_breakeven_stop.py
```
测试结果：
```text
Ran 1 test in 1.278s
OK
[SUCCESS] test_l1_h1_dual_tranche_breakeven_flow passed perfectly!
```
所有原有调用方和 Mock 机制完全平滑兼容。
