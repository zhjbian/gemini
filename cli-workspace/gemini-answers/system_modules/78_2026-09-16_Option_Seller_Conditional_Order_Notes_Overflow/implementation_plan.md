# 期权卖家系统条件单「notes 列溢出导致布防失败」缺陷修复 实施计划 (Plan)

## 1. 问题（用户报障）

> 今天我把所有自动触发机制都 force dry run，但为什么没有一个触发？

排查结论分两部分：**(A) 触发侧的真实原因** 与 **(B) 其中暴露的一个真实缺陷**。

### 1.1 触发侧事实（2026-09-16 全天 AUTO-CYCLE 日志 + 条件单表）

| 机制 | 未命中 | 跳过 | 命中 | 判定异常 |
| :--- | ---: | ---: | ---: | ---: |
| ① 5分钟综合信号 (AUTO_5M_SYNTHESIS) | 33 | 19 | 0 | 0 |
| ② QuantPivot边界反向 (AUTO_QUANT_PIVOT_BOUNDARY) | 9 | 39 | **3** | 0 |
| ③ 平衡日边界 (AUTO_BALANCED_DAY_BOUNDARY) | 24 | 19 | 0 | **6** |
| ④ 趋势日极限终点 (AUTO_TREND_DAY_EXTREME) | 30 | 19 | 0 | 0 |
| ⑤ ES盘前大单开盘回调 (AUTO_PM_BIG_TRADE_PULLBACK) | 30 | 19 | 0 | 0 |
| ⑥ 洗盘反转-双向 (AUTO_WASHOUT_REVERSAL) | 30 | 17 | 0 | 0 |
| ⑦ 吸收反转-双向 (AUTO_ABSORPTION_REVERSAL) | 30 | 16 | 0 | 0 |

- **force-dry 不改变触发判定**：它只决定"触发后开成 DRY-RUN 还是 LIVE"，
  因此"没有触发" ⇒ 也不会有任何 DRY 单（当天 `is_dry_run=1` 记录数 = 0）。
- ② 命中的动作是**布防条件单**（ARMED），不是即时开仓：当天布防 #66（SPY ≤757.09）、
  #67（SPY ≥761.74）、#68（SPY ≤757.09），三张单 `triggered_at` 全为 NULL：
  #66 于 07:53:30 被手动取消（`cancel_reason=MANUAL`）、#67 于 09:56:01 手动取消、
  #68 于 11:00:02 被 11:00 PST 时段截断自动取消（`TIME_CUTOFF_1100`）。
- 当日 8 笔交易（#282–#289）`trigger` 全为 `MANUAL_UI_SCAN`（手动），无自动单。

### 1.2 暴露的真实缺陷：③ 机制命中 6 次，6 次布防全部失败

```text
2026-09-16 07:40:47 / 07:46:10 / 08:16:07 / 09:45:52 / 10:35:29 / 10:56:21
[AUTO-CYCLE] 3. AUTO_BALANCED_DAY_BOUNDARY 判定异常：
  (pymysql.err.DataError) (1406, "Data too long for column 'notes' at row 1")
  [parameters: {... 'trigger_symbol': 'SPY', 'trigger_condition': 'GTE', 'trigger_price': 761.16,
                 'spread_action': 'BEARISH' ...}]
```

即：**该机制已经判定命中并尝试布防上轨条件单（SPY GTE 761.16 BEARISH），
但说明串超过 `order_flow_option_seller_conditional_orders.notes` 的列宽 `VARCHAR(256)`，
MySQL 直接拒绝 INSERT** ⇒ 条件单未落库 ⇒ 不可能触发，日志只留下"判定异常"。
当天条件单序号恰好跳过这些时刻（只有 #66/#67/#68），与 6 次失败一致。

## 2. 修复方案

1. **写入咽喉兜底截断**（`DbQuery.option_seller_conditional_order_create`）：
   新增类常量 `CONDITIONAL_ORDER_NOTES_MAX = 256`，写入前统一按列宽截断（保留语义前缀 + `...` 标记）。
   任何调用方（含未来新增机制）都不会再因说明串过长而丢单。
2. **元数据不可被截掉**（`OptionSellerManager.add_conditional_order`）：
   `[Groups=]/[TP=]` 在触发侧会被反解（`notes_str.split('Groups=')` / `split('TP=')`），
   因此截断必须发生在**追加元数据之前**（按 `256 − len(后缀)` 预算截断业务说明串），
   并对超长情形记 WARNING 留痕。
3. 语义不变：截断只影响落库的**说明文本**，不影响触发价格/方向/档位/风控参数。

## 3. 涉及文件

| 文件 | 变更 |
| :--- | :--- |
| `bbt_data_web/db_query_module/db_query_option_seller.py` | `CONDITIONAL_ORDER_NOTES_MAX` + 写入前截断 |
| `PyTools/option_seller/option_seller_manager.py` | `add_conditional_order` 按预算截断（保留 `[Groups=]/[TP=]`）+ WARNING 留痕 |
| `PyTools/option_seller/test_conditional_order_notes_limit.py` | 新增 3 条回归用例 |

## 4. 测试与验证策略

1. 超长说明串 → 落库长度 ≤ 256 且以 `[Groups=…] [TP=…]` 结尾（元数据未被截掉）；
2. 正常长度说明串 → 原样保存（无多余改动）；
3. 写入咽喉常量与模型列宽一致（`models.py: db.String(256)`），且代码中确实存在兜底截断。
4. 全量回归期权卖家测试套件。

## 5. 附：用户问题中"为什么没触发"的完整答复要点（已核实）

- force-dry ≠ 关闭触发；今天没有触发，故没有 DRY 单；
- 唯一命中的 ② 是**布防型机制**，三张条件单都在价格穿越前被撤销（2 手动 / 1 截断）；
- ③ 命中 6 次但布防失败（本次已修复）；
- ⑦ 吸收反转机制**未启用**：需环境变量 `OS_AUTO_ABSORPTION_REVERSAL=1`（默认关闭），
  在 Force Dry 里勾选它并不等于启用它；
- ① 的未命中原因明确：`Insufficient confluence score (Bull=10, Bear=3, minimum threshold=55)`；
  ②④ 在 07:00 PST 前被时段门禁拦截（`counter-trend channel inactive before 07:00`）后全天无合格 setup；
  ⑤ 无盘前大单上下文；⑥ 未检出洗盘反转；
  所有机制的"跳过"多为 `可用方向为空（L0-B/C/F 掩码）`；自动循环在 11:25 后随窗口结束停止。
