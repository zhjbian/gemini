# 期权卖家系统条件单「notes 列溢出导致布防失败」缺陷修复 验收报告 (Walkthrough)

## 1. 任务由来

用户报障："今天我把所有自动触发机制都 force dry run，但为什么没有一个触发？"
排查后确认两件事：

1. **触发侧**：force-dry 只影响"开成 DRY 还是 LIVE"，不参与"是否触发"；当天没有任何自动触发
   （唯一命中的 ② QuantPivot 边界反向是**布防型**机制，布防的 3 张条件单在价格穿越前全部被撤销）。
2. **一个真实缺陷**：③ 平衡日边界机制当天**命中 6 次、6 次布防全部失败**。
   本交付修复该缺陷。

## 2. 缺陷机理

```text
2026-09-16 07:40:47 / 07:46:10 / 08:16:07 / 09:45:52 / 10:35:29 / 10:56:21
[AUTO-CYCLE] 3. AUTO_BALANCED_DAY_BOUNDARY 判定异常：
  (pymysql.err.DataError) (1406, "Data too long for column 'notes' at row 1")
  [parameters: {... 'trigger_symbol': 'SPY', 'trigger_condition': 'GTE',
                 'trigger_price': Decimal('761.16'), 'spread_action': 'BEARISH' ...}]
```

- `order_flow_option_seller_conditional_orders.notes` = `VARCHAR(256)`（`models.py: db.String(256)`）；
- 机制 ③ 生成的说明串（含 L1/H1 锚位、Moat、L0 掩码、Gamma wall、Saty/QP 级别、fallback 等）超过 256 字符；
- MySQL 以 `1406 Data too long` 拒绝 INSERT ⇒ **条件单未落库** ⇒ 既不显示在页面，也不可能被触发；
- 表现与"机制没反应"无法区分，只有 AUTO-CYCLE 的一行"判定异常"（INFO 级）提示。

## 3. 修改内容

| 文件 | 变更 |
| :--- | :--- |
| `db_query_module/db_query_option_seller.py` | 新增 `CONDITIONAL_ORDER_NOTES_MAX = 256`；`option_seller_conditional_order_create()` 作为**唯一写入咽喉**按列宽截断（`…[:253] + '...'`） |
| `option_seller/option_seller_manager.py` | `add_conditional_order()` 在**追加 `[Groups=]/[TP=]` 之前**按 `256 − 后缀长度` 预算截断业务说明串，并 WARNING 留痕（元数据供触发侧反解，绝不能截） |
| `option_seller/test_conditional_order_notes_limit.py` | 新增 3 条回归用例 |

## 4. 验证

```bash
PYTHONPATH=PyTools:bbt_data_web /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  -m unittest test_conditional_order_notes_limit
```

```text
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、13 个数据库写方法
...
----------------------------------------------------------------------
Ran 3 tests in 0.312s
OK
```

| 用例 | 断言 |
| :--- | :--- |
| `test_long_notes_are_truncated_to_column_width` | 复刻实盘超长串（复刻 ③ 机制形态）→ 落库长度 ≤ 256、含 `...`、且**以 `[Groups=1] [TP=CONSERVATIVE]` 结尾** |
| `test_short_notes_are_untouched` | 正常长度串原样保存（前缀不变、元数据在尾） |
| `test_db_choke_point_truncates_for_any_caller` | 写入咽喉存在兜底截断，且常量与模型列宽（256）一致 |

手工验证（隔离守卫下）：
```text
notes len: 264 → saved notes len: 256 <= 256: True
meta kept: [Groups=1] True, [TP=CONSERVATIVE] True
```

全量回归：期权卖家套件全量执行，仅剩既有、与本次改动无交集的
`test_absorption_reversal_module` 门槛样本失败。

## 5. 用户问题的完整答复（已核实，可直接对照）

| 机制 | 当天结果 | 原因（原文摘录） |
| :--- | :--- | :--- |
| ① 5分钟综合信号 | 33 未命中 / 19 跳过 | `Insufficient confluence score (Bull=10, Bear=3, minimum threshold=55)` |
| ② QuantPivot边界反向 | **3 命中** / 9 未命中 / 39 跳过 | 命中即**布防条件单**：#66 07:21(SPY≤757.09)、#67 07:55(SPY≥761.74)、#68 10:05(SPY≤757.09)；`triggered_at` 全 NULL |
| ③ 平衡日边界 | **6 判定异常**（缺陷）/ 24 未命中 | `Data too long for column 'notes'`（本次修复）；未命中原因「无平衡日边界命中（或方向被 L0 掩码）」 |
| ④ 趋势日极限终点 | 30 未命中 | 07:00 PST 前 `counter-trend channel inactive before 07:00`；之后 `No counter-trend terminal or range-boundary setup qualified` |
| ⑤ ES盘前大单开盘回调 | 30 未命中 | 无盘前大单上下文 |
| ⑥ 洗盘反转-双向 | 30 未命中 | 未检出洗盘反转 |
| ⑦ 吸收反转-双向 | 30 未命中 | **机制未启用（`OS_AUTO_ABSORPTION_REVERSAL` 未开启）** + 候选得分 −1/5（需 4）|

三张已布防条件单的终局：

| 条件单 | 布防 | 触发价 | 布防时 SPY | 距离 | 终局 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| #66 | 07:21:06 | ≤ 757.09 | 759.32 | −2.23 | 07:53:30 `cancel_reason=MANUAL` |
| #67 | 07:55:46 | ≥ 761.74 | 759.79 | +1.95 | 09:56:01 `cancel_reason=MANUAL` |
| #68 | 10:05:42 | ≤ 757.09 | 759.44 | −2.35 | 11:00:02 `cancel_reason=TIME_CUTOFF_1100` |

⇒ 三次都**没有等到价格穿越**（`triggered_at` 全 NULL），因此 0 次触发；
当日 8 笔交易（#282–#289）全为 `MANUAL_UI_SCAN` 手动单，`is_dry_run=1` 记录数为 0。

**force-dry 的覆盖范围（已核对代码）**：自动布防单触发时 `trigger` 记为
`AUTO_QUANT_PIVOT_BOUNDARY`（②，`option_seller_manager.py:4391`），**在 `FORCE_DRY_CHOICES` 清单内**，
即：三张单若触发，开出来的会是 DRY-RUN 单（你的 force-dry 设置对它们是生效的）。

## 6. 后续可选项（未自动执行）

1. 若希望 ⑦ 吸收反转参与：需在启动 5005 的环境变量中设 `OS_AUTO_ABSORPTION_REVERSAL=1`
   并重启服务（该机制默认关闭；在 Force Dry 中勾选它并不等于启用它）。
2. 建议页面在「Force Dry 触发」选择区标注每个机制的**启用状态**（未启用时提示），
   以避免"选了却没反应"的再次误判 —— 这属于 UI 改进，可另行排期。
3. 若希望 ③ 平衡日边界不再依赖手动/截断撤单：可评估延长其布防窗口（当前 11:00 PST 截断），
   但该截断是 0DTE 时段纪律，建议保持不变。

## 7. 回滚

`★ 2026-09-16` 注释可定位两处改动；回滚即删除 `CONDITIONAL_ORDER_NOTES_MAX` 与两处截断逻辑，
恢复直接写入 `notes` 的旧行为（会重新出现 1406 布防失败）。
