# QuantData 期权异动订单邮件通知过滤实施方案

## 1. 需求背景与核心目标

当前从 QuantData 捕获到的期权异动订单（通过 Tampermonkey 脚本推送到 `/option_flow` 接口），只要用户在白名单配置中（如 `QDv3` / `QuantData`），所有异动订单都会生成 HTML 邮件卡片并直接发送 `Re: BBTAlerts` 邮件通知。为了有效降低高频与普通期权单的邮件噪音、将注意力集中在超大单与高置信度订单上，现对邮件通知实施分级精细化过滤：

1. **TSLA 标的**：所有期权订单均发送通知邮件（维持现状，含原有 SMS 联动）。
2. **限定股票池**：仅允许以下 10 个核心标的发邮件通知：
   `ORCL`, `NVDA`, `SPCX`, `GOOGL`, `META`, `TSM`, `AVGO`, `AMD`, `MU`, `MSFT`
   且必须满足以下两个准入条件之一：
   - **条件 (a)**: `ExecType` 为 `AUTO`（电子自动撮合）并且整单名义交易额 `premium >= $5M`；
   - **条件 (b)**: 期权单中存在任意一条腿的 `premium >= $15M`（无论 ExecType 为何）。
3. **发邮件之外的所有处理保持不变**：
   - 数据库落库存储 (`save_to_db` / `OptionFlow` 表) 100% 保持；
   - `BigFlowTracker.match_tracking_flows(message)` 追踪匹配 100% 保持；
   - 控制台与本地日志记录 (`print_n_log`) 100% 保持；
   - 桌面实时弹窗横幅 (`display_notif`) 100% 保持。

---

## 2. 方案设计与架构实现

### 2.1 过滤咽喉拦截点 (`option_flow.py`)
在 `bbt_signal_web/signal_app/option_flow.py` 中新增纯函数 `should_send_qd_option_flow_email(ticker, message, flow_data, user=None)`：

- **白名单标的集**：
  `QD_EMAIL_TARGET_TICKERS = {'ORCL', 'NVDA', 'SPCX', 'GOOGL', 'META', 'TSM', 'AVGO', 'AMD', 'MU', 'MSFT'}`
- **标的提取机制**：优先从 `flow_data` 结构化字段中获取，其次从 message 第一行（支持常规格式 `TSM Net:-$13.27` 与 Repeat 格式 `Repeat .TSLA261120C350 Net:$1.2 5`）解包获取并归一化为大写。
- **第一层守卫 (TSLA 豁免)**：若 `ticker == 'TSLA'`，无条件放行并发送邮件。
- **第二层守卫 (非白名单拦截)**：若 `ticker not in QD_EMAIL_TARGET_TICKERS`（如 AAPL, AMZN, BABA, SPY 等），直接拦截。
- **第三层守卫 (金额与执行类型判断)**：
  - 提取所有 Leg 的权利金金额（兼容 `flow_data` 明细与正则提取 `contract/premium/action`）；
  - 条件 (b)：若 `any(p >= 15.0 for p in leg_premiums)`，直接放行；
  - 条件 (a)：解析 `ExecType` 是否为 `AUTO`（如 `AUTO.SWEEP.D` 或结构化 `type == 'AUTO'`），且整单金额 `order_premium >= 5.0`，若满足则放行；
  - 若均不满足则拦截并输出审计日志。

---

## 3. 测试与验证策略

1. **单元测试矩阵 (`test_qd_option_flow_filter.py`)**：
   覆盖 17 组完整测试分支，包含实盘 TSM $13.27M CROSS 拦截、TSM $16.0M CROSS 放行、NVDA $6.2M AUTO 放行、NVDA $3.2M AUTO 拦截、TSLA 全量放行、AAPL 拦截、SPCX 远期风险逆转多腿放行、Repeat Flow 各场景等。
2. **端到端接口测试 (`test_option_flow_endpoint.py`)**：
   通过 Flask test client 向 `/option_flow` 发送真实 payload，验证 `save_to_db` 始终被触发，而 `send_to_gmail_html` 严格遵照新规则分支。
