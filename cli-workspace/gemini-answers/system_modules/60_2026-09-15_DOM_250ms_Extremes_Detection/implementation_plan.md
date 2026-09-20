# DOM 250/500ms 快照级极值 / 异常点检测 —— 实施计划

- **日期**：2026-09-15
- **模块**：DOM（盘口深度）毫秒级极值 / 异常检测（`order_flow_analysis/dom_extremes.py` 系列）
- **归档目录**：`60_2026-09-15_DOM_250ms_Extremes_Detection`
- **技术栈**：Python 3.11 / numpy / MW 原始 DOM（`ES_<YYYYMMDD>_DOM.csv.gz`）/ MySQL `bb_trade`（`order_flow_dom_extremes`）/ Flask（`/data/dom_extremes` + 页面卡片）/ 浅色主题 / unittest 契约测试
- **定位**：**只标注、不进决策**（前向验证结论见 Walkthrough §5）

---

## 1. 需求（用户原文）

> 与 5 分钟均值无关的即时信号可能蕴含宝贵的信息… DOM 的信号通常很快，上面这样根本不可能发现真正的信号…
> **请实现对于 250ms 或 500ms 的 snapshot 极值 / 异常点的获取和分析**

## 2. 问题定位（为什么要做）

既有 DOM 指标**全部是窗口均值**：`dom_sentinel_evaluator` 把 5 分钟窗口内 1200 根（250ms）快照重采样成等距网格后取 `np.mean()`，
落库到 `order_flow_signals.imb_short / imb_mid_short / …`。**均值对瞬时事件是天然的低通滤波器**。

实测证据（2026-09-14，ES）：

| 时刻 | DB（5 分钟均值口径） | 250ms 快照极值 | 倍率 |
|---|---|---|---|
| 08:05 窗口 | `imb_near` 均值 **+0.007** | **−0.5316 @08:05:30.000** | **76×** |
| 08:40–08:45 窗口 | **+0.043** | **+0.3634 @08:41:43.000** | 8.4×（且该极值出现在**亏损单入场前 7 秒**） |

⇒ 结论：均值口径**在结构上不可能**发现毫秒级插针 / 瞬时撤单 / 挂单真空；需要**在快照网格上直接做极值与异常检测**。

## 3. 设计

### 3.1 数据与网格口径（与哨兵**同源**）

| 项 | 取值 |
|---|---|
| 原始文件 | `RAW_DATA_DIR/ES_<YYYYMMDD>_DOM.csv.gz`（表头 `Timestamp,Type,Level,Price,Size,Contract`） |
| 快照节奏 | **ES：2026-09-14 07:51:30 起 250ms**；此前与 NQ 一样 500ms |
| 网格间隔 | `resolve_grid_interval_ms(sample_interval_ms, src_interval)` —— **跟随源**（ES 250ms / NQ 500ms），不硬编码 |
| 每快照规模 | ~400 行 = 200 档 × 2 侧 |
| 读盘方式 | `load_dom_snapshots(...)`（**小时索引**跳读，整日一次读盘多窗口复用） |
| 成交流 | `map_trades_to_grid(...)` → 逐格 `had_buy / had_sell`（判别「被成交吃掉 vs 真撤单」） |

三个函数（`load_dom_snapshots` / `build_dom_grid_series` / `map_trades_to_grid`）在本次重构中**抽取为共享函数**：
哨兵与 `dom_extremes` 调用**同一份实现**（单一权威），并逐窗口与冻结基线做**逐字节**比对（PASS，见 Walkthrough §6）。

### 3.2 被检测的序列（6 条）

| 序列 | 含义 | 方向语义 |
|---|---|---|
| `imb_near` | 近端（±2 档）失衡 | `>0` 买盘占优 |
| `imb_mid` | 中端（±5 档）失衡 | 同上（**弱序列**） |
| `imb_deep` | 深端（±15 档）失衡 | 同上（**弱序列**） |
| `w_imb` | 加权失衡 | 同上 |
| `near_bids` | 近 5 档买盘挂单**总量** | 异常放大 = 支撑 |
| `near_asks` | 近 5 档卖盘挂单**总量** | 异常放大 = 压制 |

### 3.3 四类事件

| 类型 | 定义 | 关键参数 |
|---|---|---|
| `outlier` | 稳健 z 超阈的**连续段**（合并 ≤1 格间隙） | `k_mad=3.5`，`min_bins=1`，`max_gap_bins=1` |
| `step` | 相邻格挂单量**跳变**（±近 5 档总量） | `step_vol=50` |
| `flip` | `imb_near` 符号翻转（带幅阈与最大跨度） | `flip_thr=0.10`，`flip_max_bins=6` |
| `vacuum` | 单侧挂单**真空**段（下方无支撑 / 上方无压制） | 由 `vacuum_bid/ask` 布尔序列导出 |

