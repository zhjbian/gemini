# 当日高低点自动触发机制检测：持久化存储、13:05定时自检与原因统计升级计划

## 概述与背景
目前 `http://127.0.0.1:5005/bbt_option_seller` 页面上的「当日高低点自动触发机制检测」此前仅支持前端手动点击实时探测，且探测结果驻留在内存中并未入库。
为了支撑日后对**各个机制未触发原因的统计与量化归因分析**，系统升级为：
1. **自动调度与落库**：每天 13:05（美西时间收盘后，全天 5m K 线完整落定）自动执行一次完整高低点检测，并将检测报告与结构化明细入库（MySQL `bb_trade`）。
2. **极速只读加载**：前端卡片展开时优先加载库中最后一次检测结果（避免重复耗时计算），并清晰标明检测时间与触发方式（定时自动 / 手动刷新）。点击「刷新检测」时触发实时重算并更新数据库。
3. **明细化指标归因建模**：除存储整份 JSON 报告外，同步拆解极值点、闸门阻断（L0 阻断）、机制判据失败原因至结构化明细表，直接支持 SQL 聚合与归因分析（如统计某机制因波幅超标、EMA 未理顺或 L0 掩码导致的拦截频次）。

---

## 架构与数据库设计

### 1. 数据库模型 (`bbt_data_web/models.py`)

#### 表 1：`order_flow_option_seller_extremes_probe`（主表 / 日快照）
- `id`: 主键，自增
- `probe_date`: 检测交易日（`DATE`，唯一索引 `uq_probe_date`）
- `probe_time`: 检测执行时刻（`TIME`）
- `detected_at`: 完整执行时间戳（`DATETIME`）
- `trigger_type`: 触发类型（`VARCHAR(16)`，如 `'AUTO_1305'` 或 `'MANUAL'`）
- `points_count`: 极值点数量（4）
- `triggered_count`: 命中触发机制的点位数量
- `full_payload`: 完整 JSON 报告（供前端快速渲染全部指标）
- `created_at` / `last_modified`: 时间戳

#### 表 2：`order_flow_option_seller_extremes_probe_detail`（明细表 / 归因统计）
- `id`: 主键，自增
- `probe_date`: 交易日（`DATE`，索引）
- `point_kind`: 极值类型（`VARCHAR(8)`，`HIGH` / `LOW`）
- `point_ord`: 极值序号（`INT`，1 / 2）
- `point_time`: 极值时刻（`VARCHAR(8)`，如 `11:15`）
- `point_label`: 极值标签（`高点#1`, `低点#2`）
- `spy_price`: SPY 价格（`DECIMAL(10,2)`）
- `es_price`: ES 价格（`DECIMAL(10,2)`）
- `mandated_side`: 检测方向（`VARCHAR(16)`，`BEARISH` / `BULLISH`）
- `l0_passed`: L0 是否对该方向放行（`BOOLEAN`）
- `l0_blocked_reason`: L0 拦截原因（`VARCHAR(255)`，如 `本侧被掩码: BEARISH` 或 `基础门槛未过`）
- `mechanism_id`: 机制 ID（`VARCHAR(48)`，如 `QP_BOUNDARY_REVERSAL`）
- `mechanism_name`: 机制名称（`VARCHAR(64)`）
- `verdict`: 判定结论（`VARCHAR(32)`，如 `QUALIFIED` / `REJECTED` / `ARMED`）
- `engine_verdict`: 引擎实判结论（`VARCHAR(32)`）
- `is_triggered`: 是否达标（`BOOLEAN`）
- `failed_criteria`: 未达标的前置判据摘要（`TEXT`，直接支持 `GROUP BY` 聚合分析）
- `criteria_detail`: 完整判据数组（`JSON`）
- `created_at`: 时间戳

---

## 实施步骤
1. **数据模型与持久化层**：在 `models.py` 增加数据模型，在 `intraday_probe.py` 编写 `save_probe_to_db` 与 `get_saved_probe_from_db`。
2. **每日 13:05 自动定时任务**：创建 `run_daily_extremes_probe.py`，并在 `daily_jobs.py` 中注册 `schedule_weekdays("13:05", run_option_seller_extremes_probe_auto)`。
3. **后端 API 与只读缓存响应**：在 `bbt_option_seller.py` 中重构 `/api/option_seller/intraday_extremes_probe`，默认展开瞬时返回 DB 记录，携带 `refresh=1` 实时重算并保存。
4. **前端 UI 优化**：展开时秒开并渲染持久化标签（`13:05 定时自动自检 / 手动触发检测 · 保存于 YYYY-MM-DD HH:MM:SS`），点击「刷新检测」带参数重新计算并更新库。
5. **归档维护**：更新 `bbt_trading_modules.html` 对应章节。
