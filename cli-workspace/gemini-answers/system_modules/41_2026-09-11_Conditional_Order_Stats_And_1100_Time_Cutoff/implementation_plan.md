# 实施计划 (Implementation Plan)

**模块编号**: 41
**归档目录**: `41_2026-09-11_Conditional_Order_Stats_And_1100_Time_Cutoff`
**发生日期**: 2026-09-11
**核心模块名称**: 系统自动条件单统计引擎与 11:00 PST 时段截断自动撤单 (Auto Conditional Order Statistics Engine & 11:00 PST Time-Cutoff Sweep)
**涉及技术栈**: Python / OptionSellerManager Monitor Loop / MySQL 事件表 / Flask API / Light-Theme UI / Rule Manual

---

## 1. 需求

1. **时段截断撤单**：凡在 **11:00 PST** 之后，0DTE 临期期权面临极限 Theta 衰减与做市商行权钉住 (Pinning) 效应，价格易产生非线性异动，做市商不再呈现常规日内单边对冲推力；系统已在 11:00 PST 之后刚性截断判定为 `Neutral:Time-Cutoff`。据此新增执行面规则：
   - 每天 **11:00 PST 自动撤销全部条件单**（不再留有可触发的挂单）。
   - **页面仍需展示**这批未触发的条件单，并明确标注「未触发且不会再触发」，供**盘后复盘**；
   - 展示**保留至当天 23:30 PST**，其后从页面清除（数据库保留，供统计）。
2. **统计功能**：开始统计**系统自动条件单**的「挂单」与「触发」数据（并含手动条件单以便对照），形成可复盘的量化指标。

## 2. 关键事实（勘察结论）

| 项 | 结论 |
| --- | --- |
| 数据表 | `order_flow_option_seller_conditional_orders`（21 行：12 CANCELLED / 6 TRIGGERED / 3 PENDING），**无 source / cancel_reason 列**，来源与子场景由 `notes` 文本标记推导 |
| 管理进程 | `PyTools/option_seller/option_seller_manager.py`，由 `bbt_data_web` 与 `order_flow_sentinel.py` 使用；监控循环 `_monitor_loop` 固定 8s 周期 |
| 埋点位点 | 创建：`add_conditional_order()`；触发：`_evaluate_conditional_orders()` → `option_seller_conditional_order_trigger()`；撤销：`cancel_conditional_order()` |
| 自动布防 | `evaluate_5m_synthesis_trade()` 内在无重复时调用 `add_conditional_order()`（05m 周期，RTH 06:35~11:30 PST） |
| 时区 | 管理进程写入的 `created_time` / `triggered_at` 为**美西 PT 墙钟**（实测 `created_time=07:31` 对应 MySQL `created_at=14:31` UTC，差 7 小时）；手册与既有时间窗（如 12:30~13:15 强平）同样按 PT |
| UI | `templates/bbt_option_seller.html`「待触发条件单监控」面板 → `pending_conditional_orders`（状态摘要）+ `/api/option_seller/conditional_orders`（当日记录） |

## 3. 布防窗口模型（通用性设计，非单日拟合）

定义**条件单布防窗口**（PT）：

```
允许布防:  [23:30, 24:00) ∪ [00:00, 11:00)
时段截断:  [11:00, 23:30)      ← 该区间内不允许存在任何 PENDING 条件单
```

- 窗口边界与需求中的「保留至 23:30 后清除」共用同一时间轴，语义自洽：**23:30 起为新一个条件单日**。
- 对称性与通用性：规则**方向无关**（看涨 BULLISH / 看跌 BEARISH 一视同仁），**标的相关**（ES/SPX/SPY 一致），不依赖任何单日行情特征；统计口径同样双向分列，避免只拟合上涨样例。
- 不变量：**布防窗口之外，系统中不存在可触发的条件单**。

## 4. 实施方案

### 4.1 数据层（新增，纯追加，不改动既有表结构）

新表 `option_seller_conditional_order_events`（append-only 事件流）：

| 字段 | 说明 |
| --- | --- |
| `order_id` | 关联条件单 id |
| `event_type` | `PLACED` / `TRIGGERED` / `CANCELLED` |
| `event_date`, `event_time`, `event_at` | PT 日期/时间/时刻 |
| `event_seconds` | 当日秒数（小时段分布用） |
| `source` | `AUTO` / `MANUAL`（由 notes 标记判定，写入时落库） |
| `sub_scenario` | 子场景（`RANGE_BOUND_LOWER_BOUNDARY` 等） |
| `trigger_symbol/condition/price`, `spread_action`, `risk_profile`, `dte`, `fallback_mode`, `groups`, `take_profit_mode` | 下单快照 |
| `spot_at_event` | 事件时现价（PLACED=布防时现价；TRIGGERED=触发时现价） |
| `distance_points` / `distance_pct` | 现价距触发价的有符号距离（布防难度/触发偏差） |
| `time_to_trigger_sec` | 挂单 → 触发耗时 |
| `cancel_reason` | `MANUAL` / `TIME_CUTOFF_1100` / `UNKNOWN` |
| `out_of_window` | 是否在布防窗口外创建 |
| `trade_ids`, `detail` | 开仓 trade ids、扩展信息（含回填标记） |

