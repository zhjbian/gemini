# 卖家系统：机制 ③ 盘中取数缺列修复（price_at_row 实时恒空）实施计划

- **日期**：2026-09-14
- **模块**：Option Seller 机制 ③「平衡日边界」（`AUTO_BALANCED_DAY_BOUNDARY`）取数链路 + 当日高低点探针
- **归档目录**：`49_2026-09-14_Price_At_Row_Live_Gap_Fix`
- **技术栈**：Python 3.11 / MySQL `bb_trade`（`order_flow_signals`、`smashelito_analysis`）/ Flask API + Jinja2（`bbt_data_web`，127.0.0.1:5005）/ headless Chrome DOM 断言 / 规则手册五部分级

---

## 1. 背景与问题（用户提问引出）

页面「当日高低点自动触发机制检测」中机制 ③ 显示：

```
平衡日边界 · NOT_EVALUATED ｜ ③ 该时点无 order_flow_signals 行 ⇒ 无法取数
```

排查发现**提示措辞与真实原因不符**，且背后是一个**生产级取数缺陷**：

| 检查项 | 实测（2026-09-14 盘中） |
|---|---|
| 该时点的 `order_flow_signals` 行 | **存在**（当日 17 行，06:35→07:55，含 07:05） |
| `price_at_row` 为空的行 | **17 / 17（100% NULL）** |
| 对照：回填过的 2026-09-11 | 79 / 79 有值 |
| 对照：09-08 / 09-09 / 09-10 | 77 / 73 / 76（共 79 行）有值 |

根因链：

1. `balanced_day_data.load_balanced_day_context()` 按 `price_at_row is not None` 过滤行 ⇒ 全空 ⇒ 返回 `None`；
2. `price_at_row` 的**唯一写入方**是离线批处理 `order_flow_analysis/backfill_order_flow_signals.py::_sw_fields()`（从 `recent_micro_5m` 摊平）；
3. **实时 5 分钟写库路径 `order_flow_analysis/order_flow_sentinel.py` 从不写该列**，只做「若 `baseline_dict` 有值才继承」⇒ 新槽位首次落库即 NULL；
4. **`launchd` / `daily_jobs` 无任何定时回填** ⇒ 每个交易日的实时行在当天一直是空，只有事后手工回填过的日期才有值；
5. 影响不止探针：机制 ③ 的生产取数走**同一个** `load_balanced_day_context`，`evaluate_balanced_day_channel()` 中 `if not ctx or not ctx.get("row"): return None` ⇒ **盘中 ③ 永远静默不出信号**。此前 12 个交易日的标定/影子结论用的都是**回填后**的数据，故未暴露。

## 2. 实施目标

| 目标 | 交付 |
|---|---|
| 读侧立即恢复 ③ 盘中可用 | `balanced_day_data.row_price()`：`price_at_row` → 兜底 `quantitative_metrics.es_price`（唯一口径入口） |
| 实盘 / 影子同源 | `balanced_day_shadow.py` 复用同一 `row_price()`（此前两处各写一份过滤逻辑） |
| 写侧根治，实时数据自洽 | `order_flow_sentinel.py` 落库时补齐 `sig.price_at_row`（不覆盖既有非空值） |
| 失败原因可见、不再误导 | `load_balanced_day_context(..., diag=...)` 回填 `{rows, rows_with_price, price_source, reason}`；探针区分「无行 / 价格列全空 / DB 异常」并新增「行价格来源」判据行 |
| 文档与代码一致 | 手册 §3.1.4.1.2 取数口径表更新（价格序列 / 当日高低 / 开盘锚 / 关键位族）+ MD 补记；顺带修一处既有关键位族滞后描述 |

## 3. 关键设计与依据

### 3.1 为何兜底 `es_price` 是**口径不变**的

| 依据 | 实测 |
|---|---|
| 逐行等值 | 2026-09-11 抽样 6 行 `price_at_row` 与 `quantitative_metrics.es_price` **diff = 0.0** |
| 尺度一致 | 两者同为 **ES 点位**（机制内现价 / 极值 / 关键位 / 容差全部 ES 口径） |
| 覆盖率更高 | `es_price` 78/79 vs `price_at_row` 73~79（09-08…09-11） |
| 语义 | 同一行的同一量（`price_at_row` 本就是回填时从同一份 tick/价源摊平得到） |

### 3.2 写侧取值

`sig.price_at_row = float(quant_metrics['es_price'])`，仅在 `price_at_row is None` 时写入（保留回填/历史权威值）。

### 3.3 改动清单

| 层 | 文件 | 改动 |
|---|---|---|
| 取数（读侧） | `PyTools/option_seller/balanced_day_data.py` | 新增 `PRICE_FIELD_ORDER` / `row_price()`；`load_balanced_day_context(..., diag=None)` 支持诊断回填；上下文新增 `price_source` |
| 影子 | `PyTools/option_seller/balanced_day_shadow.py` | 改用 `row_price()`（实盘/影子同源） |
| 探针 | `PyTools/option_seller/intraday_probe.py` | 失败原因三分（`db_error` / `no_rows` / `no_price_column`）+ 新增「取数口径：行价格来源」判据行 |
| 写库（写侧） | `PyTools/order_flow_analysis/order_flow_sentinel.py` | 落库时补齐 `price_at_row` |
| 文档 | 手册 HTML + MD | §3.1.4.1.2 取数口径表（价格序列 / 当日高低 / 开盘锚 / 关键位族）与 §1.2 列填充注记 |

## 4. 验证方案

1. **A/B 新旧取数对比**（历史日必须**逐字段完全一致**；当日 NULL 行由「剔除」变「可判定」）
2. **探针 API 实调**（③ 由 `NOT_EVALUATED` 变为真实评分结论，且显示价格来源）
3. **写侧生效确认**（下一个 5 分钟槽位的新行 `price_at_row` 非空）
4. **回归**：`option_seller` 测试套件 + 影子 CLI（历史日结论不变）
5. **只读性**：除写侧落库外无其它 DB 写入；不触发任何下单路径

## 5. 风险与回退

- **风险**：兜底值若与主列**不同尺度**会造成 ES/SPY 混比 ⇒ 已用逐行等值 + 尺度核对锁定；写侧仅在主列为空时写入，不覆盖历史权威值。
- **回退**：`/tmp/bbt_pricefix_backup_081305/`（四文件术前副本）；读侧可仅删 `row_price()` 的第二分支恢复旧行为。
- **注意**：`order_flow_sentinel.py` 是实时路径，**不得在盘中为测试目的重跑**（会重写当日行并触发自动开仓编排）；本轮只做静态校验 + 观察下一槽位真实落库。
