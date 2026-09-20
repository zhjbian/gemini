# 卖家系统：机制 ③ 盘中取数缺列修复验收报告

- **日期**：2026-09-14
- **模块**：Option Seller 机制 ③「平衡日边界」取数链路（`price_at_row` 实时恒空）+ 当日高低点探针
- **归档目录**：`49_2026-09-14_Price_At_Row_Live_Gap_Fix`
- **技术栈**：Python 3.11 / MySQL `bb_trade`（只读诊断 + 写侧落库列补齐）/ Flask API + Jinja2（bbt_data_web）/ 规则手册五部分级 / A-B 取数对照

---

## 1. 结论先行

| 问题 | 结论 |
|---|---|
| 页面提示 `③ 该时点无 order_flow_signals 行 ⇒ 无法取数` | **措辞错误**：行是存在的（当日 17 行）；真实原因是 **`price_at_row` 100% 为 NULL**，取数函数过滤后返回 `None` |
| 根因 | `price_at_row` 的**唯一写入方**是离线批处理 backfill；**实时 5m 写库路径从不写该列**，且无任何定时回填 |
| 影响面（比一条提示严重） | 机制 ③ 的生产取数走同一函数 ⇒ **盘中永远静默不出信号**；此前 12 交易日的标定结论都建立在**回填后**数据上，故未暴露 |
| 修复 | **读侧兜底**（`price_at_row` → `quantitative_metrics.es_price`，逐行等值、同为 ES 点位）+ **写侧补齐**（sentinel 落库写 `price_at_row`）+ **探针失败原因三分** |
| 结果 | ③ 由 `NOT_EVALUATED` 变为真实结论（今日 4 个检测点均 `QUALIFIED`）；写侧已在 **08:15 槽位实测生效** |

## 2. 证据

### 2.1 缺列实测（修复前）

```
2026-09-14  order_flow_signals 17 行（06:35→07:55）   price_at_row 非空 **0 / 17**
2026-09-11  79 行                                      非空 79 / 79   ← 当天 19:27 回填过
2026-09-08/09/10  79 行                                非空 77 / 73 / 76
es_price（quantitative_metrics）覆盖率：09-08…09-11 均 78/79 ＞ price_at_row
```

写入方全仓检索：`price_at_row` 仅出现在 `models.py`（列定义）、`backfill_order_flow_signals.py`（唯一写入）、`order_flow_direction_gate.py` / `adam_signal_deepdive.py`（读取）；实时路径 `order_flow_sentinel.py` **无写入**。`launchd` / `daily_jobs` 内**无定时 backfill**。

### 2.2 兜底等值性（口径不变的依据）

```
2026-09-11 逐行对照（price_at_row vs quantitative_metrics.es_price）：
  06:35 7675.50 / 7675.50   06:40 7673.50 / 7673.50   06:45 7672.25 / 7672.25
  06:50 7667.75 / 7667.75   06:55 7668.75 / 7668.75   07:00 7681.00 / 7681.00
  平均绝对差 = 0.000
```

### 2.3 A/B 新旧取数对照（关键回归）

| 日期 | 时间 | 旧（仅 `price_at_row`） | 新（含兜底） | 一致性 |
|---|---|---|---|---|
| 09-08 | 11:00 | rows=53 price=7695.25 | rows=53 price=7695.25 | **逐字段一致**（src=price_at_row） |
| 09-09 | 11:00 | rows=53 price=7652.50 | rows=53 price=7652.50 | 一致 |
| 09-10 | 11:00 | rows=54 price=7602.25 | rows=54 price=7602.25 | 一致 |
| 09-11 | 11:00 | rows=54 price=7674.75 | rows=54 price=7674.75 | 一致 |
| 09-11 | 11:30 | rows=60 price=7672.00 | rows=60 price=7672.00 | 一致 |
| **09-14** | 07:05 / 07:55 | **None** | **ctx**（rows=7 / 17，src=es_price） | **由「不可判定」变「可判定」** |

⇒ 历史日（已回填）**结果完全不变**；仅当日空列行由「被剔除」变「参与判定」。

### 2.4 探针 API 实调（同一天、同一批检测点）

| 检测点 | 修复前 | 修复后 |
|---|---|---|
| HIGH 07:05 | `NOT_EVALUATED` · 该时点无 order_flow_signals 行 | **`QUALIFIED`** score=82.5 · BEARISH · 组数 1 · 路径 R |
| HIGH 07:10 | `NOT_EVALUATED` | **`QUALIFIED`** score=82.5 · BEARISH |
| LOW 07:40 | `NOT_EVALUATED` | **`QUALIFIED`** score=77.5 · BEARISH |
| LOW 07:55 | `NOT_EVALUATED` | **`QUALIFIED`** score=77.5 · BEARISH |

