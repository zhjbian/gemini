# Option Seller 独立线程邮件通知模块实施计划 (Implementation Plan)

## 1. 业务背景与目标
针对 BBT.AI Option Seller (期权卖方高胜率自动化交易系统)，建立高时效、异步非阻塞的专属邮件通知体系。
- **通知事件范围**：专注核心仓位生命周期（开仓、分批止盈 T1/T2、保本止损激活、硬止损 2.2x、时间强平 12:30 PST、交易员手动平仓）。
- **统一会话归拢 (Threading)**：所有通知采用固定邮件主题 `BBT_OptionSeller` 并指定固定 `In-Reply-To` / `References`，确保用户在 Gmail/手机端收件箱中归入单一连续会话 Thread，方便历史翻阅与上下文追踪。
- **零延迟性能保障**：邮件采用独立守护线程异步投递，绝对不阻塞毫秒级主交易与 10 秒风控盯盘循环。

---

## 2. 核心架构设计

### 2.1 邮件主题与会话规范
- **主题规范 (Subject)**: `BBT_OptionSeller` (固定恒定，完全归入单条 Gmail Thread)
- **会话识别头 (Threading Headers)**:
  - `In-Reply-To`: `<bbt-option-seller-thread@bbtrading.local>`
  - `References`: `<bbt-option-seller-thread@bbtrading.local>`

### 2.2 触发事件与视觉规范
1. **开仓通知 (`notify_trade_opened`)**:
   - 包含价差合约、单手预收权利金、双批次总金额、安全垫距离 (Buffer %)、Delta、策略模式与预定止盈/止损全景预案。
2. **平仓通知 (`notify_trade_closed`)**:
   - **分批止盈 T1 (40%)**: 翡翠绿卡片，通知已落袋金额，同时重点呈现 `🛡️ [Scheme A 保本风控已同步生效]`（通知第 2 批止损已移至开仓保本价）。
   - **深度止盈 T2 (75%)**: 胜利翡翠绿卡片，通知全额深度收割。
   - **保本平仓**: 天蓝色盾牌卡片，通知无伤离场、总体锁定正收益。
   - **硬止损 (2.2x)**: 醒目警示红卡片，说明突发波动触发 2.2x 纪律掐断，成功规避理论穿仓最大风险。
   - **时间强平 (12:30 PST)**: 纪律紫色卡片，严格执行不隔夜原则。

---

## 3. 涉及模块与代码变更

### 3.1 [NEW] `PyTools/option_seller/option_seller_notifier.py`
- 封装 `OptionSellerNotifier` 类。
- 实现 `_send_email_thread`（SMTP 发信）与 `send_async`（后台线程触发）。
- 实现 `notify_trade_opened(...)` 与 `notify_trade_closed(...)` 模版组装逻辑。

### 3.2 [MODIFY] `PyTools/option_seller/option_seller_manager.py`
- 引入 `OptionSellerNotifier`。
- 在 `open_trade()` 中，开仓成功后触发 `notify_trade_opened`。
- 在 `close_trade()` 中，结案与 DB 更新后触发 `notify_trade_closed`。

---

## 4. 验收与验证计划
1. **模块单元与网络测试**:
   - 编写独立脚本调用 `OptionSellerNotifier.notify_trade_opened`，验证 Gmail SMTP 鉴权与发信成功。
2. **统一会话 Thread 验证**:
   - 检查邮件 Subject 是否为 `BBT_OptionSeller`，验证手机与桌面端是否正常归拢为一个会话。
3. **日志追踪验证**:
   - 确认发信事件正常记录于 `/Users/zhijiebian/Documents/MyDoc/Finance/Current/Config/bbt_option_seller.log`。
