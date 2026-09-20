# MotiveWave Spike 邮件通知过滤交付与验收报告

## 1. 概述与核心变更

本次迭代针对从 MotiveWave 捕获并推送到 `/order_flow_spike` 接口的异动价格 Spike 邮件通知发送机制进行了精准重构与分级过滤。通过收紧其他股票的准入标的、过滤前一日收盘价成交以及引入 30 股的最小过滤阈值，有效消除零散琐碎的低信噪比邮件干扰，同时严格保持 TSLA 的全量通知能力与底层数据库落库一致性。

### 核心变更点
1. **核心文件**：[bbt_signal_web/signal_app/order_flow_spike.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_signal_web/signal_app/order_flow_spike.py)
2. **标的分级与准入条件重构**：
   - **TSLA 规则**：维持既有规则不变，满足 `volume >= SMS_MIN_VOLUME (5)` 且非前日收盘价 (`not is_prev_close`) 即外发邮件通知。
   - **重点标的白名单**：其他标的仅开放 `SPY`, `QQQ`, `ORCL`, `NVDA`, `GOOGL`, `META` 6 个核心标的，且必须同时满足：
     - (a) Spike 价格不是前一日收盘价 (`not is_prev_close`)；
     - (b) 成交量达到或超过 30 股 (`volume >= 30`)。
   - **其余所有标的**：直接拦截，不发送邮件通知。
3. **数据链路全保真**：
   - 数据库记录 `DbQuery.spike_mw_add()` 无论邮件是否发送均 100% 正常入库。
   - 桌面通知 `BBTSignalUtil.display_notif` 保持既有逻辑。

---

## 2. 规则判断决策矩阵

| 标的代码 | 成交股数 (Volume) | 价格属性 (is_prev_close) | 是否在 RTH | 判定结果 (是否发送邮件) | 规则依据 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TSLA** | 10 股 | 否 (False) | 是 (True) | **发送 (True)** | TSLA 保持现状：volume >= 5 且非前收 |
| **TSLA** | 5 股 | 否 (False) | 是 (True) | **发送 (True)** | 边界用例：刚好达到最小 5 股 |
| **TSLA** | 4 股 | 否 (False) | 是 (True) | **拦截 (False)** | 成交量未达标 |
| **TSLA** | 100 股 | 是 (True) | 是 (True) | **拦截 (False)** | 前日收盘价归档单拦截 |
| **QQQ** | 356,000 股 | 否 (False) | 是 (True) | **发送 (True)** | 满足核心标的 + volume >= 30 + 非前收 |
| **QQQ** | 29 股 | 否 (False) | 是 (True) | **拦截 (False)** | 成交量未达 30 股门槛 |
| **QQQ** | 356,000 股 | 是 (True) | 是 (True) | **拦截 (False)** | 前日收盘价归档单拦截 |
| **ORCL** | 30 股 | 否 (False) | 是 (True) | **发送 (True)** | 边界用例：刚好达到 30 股 |
| **NVDA** | 50 股 | 否 (False) | 是 (True) | **发送 (True)** | 满足核心标的准入 |
| **NVDA** | 25 股 | 否 (False) | 是 (True) | **拦截 (False)** | 成交量未达 30 股门槛 |
| **GOOGL** | 30 股 | 否 (False) | 是 (True) | **发送 (True)** | 核心标的放行 |
| **META** | 29 股 | 否 (False) | 是 (True) | **拦截 (False)** | 成交量未达 30 股门槛 |
| **AAPL** | 500 股 | 否 (False) | 是 (True) | **拦截 (False)** | 不在白名单标的池中 |
| **TSM** | 100 股 | 否 (False) | 是 (True) | **拦截 (False)** | 不在白名单标的池中 |

---

## 3. 测试与验证

### 3.1 语法健全性测试
执行 Python 语法静态编译校验：
```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m py_compile /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_signal_web/signal_app/order_flow_spike.py
```
- 结果：`exit code 0`，代码语法无任何错误。

### 3.2 21 组严苛用例全量覆盖测试
编写单元测试脚本测试 `TSLA`、白名单标的（`SPY`, `QQQ`, `ORCL`, `NVDA`, `GOOGL`, `META`）边界值以及非白名单标的（`AAPL`, `AMZN`, `TSM`）：
- 结果：`All 21 test cases passed! (100% Success)`
