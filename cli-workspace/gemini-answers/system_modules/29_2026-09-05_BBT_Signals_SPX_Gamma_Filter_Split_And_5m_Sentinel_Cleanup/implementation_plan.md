# BBT 信号图 SPX Gamma 周期过滤拆分与 5 分钟 Order Flow 信号 Sentinel 标记彻底清理引擎实施计划 (Implementation Plan)

## 1. 背景与核心问题诊断

1. **SPX Gamma 周期混杂无序**：在原有系统中，`spx_gamma_signals` 数据表中未存储 `timeframe` 字段，前端过滤仅能依靠时间戳分钟数（是否为 0 或 30 分）粗暴猜测；且同一时间点（如 07:30:00）只能存一条记录，导致 5m 结构决策树信号与 30m 大模型宏观信号相互冲突、覆盖，无法独立过滤与并存。
2. **Order Flow 5m 信号 Sentinel 误标**：历史 5 分钟 Order Flow 信号生成逻辑中曾遗留强制赋值 `is_sentinel=True` 的缺陷，导致前端散点图将所有 5m 信号均渲染为紫色卫星（Sentinel），破坏了 High/Medium/Low 的三级真实强度与红绿多空原貌。

---

## 2. 核心架构与改造方案

### 2.1 数据库结构升级 (`spx_gamma_signals`)
- 新增字段：`timeframe VARCHAR(8) NOT NULL DEFAULT '30m' AFTER ticker`。
- 重构联合唯一索引：将原有的 `(ticker, signal_date, signal_time)` 变更为 `(ticker, signal_date, signal_time, timeframe)`，确保同一时间点 30m 与 5m 记录完整并存。
- 新增高效索引：`idx_tf_date_time (timeframe, signal_date, signal_time)`。
- 历史数据精准回填：将原有 939 条历史数据中的非 0/30 分钟记录自动回填为 `'5m'`，整点/半点回填为 `'30m'`。

### 2.2 SQLAlchemy ORM 模型对齐 (`bbt_data_web/models.py`)
- `SpxGammaSignal` 实体类中定义 `timeframe = db.Column(db.String(8), nullable=False, default='30m', index=True)`。
- 更新 `__table_args__` 的 `UniqueConstraint` 包含 `timeframe`。

### 2.3 SPX Gamma 计算与落库引擎 (`PyTools/quantdata/spx_gamma_analyst.py`)
- `analyze_spx_gamma` 增加 `timeframe="30m"` 参数，支持写入 `timeframe` 字段。
- 命令行支持 `-tf` / `--timeframe` 参数（可选 `30m` 或 `5m`）。
- `init_signals_table` 增加平滑迁移检测与自适应更新。

### 2.4 后端 API 接口精准过滤 (`bbt_data_web/data_app/bbt_signals.py`)
- `/data/spx_gamma_signals` 接收 `timeframe` 参数，直接按 `SpxGammaSignal.timeframe == timeframe` 进行过滤，返回数据中包含 `timeframe`。
- `/data/order_flow_chart_data` 散点图接口返回的数据中包含 `timeframe` 字段。

### 2.5 前端图表与数据表格展示闭环 (`bbt_signals.js` / `bbt_signals.html`)
- 散点图复选框：`chkChartShowSpxGamma30m` 与 `chkChartShowSpxGamma5m` 依据 `sig.timeframe` 进行精确过滤。
- 数据表格：表头增加 `Timeframe` 列，使用浅色徽标展示：
  - `30m` 蓝色徽章：`<span class="badge" style="background:#e0f2fe; color:#0284c7; font-weight:700;">30m</span>`
  - `5m` 紫色徽章：`<span class="badge" style="background:#f3e8ff; color:#7e22ce; font-weight:700;">5m</span>`
- 配合 `#gammaTimeframeFilter` 下拉菜单，实现毫秒级精准筛选。
