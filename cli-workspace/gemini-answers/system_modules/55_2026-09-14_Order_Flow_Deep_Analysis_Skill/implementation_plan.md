# Order Flow 深度分析模块（skill + pattern 体系 + 页面展示）实施计划

- **日期**：2026-09-14
- **模块**：`order-flow-deep-analysis` agent skill（证据向量 + P1–P5 pattern + 回测/标定）+ 大周期页面展示卡片
- **归档目录**：`55_2026-09-14_Order_Flow_Deep_Analysis_Skill`
- **技术栈**：Python 3.11 / MySQL `bb_trade`（`order_flow_signals` · `order_flow_big_trade` · `of_deep_pattern_cases`）/ MW 原始 TICKS/DOM 文件 / Flask + Jinja2（`bbt_data_web`）/ agent skill（`~/.agents/skills/`）/ 浅色主题

---

## 1. 背景

此前对 ES 某时间段（如 07:25–08:15 当日低点）做的深度 order flow 分析，是**一次性、定性**的：报告里「支持/不支持」是离散清单，且存在「DOM 结论只看 T0 单点快照」「imb 偏空是硬编码文案」两个缺陷。用户要求把它沉淀成**可重复使用、可积累、可回测**的模块，并在页面上持续展示每次分析结果。

## 2. 目标

| 目标 | 交付 |
|---|---|
| 可重复的深度分析 skill | `order-flow-deep-analysis`（时间点/段 → 五板块报告 → 命名规范落盘） |
| DOM 全窗口扫描（修「以偏概全」） | `dom_window_profile()` 聚合器：时间加权均值 / 分时占比 / 前后半段收敛 / 逐段 DOM×tick 交叉 |
| 证据向量 + 可机检 pattern | `patterns.py`：`build evidence` + `match_patterns`（P1–P5） |
| 积累 → 标定 | `of_deep_pattern_cases` 落库 + `backtest.py` 回测 + `calibrate.py` 网格标定 |
| 页面持续展示 | `/bbt_signals_large_timeframe` 新增可收起卡片（列出 case + 前向结果 + 报告链接）；Adam 卡片改为可收起 |

## 3. 处理逻辑（数据源 → 指标 → pattern → 跟踪）

### 3.1 数据源（TICK / DOM 元数据）

| 层 | 来源 | 用途 |
|---|---|---|
| **TICK（逐笔成交）** | 原始 `ES_<date>_TICKS.csv`（`adam_tick_analysis`） | Δ1m/Δ5m/Δ30m 净 Delta、买占比、≥20 手大单、Volume Profile（POC/VAH/VAL）、逐分钟节奏 |
| **DOM（盘口挂单）** | 原始 `ES_<date>_DOM.csv.gz`（`adam_dom_analysis`） | ±2/±5/±15/±25 tick 失衡、挂单墙、堆叠、真空、时间演变 |
| **引擎行（每 5 分钟）** | `order_flow_signals`（`recent_micro_5m` / `imb_short·mid` / `recent_30m_delta` / `quantitative_metrics`） | 慢口径 Δ30m、DOM 平铺失衡、washout/quality_tier |
| **机构大单** | `order_flow_big_trade`（`SingleTickBigTrade`） | 机构大单净量 |

### 3.2 指标（evidence 维度）

证据向量 = `{tick, dom, engine}` 三层 + 位置分位：

- `tick`：`delta_30m`（慢）、`delta_5m`（末段）、`delta_5m_max/min`（窗口内最强短窗脉冲）、`window_net`、`buy_ratio`、`big_lot_buy/sell`、`stbt_net/n`
- `dom`：`imb5_mean`（窗口时间加权）、`bear/bull_frac`（分时占比）、`converge`（前后半段收敛）
- `engine`：`washout_bull/bear`、`direction`
- 位置：`low_pos_pct` / `high_pos_pct`（窗口低/高点在当日区间分位）

### 3.3 验证 pattern（P1–P5，可机检）

| id | 名称 | 方向 | 判据（证据向量上） |
|---|---|---|---|
| P1 | 低点吸收反转 | 多 | 低位(≤0.20 分位，已标定) + Δ30m>0 + 窗口有短窗买脉冲 + 大额不强净卖 |
| P2 | 恐慌洗盘反转 | 多 | washout_bull 命中 + 大额/机构大单净买 |
| P3 | 高位派发 | 空 | 高位(≥0.60) + Δ30m<0 + 大额净卖 |
| P4 | 挂单-成交同向共振 | 双向 | imb ±5 与 Δ5m 同向且与 bias 一致（最高可信） |
| P5 | 短长窗背离 | 双向 | Δ5m 与 Δ30m 反向（转折前兆） |

### 3.4 使用方法

```bash
# 分析（五板块报告 + 命名规范落盘）
python3 ~/.agents/skills/order-flow-deep-analysis/scripts/run_analysis.py \
  --date 2026-09-14 --start 07:25 --end 08:15 [--at 07:55 --lookback 30] [--bias bullish] \
  [--slug low_absorption_reversal] [--emit-evidence-json /tmp/ev.json] [--log-case]

# 回测（积累 → 命中率）
python3 .../backtest.py --since-days 12 [--backfill]

# 标定（网格 → 回写 patterns.py 常量）
python3 .../calibrate.py --since-days 12 --apply
```

输出：`/Users/zhijiebian/.gemini/cli-workspace/order-flow-deep-analysis/order_flow_analysis_<TICKER>_<分析日>_<分析时刻 HHMM>_<slug>_<生成日>_<生成时刻 HHMM>.html`

### 3.5 后续数据跟踪整理

- **落库**：`--log-case` 写 `of_deep_pattern_cases`（证据向量 + pattern + 置信；前向结果列留空）
- **回填**：`backtest.py --backfill` 把前向结果（+15/30/60m 位移 + 命中）写回已存在的 case
- **标定**：`calibrate.py --apply` 网格搜索阈值 → 回写 `patterns.py` 常量
- **页面**：`/bbt_signals_large_timeframe` 的「Order Flow 深度分析」卡片列出 case + 前向结果 + 报告链接

## 4. 风险与回退

- 阈值均为初值（`P1_POS_MAX=0.20` 已标定、`HIT_PTS=3.0`、`P3_POS_MIN=0.60`、`P1_BIG_NET_SELL_MAX=500`），样本小（12 日 / 94–159），需随日数累积重跑标定收敛。
- ≥20 手大单暂缓（用户有其他想法）⇒ P1/P3 的大额否决暂不生效，P3 样本暂缺。
- 全部只读 + 不接入自动下单；回滚 = 删 `scripts/` 下新增文件 + 页面改动处还原。
