# ES DOM 250ms 特征值：提取 · 展示 · 跟踪统计（实施计划）

- **日期**：2026-09-15
- **模块**：`PyTools/order_flow_analysis/dom_features.py` + `backfill_dom_features.py` + `dom_feature_stats.py`；`bbt_data_web` API/页面
- **锚点定义（用户澄清）**：**既有 pattern 案例**（`of_deep_pattern_cases`，如 `ES_2026-09-14_0825` = 07:25→08:25 bull / P1 medium / 前向 +17.25/+23.75/+29.5）——要提取的是该案例**底部盘整阶段**的 DOM/order flow 特征值。
- **落位（用户指定）**：`http://127.0.0.1:5005/bbt_signals_large_timeframe` →「Order Flow 深度分析（pattern 匹配）」+「Adam 信号研究进展（每日 / 每周）」

## 1. 前置事实（2026-09-15 DOM 可信度审计，决定本模块口径）

工具 `audit_dom_data.py`（26 个交易日）：**可用 0 · 部分可用 3 · 不可用 23**。

| 事实 | 数值 |
|---|---|
| 真正 250ms 档 | **只有 2026-09-14**（中位 316ms，38/60 窗口达标）；08-24（23/60）、08-21（19/60）为过渡档 |
| 其余交易日 | 500ms 档（中位 514–613ms），每 5min 窗口 380–650 快照（标称 600）⇒ 10–20% 空洞 |
| 09-15（今天） | 已回到 ~500ms（中位 538ms）⇒ **250ms 是偶发，不是稳定配置** |
| 无 RTH 数据 | 9 天（08-23、08-30、09-01/02/03/06/09/13 等） |
| 09-14 内部 | 06:30–07:35 为 500ms；07:50 后才 ~300ms；08:45–09:05 p90 高达 1914ms |

⇒ **三条硬约束**：① 特征在**真实快照时间轴**上算（Δt 归一，不建等距网格）；② 每槽带**质量门禁**；③ **cohort 分开**（c250: iv≤350ms / c500: 350–700ms），绝不混算。

## 2. 设计

### 2.1 阶段切分（回答"底部时盘口什么样"）
用 TICKS 的 1 分钟价格路径把案例窗口切成 `decline → base（底部盘整）→ rally`：
`base_start` = 低点前最后一段仍贴近低点（≤low+1.5 点）的起点；`base_end` = 低点后首次上行 >low+3 点。
底部常常包含**数据空洞** ⇒ 另取 base 内**最长连续块**（`base_block`）单独出特征（隔离空洞）。

### 2.2 特征集（全部 Δt 归一）
- **档位/盘口**：近端(±5)买卖挂单、深度(±20)买卖挂单、`imb_near`、`w_imb`、价差(tick)、真空档位、挂单墙。
- **速率（每秒）**：加单/减单（买/卖两侧）、净变化、深度净变化；**撤/吃分解**——减量按同区间**主动方成交量**占比归因（MW TICKS 的 `Side` = 主动方：`ASK`=买方主动、`BID`=卖方主动 ⇒ 2026-09-15 修正，原先按 `BUY/SELL` 匹配导致成交量恒 0）。
- **补单**：大幅减量（≥3×中位|Δ|）后回到 80% 前值的时间（中位/占比）。
- **持续性**：失衡符号持续率、翻转次数/分钟、|imb| p90/max、失衡变化率 p90。
- **质量**：快照数、间隔中位/p90、覆盖率（以**本段自身节奏**为分母）、空洞占比、最大空洞。

### 2.3 质量门禁
`n_snaps ≥ 40` ∧ `iv_med ≤ cohort 上限` ∧ `iv_p90 ≤ cohort 上限` ∧ `coverage ≥ 60%` ∧ `hole_pct ≤ 10%`。
不达标 ⇒ `quality_ok=0`（照实入库，但**不得**进入统计）。

### 2.4 存储与任务
- 表 `order_flow_dom_features`（唯一键 `(feature_date, slot_time, kind, ref_id)`，`kind ∈ {case, slot}`，特征以 JSON 落 `features`）。
- `backfill_dom_features.py --mode cases`（案例，2 行）/ `--mode slots`（逐日逐 5 分钟槽，滚动 60 分钟窗口，与案例同口径）。
- **性能**：逐槽各读一次 DOM 需 ~53s/槽（gzip 必须从流头解压）⇒ 改为**单遍流式 + 逐槽切片**（`stream_day_series` / `extract_day_slots`），并把撤/吃归因从"每区间重扫全部成交（O(区间×成交)，单日会挂死）"改为**单次指针推进 O(成交+区间)** ⇒ 单日 **~20–60s**。

