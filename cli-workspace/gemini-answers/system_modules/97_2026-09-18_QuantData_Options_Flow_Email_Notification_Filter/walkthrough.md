# QuantData 期权异动订单邮件通知过滤交付与验收报告

## 1. 概述与核心变更

本次迭代针对从 QuantData 捕获到的期权异动订单的邮件通知发送机制实施了精准的分级过滤拦截，全面解决了普通大单（如 TSM $13.27M CROSS 订单）频繁发送邮件干扰的问题，同时严格保留了 TSLA 全量通知、核心标的高置信度订单（AUTO >= $5M）及超大单腿（任意腿 >= $15M）的有效覆盖。

### 核心变更点
1. **修改核心路由模块**：
   - 文件：[bbt_signal_web/signal_app/option_flow.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_signal_web/signal_app/option_flow.py)
   - 新增 `QD_EMAIL_TARGET_TICKERS = {'ORCL', 'NVDA', 'SPCX', 'GOOGL', 'META', 'TSM', 'AVGO', 'AMD', 'MU', 'MSFT'}` 白名单定义。
   - 新增纯函数 `should_send_qd_option_flow_email(ticker, message, flow_data=None, user=None)`，统一对 QuantData 异动订单（含单腿、多腿复合单及 Repeat Flow）进行方向性与金额维度的邮件过滤。
   - 在 `handle_option_flow()` 中将邮件外发入口收归守卫，不满足条件的期权单静默拦截并输出 INFO 日志，数据库落库与桌面弹窗 100% 保持现状。

---

## 2. 规则判断决策流

针对进入系统的每一笔 QuantData 订单：
1. **标的归一化与识别**：从结构化字段或报文前缀解析标的代码。
2. **TSLA 规则 (1)**：若标的为 `TSLA`，立即放行发信（原有 TSLA 短信提醒同样触发）。
3. **股票池准入**：若标的不在 `ORCL`, `NVDA`, `SPCX`, `GOOGL`, `META`, `TSM`, `AVGO`, `AMD`, `MU`, `MSFT` 中，直接拦截不发邮件。
4. **双重条件裁决 (2)**：
   - **条件 (b) 单腿 >= $15M**：无论订单执行类型（CROSS, TIED, AUCT, AUTO 等），只要存在单腿金额达到 $15M，即刻判定为超大机构单，放行发信。
   - **条件 (a) AUTO 且 >= $5M**：若执行类型属于电子自动市价撮合（`ExecType` 前缀为 `AUTO`，如 `AUTO.SWEEP.D` 或 `AUTO.BLOCK.D`），且整单名义交易额达到 $5M，放行发信。
   - 其余情况（如 CROSS / AUCT 且单腿未达 $15M，或 AUTO 金额低于 $5M）全量拦截，不触发邮件。

---

## 3. 验证与测试结果

### 3.1 单元测试矩阵 (`test_qd_option_flow_filter.py`)
测试脚本完整覆盖 17 项严苛用例，执行结果如下：

```
==================================================
Running tests for should_send_qd_option_flow_email
==================================================
[PASS] Case 1: User Screenshot - TSM -$13.27M CROSS.BLOCK.N -> Result: False, Expected: False
[PASS] Case 2: TSM -$16.0M CROSS.BLOCK.N (Leg >= 15M) -> Result: True, Expected: True
[PASS] Case 3: NVDA +$6.2M AUTO.SWEEP.D (AUTO >= 5M) -> Result: True, Expected: True
[PASS] Case 4: NVDA +$3.2M AUTO.SWEEP.D (AUTO < 5M) -> Result: False, Expected: False
[PASS] Case 5: TSLA $0.8M CROSS.BLOCK.N (TSLA always notifies) -> Result: True, Expected: True
[PASS] Case 6: AAPL $20M AUTO.SWEEP.D (Not in target tickers) -> Result: False, Expected: False
[PASS] Case 7: SPCX Multi-Leg TIED_MULTI_CROSS (Leg >= 15M) -> Result: True, Expected: True
[PASS] Case 8: SPCX Multi-Leg AUTO (Total >= 5M) -> Result: True, Expected: True
[PASS] Case 9: Repeat Flow TSLA (always notify) -> Result: True, Expected: True
[PASS] Case 10: Repeat Flow AMD $6.0M AUTO -> Result: True, Expected: True
[PASS] Case 11: Repeat Flow AMD $2.0M AUTO -> Result: False, Expected: False
[PASS] Case 12a: ORCL $5.5M AUTO -> True -> Result: True, Expected: True
[PASS] Case 12b: MSFT $18.0M CROSS -> True (Leg >= 15M) -> Result: True, Expected: True
[PASS] Case 12c: META $12.0M CROSS -> False (CROSS < 15M) -> Result: False, Expected: False
[PASS] Case 12d: AVGO $7.0M AUTO -> True -> Result: True, Expected: True
[PASS] Case 12e: MU $5.0M AUTO -> True -> Result: True, Expected: True
[PASS] Case 12f: GOOGL $4.9M AUTO -> False -> Result: False, Expected: False
--------------------------------------------------
>>> ALL TESTS PASSED! (100% SUCCESS)
```

### 3.2 端到端接口集成测试 (`test_option_flow_endpoint.py`)
针对实际 Flask Webhook 路由 `/option_flow` 发起 POST 请求校验：
- **测试 A（用户截图 TSM -$13.27M CROSS）**：`save_to_db` 正常调用，邮件外发被成功拦截（0 次 SMTP 发送）。
- **测试 B（NVDA +$6.2M AUTO）**：`save_to_db` 正常调用，邮件外发成功触发。
- **测试 C（TSLA $0.8M CROSS）**：`save_to_db` 正常调用，邮件外发成功触发。
- **全链路测试结果**：`>>> All Endpoint Integration Tests Passed!`。

---

## 4. 结论与交付确认

代码改动已就绪且经过完备的单元测试与端到端测试验证，严格保证了非邮件通知流程（数据库存储、大单追踪、桌面弹窗等）无任何逻辑侵入或退化。