新增判据行同步可见：`取数口径：行价格来源 = es_price（行数 7 / 窗口 7）[✓]`（旧文案不区分原因，现已按 `no_rows` / `no_price_column` / `db_error` 三分）。

### 2.5 写侧生效（实盘实测，非模拟）

```
sentinel 文件修改时间            2026-09-14 08:14:53
08:10 槽位（改前落库 08:11:27）  price_at_row = NULL
08:15 槽位（改后落库 08:16:16）  price_at_row = 7669.25  ← 等于该行 es_price（7669.25）
```

⇒ 写侧修复在下一次 5 分钟槽位即生效，实时行此后自带行价格。

### 2.6 回归与只读性

| 检查 | 结果 |
|---|---|
| `py_compile`（4 个改动文件） | OK |
| `option_seller` 测试套件 | `test_isolation` 守卫通过；`force_dry_degrade` / `intraday_probe` / `journal_filter_catalog` / `l1_h1_breakeven_stop` 全 **OK** |
| 影子 CLI 历史日 | `balanced_day_shadow.py --date 2026-09-11 --scorer v2` ⇒ 18 命中 / 假信号 0 ⇒ **与修复前一致** |
| 影子 CLI 当日 | `--date 2026-09-14` ⇒ 17 命中 / 假信号 1（6%）⇒ 当日首次**可评分**（此前无上下文） |
| HTTP | `/bbt_option_seller` 200 · `/api/option_seller/intraday_extremes_probe` 200 |
| 副作用 | 除**写侧落库补齐一列**外无其它 DB 写入；**未重跑 sentinel**（避免盘中重写当日行与触发自动开仓编排）；未下单 |

## 3. 改动清单

| 层 | 文件 | 改动 |
|---|---|---|
| 取数（读侧） | `PyTools/option_seller/balanced_day_data.py` | 新增 `PRICE_FIELD_ORDER` / `row_price()`；`load_balanced_day_context(..., diag=None)` 回填 `{rows, rows_with_price, price_source, reason}`；上下文新增 `price_source` |
| 影子 | `PyTools/option_seller/balanced_day_shadow.py` | 改用 `row_price()`（实盘 / 影子同源；此前两处各一份过滤逻辑） |
| 探针 | `PyTools/option_seller/intraday_probe.py` | 失败原因三分 + 新增「取数口径：行价格来源」判据行 |
| 写库（写侧） | `PyTools/order_flow_analysis/order_flow_sentinel.py` | 落库时 `sig.price_at_row ?= float(quant_metrics['es_price'])`（仅主列为空时写） |
| 文档 | 手册 HTML + MD | §3.1.4.1.2 取数口径表（价格序列 / 当日高·低 / 开盘锚·最新价 / 关键位族）与 §1.2 列填充注记；**顺带修复一处既存滞后**：关键位族原写「`smashlevel` + `levels_data` 全部数值」，与 2026-09-13 起的白名单 4 键（`ut1`/`fut`/`dt1`/`fdt`）不符 ⇒ 已改为白名单口径并指向 §3.1.4.1.1 |

## 4. 回滚

| 场景 | 操作 |
|---|---|
| 全部回退 | 用 `/tmp/bbt_pricefix_backup_081305/`（`balanced_day_data.py` / `balanced_day_shadow.py` / `intraday_probe.py` / `order_flow_sentinel.py` 术前副本）覆盖 |
| 只回退读侧兜底 | 删 `row_price()` 的第二分支（`es_price` 段）即回到「只认 `price_at_row`」 |
| 只回退写侧 | 删 `order_flow_sentinel.py` 中 `if getattr(sig, 'price_at_row', None) is None:` 整块 |

## 5. 遗留与后续建议

1. **当日历史空列行未回写**：09-14 08:15 之前的 17 行 `price_at_row` 仍为 NULL（读侧兜底已覆盖，故不影响判定）。如需列值自洽，可在**收盘后**跑一次 `backfill_order_flow_signals.py`（盘后运行，避免与实时写库竞争）。
2. **同类风险体检建议**：`tick 侧 9 列`（`delta_5m/10m/15m/30m`、`vol_5m/15m`、`price_at_row`、`price_chg_5m/15m`）同属「只由 backfill 铺平」——本类缺陷已第二次出现（前一次是 2026-09-13 的 DOM 平铺列）。建议给「实时写库缺列」加一条巡检：逐列统计**当日实时行**的 NULL 率并在 MW 健康检查同款页面告警。
3. **`price_chg_5m` / `delta_5m` 仍为空**：机制 ③ 当前不依赖它们；若后续评分器要用，需同法补齐（sentinel 内有末片 `price_start/price_end` 可算）。
4. 探针的 ③ 结论**不含趋势日门控**（门控只在生产通道内生效），故页面显示 `QUALIFIED` ≠ 生产必然开仓——此语义已在探针免责说明中标注，未变。