理由：既有表若加列需改动生产表结构并重启全部相关进程；事件流表可完整保留「挂单 → 触发/撤销」全过程，直接支撑统计且零侵入。

同时提供**历史回填**：由存量 21 条条件单合成 `PLACED` 与终态事件（回填标记 `detail.backfill=true`），使统计面板上线即有数据。

### 4.2 管理器层（`option_seller_manager.py`）

1. `is_conditional_arming_window()`：按 PT 判定是否处于允许布防窗口。
2. `cancel_all_conditional_orders(reason)`：批量撤销内存 + DB 中全部 PENDING，逐单写 `CANCELLED` 事件并在 `notes` 追加 `[TIME_CUTOFF_1100]` 标记。
3. `enforce_conditional_order_cutoff()`：在 `_monitor_loop` 每轮**先于触发判定**执行；处于截断区间且存在 PENDING ⇒ 全部撤销（自然幂等，可覆盖 11:00~11:30 引擎尾窗新挂单）。
4. 自动布防闸门：`evaluate_5m_synthesis_trade()` 布防分支在窗口外直接跳过（每日仅记一次日志）。
5. 埋点：创建 → `PLACED`；触发成功 → `TRIGGERED`；撤销 → `CANCELLED`（带 reason）。

### 4.3 API 层（`data_app/bbt_option_seller.py`）

- `POST /api/option_seller/conditional_order/create`：处于截断区间时**拒绝创建**并返回明确原因（可配置常量回退为「仅告警放行」）。
- `GET /api/option_seller/conditional_orders`：为每条订单补充 `cancel_reason` / `is_time_cutoff`；当 PT ≥ 23:30 时**不再返回**当日的 `TIME_CUTOFF_1100` 单（页面清除，数据保留）。
- `GET /api/option_seller/conditional_order_stats?date_from&date_to&source`：返回挂单/触发/撤销总数、触发率、按来源/方向/触发条件/子场景/小时段分布、平均触发耗时、平均布防距离与触发偏差、按日趋势。

### 4.4 UI 层（`templates/bbt_option_seller.html`）

- 「待触发条件单监控」面板：新增**时段截断分组**，灰底（浅色主题）卡片、`已时段截断 · 未触发且不会再触发` 徽标、显示撤销时间与原因，隐藏「撤单」按钮；面板标题补注「保留至 23:30 供盘后复盘」。
- 新增**条件单统计**折叠卡片：KPI（挂单/触发/触发率/截断撤销/待触发）+ 按方向（看涨/看跌双向）、按来源、按子场景、按小时段、按日趋势小表；日期范围与来源筛选；浅色主题。

### 4.5 规则入库（规则手册）

在手册 `1. 决策架构：三阶梯结构决策树状态机` 节内追加「11:00 PST 时段截断撤单」决策性规则（HTML + 对应 `.md`），与既有 `Neutral:Time-Cutoff` 截断条并列。

## 5. 验收标准

| # | 验收项 | 判定 |
| --- | --- | --- |
| 1 | 截断区间内 PENDING 全部被撤销 | DB `status=CANCELLED` 且事件表存在 `CANCELLED/TIME_CUTOFF_1100` |
| 2 | 布防窗口内不误撤 | 23:30~11:00 区间调用不产生撤销 |
| 3 | 页面展示与标注 | 截断单仍显示、标注「未触发且不会再触发」、无撤单按钮 |
| 4 | 23:30 后页面清除 | 接口不再返回当日截断单；DB 事件仍在 |
| 5 | 统计正确 | 挂单/触发/触发率与事件表、订单表三方一致，且双向（BULLISH/BEARISH）均有分列 |
| 6 | 历史回填 | 存量 21 单全部生成 PLACED + 终态事件 |
| 7 | 回滚可行 | 关闭开关常量后行为还原；事件表可整表删除，不影响既有表 |

## 6. 风险与回滚

- **风险**：截断扫描会撤销当日残留 PENDING（属预期行为）；创建闸门会拒绝 11:00~23:30 期间的手动建单（可用常量 `BLOCK_CREATE_OUTSIDE_ARM_WINDOW=False` 回退为仅告警）。
- **回滚**：还原 `option_seller_manager.py` / `bbt_option_seller.py` / `bbt_option_seller.html` 三处改动；`DROP TABLE option_seller_conditional_order_events`；规则手册条目删除即可。
