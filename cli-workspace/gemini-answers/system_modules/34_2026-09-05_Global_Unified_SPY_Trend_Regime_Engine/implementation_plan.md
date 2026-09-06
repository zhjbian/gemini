# 全局统一 SPY Trend Day 判定引擎实施计划 (Implementation Plan)

## 1. 需求与背景分析
在之前的实现中，不同分析子系统（如 SPX Gamma、Order Flow Sentinel、AI Tape Analyst 等）对单边强趋势日（Trend Day）存在定义不一致、数据源各异（SPX / ES）以及缺乏严格时间窗约束等问题。
为了建立高确定性、理论扎实且全系统通用的趋势日量化识别标准，按用户要求全局统一趋势日检测函数 `evaluate_intraday_trend_regime`：
1. **统一标的**：一律以 SPY 现货为基准（弃用 SPX / ES，避免期货展期价差或指数估值跳空干扰）；
2. **严格时间窗口**：仅限定在美西时间 `06:30 - 11:00` 之间有效，超出此区间一律判定为非趋势日；
3. **SPY 量化门限适配**（按照 SPX:SPY 约 10:1 比例换算）：
   - 现价显著偏离 RTH 开盘价：多头 `current_spy >= rth_open + 0.80 点`（空头 `current_spy <= rth_open - 0.80 点`）；
   - 开盘后未曾发生深幅逆向走势：多头 `rth_open - rth_low <= 1.20 点`（空头 `rth_high - rth_open <= 1.20 点`）；
   - 极值未发生深幅回撤：多头 `rth_high - current_spy <= 1.50 点`（空头 `current_spy - rth_low <= 1.50 点`）；
   - **核心结构过滤铁律**：**5分钟 bar close 在 15分钟 bar 13EMA 反方向的次数 <= 1**（多头跌破 13EMA 次数 <= 1；空头站上 13EMA 次数 <= 1）。
4. **约束**：暂时不要回填任何数据，代码修改完成交由用户测试。

## 2. 核心架构设计与改造清单
1. **新建全局公共模块 `PyTools/quantdata/trend_regime.py`**：
   - 包含多日 SPY 1 分钟 K 线自动拉取与内存缓存器 `get_or_fetch_spy_df`，保证 15 分钟 13EMA 在 06:30 开盘时已拥有至少 5 个交易日的平滑历史；
   - 实现 `evaluate_intraday_trend_regime(target_ts, current_spx=None, day_low=None, day_high=None, connection=None)`；
   - 自动聚合计算 15 分钟 13EMA 与 5 分钟 K 线，对齐统计 5m close 反向次数。
2. **统一调用与模块解耦**：
   - `PyTools/quantdata/spx_gamma_analyst.py`：移除旧实现，统一导入 `quantdata.trend_regime.evaluate_intraday_trend_regime`；
   - `PyTools/order_flow_analysis/order_flow_rules_optimizer.py`：接入统一的 `evaluate_intraday_trend_regime`；
   - `PyTools/order_flow_analysis/ai_tape_analyst.py`：接入统一的 `evaluate_intraday_trend_regime`。
3. **系统文档与规则手册更新**：
   - 建立模块 34 目录及实施计划与验收报告；
   - 更新 `bbt_trading_modules.html` 表格；
   - 更新 `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` 与 `.md`。

## 3. 验证计划
- 针对 2026-09-04 09:20 局部反弹行情：验证 SPY 5m bar 跌破 15m 13EMA 次数超出 1，输出 `False, False`，拦截虚假看多；
- 针对 2026-09-04 11:30 行情：验证时间超出 11:00 窗口直接返回 `False, False`；
- 针对 2026-09-03 09:30 单边大涨行情：验证 SPY 5m bar 跌破 15m 13EMA 次数 <= 1，开盘回调 <= 1.20 点，精准识别为多头 Trend Day；
- 严禁触发任何全量历史数据回填。
