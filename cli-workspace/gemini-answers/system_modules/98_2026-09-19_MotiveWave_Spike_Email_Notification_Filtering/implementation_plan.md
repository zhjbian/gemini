# MotiveWave Spike 邮件通知过滤实施计划 (M02 演进)

## 1. 需求与背景

系统通过 MotiveWave Java Study 捕获实时价格异动（Spike），并通过 HTTP POST 推送到后端接口 `/order_flow_spike`（对应 [bbt_signal_web/signal_app/order_flow_spike.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_signal_web/signal_app/order_flow_spike.py)）。
原逻辑中：
- 仅限制 `ticker in ['SPY', 'QQQ', 'TSLA', 'NVDA']`，且 `volume >= SMS_MIN_VOLUME (5)`，`not is_prev_close`，在 RTH 时段外发邮件。

为降低低置信度、零散成交或前日收盘价归档单的噪音邮件干扰，现对 Spike 邮件通知实施精准分级过滤：
1. **TSLA 标的**：所有 Spike 均予以通知，与现有规则保持完全一致（`volume >= 5` 且目标价格不是前一日收盘价）。
2. **其他标的**：仅限 `SPY`, `QQQ`, `ORCL`, `NVDA`, `GOOGL`, `META`，且必须同时满足：
   - (a) Spike 目标价格不是前一日收盘价 (`not is_prev_close`)；
   - (b) Spike 股数必须达到或超过 30 股 (`volume >= 30`)。
3. **其他未列入标的**：直接拦截，不发送邮件通知。
4. **数据库落库与系统逻辑保真**：所有 Spike 无论是否发送邮件，均 100% 正常写入 MySQL 数据库 (`DbQuery.spike_mw_add`)，桌面系统通知保持原逻辑。

---

## 2. 实施方案与变更细节

### 2.1 修改文件
- **[bbt_signal_web/signal_app/order_flow_spike.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_signal_web/signal_app/order_flow_spike.py)**

### 2.2 核心逻辑实现
```python
    ticker_upper = (ticker or '').upper()
    other_spike_tickers = {'SPY', 'QQQ', 'ORCL', 'NVDA', 'GOOGL', 'META'}

    if ticker_upper == 'TSLA':
        eligible_spike = (volume >= SMS_MIN_VOLUME and not is_prev_close)
    elif ticker_upper in other_spike_tickers:
        eligible_spike = (volume >= 30 and not is_prev_close)
    else:
        eligible_spike = False

    if BBSms.should_send_for(user) and \
            BBDateTime.is_RTH_Now() and \
            eligible_spike:
        sms_msg = user + ":\n" + message
        html_msg = render_order_flow_spike_html(...)
        BBSms.send_to_gmail_html(html_msg)
```

---

## 3. 验证与回归矩阵

1. **TSLA 验证**：
   - TSLA, volume=5, not prev close -> 发送
   - TSLA, volume=4, not prev close -> 拦截
   - TSLA, volume=100, prev close -> 拦截
2. **白名单标的验证 (SPY, QQQ, ORCL, NVDA, GOOGL, META)**：
   - QQQ, volume=356000, not prev close -> 发送
   - QQQ, volume=29, not prev close -> 拦截
   - QQQ, volume=356000, prev close -> 拦截
   - ORCL, volume=30, not prev close -> 发送
   - NVDA, volume=25, not prev close -> 拦截
   - GOOGL, volume=30, not prev close -> 发送
   - META, volume=29, not prev close -> 拦截
3. **非白名单标的验证**：
   - AAPL, AMZN, TSM 等任意成交量 -> 拦截
4. **编译与代码健全性验证**：
   - `python3 -m py_compile` 语法无误。