### 3.4 稳健尺度：**窗口局部 median/MAD**（关键决策）

- 尺度链：**`MAD → IQR/1.349 → flat_floor(max(|median|×0.02, 1e-6))`**，**刻意不使用标准差兜底**。
  - 反例：`MAD=0` 的**平台型异常**（连续同值）若退回 `std`，平台本身会把 `std` 抬高，异常被自己掩盖（实测 z 仅 1.46）；
  - IQR / 截尾 std 同样被 ≥15% 占比的平台污染（实测 z 仅 1.75）；
  - ⇒ **持续型 / 大幅型异常交给绝对阈值**（`abs_imb_strong=0.30`、`abs_vol_strong=400`），稳健 z 只负责**相对突兀**。
- 尺度**窗口局部**（每个 5 分钟窗口自算），而非 60 分钟滚动基线：滚动基线会把「慢漂移」误判为正常（已做对照，窗口局部更少漏报）。

### 3.5 数据有效性掩码 `data_valid_mask`（**必须**）

网格由 `range(start, end, interval)` 生成，窗口起点可能**早于第一根快照**（预热段），窗口尾部可能**晚于最后一根**
（陈旧段）——这些格子若留零值会被当成「挂单量 = 0 的极端异常」。
⇒ 掩码只保留 `[第一根快照, 最后一根快照]` 覆盖的格，其余置 `NaN` 并在统计中剔除。
**修复效果**：07:30 窗口的伪极值 32 个 → 3 个；`near_asks z=−17` 消失。

### 3.6 分级与打分（`grade_event`）

| 级别 | 分数 | 典型构成 |
|---|---|---|
| **L1** | ≥3 | z≥6 或 绝对幅超强阈；`step` 大幅（≥2×）且方向项命中；弱序列封顶 L2 |
| **L2** | =2 | 中等：z≥4 / 中等 step / flip / vacuum |
| **L3** | ≤1 | 弱信号（保留但不入默认视图） |

标定证据（2026-09-14 08:00–09:00，426 事件）：分数直方图 `{0:19, 1:195, 2:191, 3:21, ≥4:0}`
⇒ 若 L1 门槛设 ≥4 则**永远为空**，故 L1 = ≥3（≈1.6 条/窗口，人可读的量级）；
`near_bids/near_asks` 是**近 5 档挂单之和**（中位 ≈230、最大 431）⇒ `abs_vol_strong=400`。

### 3.7 形态与方向

- **形态按时长**：`duration_ms ≤ spike_max_ms(750)` ⇒ `spike`（插针），否则 `plateau`（平台）——**比按 z 高低更贴合用途**。
- **方向映射**（`event_direction`，供前向验证）：
  - `imb*`/`w_imb` 离群：峰 >0 ⇒ 多，<0 ⇒ 空；
  - `near_bids` 异常放大 ⇒ 多；`near_asks` ⇒ 空（**注意：是"量放大"而非"失衡"**）；
  - `step`：**加单**按该侧方向（买盘加 ⇒ 多 / 卖盘加 ⇒ 空）；**减单取反**（买盘被吃或撤 ⇒ 空 / 卖盘 ⇒ 多）；
  - `flip`：偏空→偏多 ⇒ 多；`vacuum`：买侧真空（下方无支撑）⇒ 空 / 卖侧真空 ⇒ 多。

### 3.8 阈值**间隔归一**（实施中新增，补入计划）

同一 `step_vol=50` 在 500ms 网格上比 250ms 网格**更易被跨越**（相邻两格之间累积了 2 倍挂单流）⇒ L1 密度跨日不可比
（实测 2026-08-31 **26 条/窗口** vs 2026-09-14 **1 条/窗口**）。
⇒ `analyze_arrays` 内以 **250ms 为基准**线性缩放：`step_vol_eff = step_vol × grid_interval_ms / 250`，
**检出处与评分处一致使用**，并在结果中回传 `step_vol_eff`（便于复盘核对）。效果：7 天总事件 30,421 → 11,084、入表行 23,521 → 6,669。

