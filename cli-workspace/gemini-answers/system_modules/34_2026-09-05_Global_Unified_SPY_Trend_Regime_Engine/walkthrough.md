# 全局统一 SPY Trend Day 判定引擎验收报告 (Walkthrough)

## 1. 模块核心目标与改动概述
针对全交易系统（SPX Gamma 分析、Order Flow 盘面判断、AI Tape Analyst）中单边趋势日检测标准不一、标的离散的问题，本模块建立了全局统一的日内单边强趋势日判定引擎：
- **基准标的一致性**：一律采用高流动性现货 ETF `SPY` 作为唯一技术判定基准；
- **严格时间窗约束**：仅限定在美西时间 `06:30 - 11:00` 之间有效，超出此区间强制判定为非趋势日，有效防范午后做市商 Gamma 衰减与仓位平仓引发的震荡失真；
- **点位量化门限升级**（SPY 标的，比例 1:10 严格对应）：
  - 现价显著高于 RTH 开盘价：`current_spy >= rth_open_spy + 0.80 点`（对应 SPX 8.0 点）；
  - 开盘后未曾发生深幅逆势破位：`rth_open_spy - rth_low_spy <= 1.20 点`（对应 SPX 12.0 点）；
  - 高位未发生深幅回撤：`rth_high_spy - current_spy <= 1.50 点`（对应 SPX 15.0 点）；
  - **核心技术共振铁律**：**5分钟 bar 收盘价在 15分钟 bar 13EMA 反方向的次数 <= 1 次**；
- **双向严格对称**：空头单边趋势日逻辑完全对称执行（`current_spy <= rth_open_spy - 0.80`，`rth_high_spy - rth_open_spy <= 1.20`，反弹 `<= 1.50`，5m 收盘站上 15m 13EMA 次数 `<= 1`）；
- **执行约束遵循**：未触发任何历史全量数据回填，保持系统既有生产数据不受干扰。

## 2. 核心架构与落地文件
1. **新建全局统一模块 `PyTools/quantdata/trend_regime.py`**：
   - 实现了 `get_or_fetch_spy_df(target_date)`：自动拉取前 5 天 SPY 1m 数据并全局缓存，确保 15m 13EMA 在 06:30 开盘时即具备平滑、稳定的历史基础；
   - 实现了 `evaluate_intraday_trend_regime(target_ts, ...)`：返回 `(is_bullish_trend_day, is_bearish_trend_day, rth_open_spy)`。
2. **SPX Gamma 分析模块对接 (`quantdata/spx_gamma_analyst.py`)**：
   - 清理模块内旧版本地函数，统一引入并调用 `trend_regime.evaluate_intraday_trend_regime`；
   - 驱动第三层决策树在非趋势日下将顺势 Cushion 推进门槛由 15.0 点严谨拓宽至 23.0 点。
3. **订单流子系统对接 (`order_flow_analysis/order_flow_rules_optimizer.py` 与 `ai_tape_analyst.py`)**：
   - 将原先孤立的 EMA 带与 Smashlevel 简易布尔判断升级为调用统一引擎 `evaluate_intraday_trend_regime`，实现跨模块指标共振与逻辑同构。

## 3. 测试验证实证
1. **2026-09-04 09:20（非趋势日反弹诱多点拦截）**：
   - SPY 5m bar 跌破 15m 13EMA 次数统计达 33 次（远大于 1 次）；
   - `evaluate_intraday_trend_regime` 精准返回 `(False, False, 772.01)`；
   - `analyze_spx_gamma` 在该点输出 `Neutral:Compression-Top`（顺势门槛提升至 23 点，上方 Cushion 15.1 点被判为空间压缩中性），彻底杜绝了虚假看多。
2. **2026-09-04 11:30（时间窗拦截）**：
   - 时间超出 11:00 上限，直接返回 `(False, False, None)`。
3. **2026-09-03 09:30（真实单边大涨日验证）**：
   - SPY 06:30 开盘 767.90，现价 772.00，开盘破位 0.24 点（<= 1.20 点），5m bar 跌破 15m 13EMA 次数为 0；
   - `evaluate_intraday_trend_regime` 精准返回 `(True, False, 767.90)`，判定为多头单边趋势日。
