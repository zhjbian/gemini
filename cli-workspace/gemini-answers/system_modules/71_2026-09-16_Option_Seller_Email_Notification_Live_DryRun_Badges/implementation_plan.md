# 期权卖家系统邮件通知 LIVE 实盘与 DRY-RUN 模拟盘醒目标识改造 实施计划 (Plan)

## 1. 业务背景与用户需求
在日常实盘与模拟交易运行过程中，期权卖家系统（`OptionSeller`）会异步向交易员邮箱发送开仓、平仓（止盈、止损、保本、超时平仓、手动平仓）以及两手保本移动等关键事件通知。
此前存在以下识别痛点：
1. **平仓与保本邮件缺乏环境标示**：止盈止损与保本邮件模板中完全缺失执行环境（`is_dry_run`）字段显示，用户查看邮件内容时无法第一时间判定是真实资金操作还是回测/试运行数据。
2. **邮件主题未区分会话**：所有邮件统一使用 `Re: BBT_OptionSeller` 主题，且归并在同一个 Message-ID 线程下，导致 Gmail 中实盘重要单与测试试运行单混合展示，易发生误读。
3. **移动端通知摘要缺乏警示**：移动端通知推送或邮件折叠预览时，摘要前缀没有明确标识环境，无法在锁屏界面快速区分。

## 2. 改造方案设计

### 2.1 视觉与标识规范设计（遵循 User Rule 12 浅色护眼与高对比度规范）
1. **邮件主题与邮件线程分流**：
   - 实盘订单：`Subject: [🔴 LIVE 实盘] Re: BBT_OptionSeller`，线程 Message-ID: `<bbt-option-seller-live-thread@bbtrading.local>`
   - 模拟单/试运行：`Subject: [DRY-RUN 模拟] Re: BBT_OptionSeller`，线程 Message-ID: `<bbt-option-seller-dryrun-thread@bbtrading.local>`
   - 实现 Gmail 客户端自然归拢为两条独立会话线，实盘订单不被测试单淹没。
2. **移动端推送隐藏预检文本 (Hidden Preheader)**：
   - 统一在前部置顶高对比标签：`【🔴 LIVE 实盘开仓】` / `【🔴 LIVE 实盘平仓】` / `【🔴 LIVE 实盘保本】` 或 `【DRY-RUN 模拟开仓】` 等。
3. **卡片顶部边缘强调线 (Card Accent Top Border)**：
   - 实盘：`border-top: 4px solid #ef4444`（醒目红色警示条）
   - 模拟盘：`border-top: 4px solid #64748b`（稳重石板灰）
4. **横幅标题栏顶部胶囊徽章 (Banner Pill Badge)**：
   - 实盘：`<span style="background: #dc2626; color: #ffffff; font-size: 12px; font-weight: 900; padding: 4px 12px; border-radius: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); border: 1.5px solid #ffffff;">🔴 LIVE 实盘交易</span>`
   - 模拟盘：`<span style="background: rgba(15, 23, 42, 0.45); color: #f8fafc; font-size: 12px; font-weight: 700; padding: 4px 12px; border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.45);">🧪 DRY-RUN 模拟盘</span>`
5. **表格明细行统一增加「执行环境」行**：
   - 无论开仓、平仓还是保本激活，详情表格统一增设「执行环境」栏：
     - 实盘：`🔴 LIVE TRADING (Schwab 实盘)`
     - 模拟盘：`🧪 DRY-RUN (纸面模拟盘)`
6. **页脚明确归档环境**：
   - 实盘显示：`BBT.AI Option Seller • 🔴 LIVE 真实资金实盘 • 自动风控审计日志已归档`
   - 模拟盘显示：`BBT.AI Option Seller • 🧪 DRY-RUN 模拟盘 • 自动风控审计日志已归档`

### 2.2 涉及模块与代码变动
- 核心修改文件：[option_seller_notifier.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_notifier.py)
  - 增加静态方法与类方法：
    - `_is_dry_run(cls, obj: Any) -> bool`: 健壮解析 `dict`、`bool`、`int`、`str` 等各种形态下的环境标记，缺失时严格安全回退为 DRY RUN。
    - `_render_header_badge(is_dry: bool) -> str`: 渲染横幅右上角高亮胶囊。
    - `_render_subtitle_badge(is_dry: bool) -> str`: 渲染合约小标题行内标签。
    - `_render_table_env(is_dry: bool) -> str`: 渲染信息表格内的执行环境胶囊。
  - 重构 `_send_email_thread` 与 `send_async`：
    - 支持依据 `is_dry_run` 分流设置 `Subject` 与 Gmail 会话 `In-Reply-To` / `References`。
  - 重构所有模板输出方法：
    - `notify_trade_opened`: 融入头部徽章、卡片顶框、标题内联标签、表格执行环境行。
    - `notify_trade_closed`: 从入参 `trade` 字典中自动提取 `is_dry_run`，全面补齐头部徽章、卡片顶框、表格执行环境行。
    - `notify_l1_h1_breakeven_activated`: 从 `trade` 提取 `is_dry_run` 并补齐全部视觉标识。

## 3. 测试与验证策略
1. 编写独立单元测试 `test_option_seller_notifier_badges.py`：
   - 校验各种参数形态下的 `_is_dry_run` 鲁棒性。
   - 分别测试开仓、平仓、保本 3 类通知在 `is_dry_run=False` (实盘) 与 `is_dry_run=True` (模拟) 下 HTML 输出的关键词命中与样式属性。
   - 测试底层 `_send_email_thread` 生成的标准 MIME 报文其 Subject（经 base64 解码）与线程 ID 严格分流。
2. 回归运行现有的期权卖家全套单元测试，确保原有调用签名与 Mock 兼容性 100% 保持。