### 3.9 落地形态（四段式）
| 阶段 | 内容 | 产物 |
|---|---|---|
| **P1** | 检测库（纯计算，可被哨兵内联复用） | `dom_extremes.py`；哨兵 `dom_metrics['extreme']` 摘要（**零 schema 变更**） |
| **P2** | 单窗口 / 整日 CLI + 浅色 HTML 报告 | `run_dom_extremes.py` |
| **P3** | 前向验证（有/无方向优势） | `validate_dom_extremes.py`（分组 × 前向 15/30/60 分钟） |
| **P4** | 生产接入 | ① 回填落库脚本 `backfill_dom_extremes.py`（幂等）② 只读 API `GET /data/dom_extremes` ③ `/bbt_signals` 页面卡片（**标注用**） |

### 3.10 生产接入的边界（纪律）

- **不进决策**：`option_seller_*` 与信号引擎**不读** `order_flow_dom_extremes`；哨兵只写摘要、不做判定。
- **热路径不写库**：哨兵（每 5 分钟、日内数百次）**只写** `dom_metrics.extreme` JSON 摘要（≈2.7KB，随既有行落库）；
  事件明细靠**盘后回填**（只读原始 DOM → `order_flow_dom_extremes`），避免在热路径上引入 DB 写放大。
- **幂等**：唯一键 `(event_date, ts_ms, kind, series, side)` + `INSERT … ON DUPLICATE KEY UPDATE`；
  其中 `series` / `side` 取 **NOT NULL DEFAULT ''**（MySQL 中唯一键列含 NULL 可重复 ⇒ 幂等失效）。
- **可回滚**：回填 `--apply` 时输出受影响主键的 `DELETE` 语句（`--revert-sql`）。

## 4. 改动清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `PyTools/order_flow_analysis/dom_sentinel_evaluator.py` | 抽取 3 个共享函数（`load_dom_snapshots` / `build_dom_grid_series` / `map_trades_to_grid`）；新增 `_extreme_summary()`；返回 dict 新增 `extreme` 键 |
| 2 | `PyTools/order_flow_analysis/dom_extremes.py` | **新增**（约 760 行）：稳健统计 / 有效性掩码 / 四类事件 / 分级 / 方向 / `analyze_arrays` / `summarize_for_sentinel` / `analyze_window` / `analyze_day` |
| 3 | `PyTools/order_flow_analysis/order_flow_config.py` | 新增 `THRESHOLDS["dom_extremes"]`（全部阈值集中、可覆盖） |
| 4 | `PyTools/order_flow_analysis/run_dom_extremes.py` | **新增**：CLI + 浅色 HTML 报告 + JSON |
| 5 | `PyTools/order_flow_analysis/validate_dom_extremes.py` | **新增**：前向验证（多空分层 / 强度分层 / 成交性质 / 共振 / 序列×类型） |
| 6 | `PyTools/order_flow_analysis/backfill_dom_extremes.py` | **新增**：DDL + 幂等 UPSERT + dry-run/apply + 可回滚 |
| 7 | `PyTools/order_flow_analysis/test_dom_extremes.py` | **新增** 50 条契约测试（含回填行映射 / DDL 幂等键 / 强度分层） |
| 8 | `bbt_data_web/models.py` | 新增模型 `OrderFlowDomExtreme`（`series/side` NOT NULL DEFAULT ''） |
| 9 | `bbt_data_web/data_app/bbt_signals.py` | 新增只读端点 `GET /data/dom_extremes`（清单 + 分组统计 + 实时摘要） |
| 10 | `bbt_data_web/templates/bbt_signals.html` | 新增「DOM 毫秒极值（250/500ms 快照级）」卡片（含「只标注、不进决策」警示 + 跟随全局日期） |
| 11 | 归档 | 本目录 Plan / Walkthrough（md + html）+ `bbt_trading_modules.html` 登记 |

> 规则手册（`gemini_answer-trading_system_rules_manual`）**本次不登记**：按规则 (11)，手册只收「决策性规则」，
> 本模块明确定位为**观测/复盘**且**无方向优势**，不构成任何开仓判定 —— 已在文档中显式声明。

## 5. 验收标准

1. 三个共享函数抽取后，**既有哨兵输出逐字节不变**（仅新增 `extreme` 键）；
2. 250ms / 500ms **自适应**网格（ES / NQ 各自跟随源）；
3. 单元测试全绿（含回填 DDL/幂等键与行映射契约）；
4. 回填脚本 **dry-run / apply / 回滚** 三态可用且**重复执行零重复行**；
5. API 与页面卡片可读（只读、含免责声明）；
6. 前向验证给出**诚实的**有/无优势结论，并据此决定是否进决策（**结论：不进**）；
7. **阈值间隔归一**（250ms 基准 → 按网格间隔线性缩放）生效，且检出处与评分处同口径；
8. **统计口径自检**：基准率逐日取用（不跨日平均）、且计「方向命中」而非「有无变动」——两条均已写成回归测试。