### 2.5 跟踪统计与 pattern 发现（`dom_feature_stats.py`）
三条统计纪律：① 基准率**逐日**（不跨日平均）；② 基准**同时段配对**（只用该日"有 DOM 数据的时段"内的 5 分钟 bar 算基准 ⇒ 消除数据可得性选择偏差）；③ **cohort 分开**。
分桶：每个特征按三分位切 low/mid/high，逐桶给 `n / n_days / 上行% / 基准% / edge`；`n < min_bucket_n` 或**只有 1 天有配对基准** ⇒ 打 `n_low` / `single_day` 标记，**不下结论**。
复合「底部特征分」`base_signature`：`imb_mean`、`deep_near_div(=w_imb−imb)`、`cancel_share_bid` 三轴按**当日横截面**标准化后等权。

### 2.6 展示（两个卡片）
- **Order Flow 深度分析**：每个 case 行展开区追加「🧱 DOM 250ms 特征（底部盘整）」——质量徽标 + 摘要行 + level/rate/persistence 两列小表 + 免责行；无数据显示回填命令。
- **Adam 信号研究进展**：新增「🧱 DOM 250ms 特征跟踪」——每日/每周切换 + 九列表（槽位/达标/覆盖中位/上行%15·30·60/对照基准%/edge）+ 特征分桶表 + 脚注（n 与对照口径）。
- 两个板块均为**懒加载 + try/catch 降级**，接口异常不影响原卡片。

## 3. 改动清单
| 文件 | 内容 |
|---|---|
| `PyTools/order_flow_analysis/dom_features.py`（新） | 真实时间轴特征提取（snap_row / stream_day_series / extract_day_slots / assemble_window / 阶段切分 / 质量门禁）+ CLI + 浅色 HTML |
| `.../backfill_dom_features.py`（新） | 建表 + cases/slots 两模式回填（幂等 UPSERT + dry-run） |
| `.../dom_feature_stats.py`（新） | cohort 感知门禁 + 配对基准 + 每日/每周 + 特征分桶 |
| `.../audit_dom_data.py`（新） | DOM 可信度审计（准入清单，先行条件） |
| `bbt_data_web/data_app/bbt_signals.py` | `GET /data/dom_features`、`GET /data/dom_feature_stats`（只读） |
| `bbt_data_web/templates/bbt_signals_large_timeframe.html` | 两个卡片的展示板块（+307 行，纯增量） |

## 4. 验收标准
1. 案例 `ES_2026-09-14_0825` 能给出底部段特征值（含质量与空洞如实暴露）；
2. 逐日逐 5min 槽回填可跑完（单日 ≤ 2 分钟）；
3. 统计层**不产出**任何在样本不足时的 pattern 结论（n/天数门槛 + single_day 标记）；
4. 两个页面板块可用，接口异常时优雅降级且不影响原卡片；
5. 全程只读原始数据、只写自有表；**只标注、不进决策**（不接入下单，不写规则手册——非决策性规则）。

### 2.7 追加：短期口径（当天余下 / 次日）——用户 2026-09-15 指定
- 目标变量层 `dom_day_targets.py`：TICKS 1 分钟价路径 → `rest_ret/rest_up/rest_mfe/rest_mae/rest_pos_pct`
  与 `next_ret/next_up/next_open_ret`（次日交易日自动向后查找，无 TICKS 则 NULL，不插补）。
- **次日收益在同一交易日内是常量 ⇒ 次日只能做日级检验**（日指标 = 当日原始均值 / 日高值占比 / 日级复合分，
  附留一天 min|ρ| 脆弱性标记）；槽位级只用于**同日配对**的当天余下检验。
- 复合"底部特征分"的日级版本必须用**原始日均跨日 z**（当日内 z 分的日均恒为 0，会产出人工 ρ）。
- 验收：① 当天/次日目标 958 行全部回填；② 槽位级当天余下 edge 与同日配对口径一致；
  ③ 日级检验给出 ρ + 留一天敏感性；④ 页面显示当天/次日表与日级检验表（标注 cohort）。
