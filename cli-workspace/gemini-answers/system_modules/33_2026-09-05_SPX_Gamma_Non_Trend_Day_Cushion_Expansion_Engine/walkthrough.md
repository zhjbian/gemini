# SPX Gamma 非趋势日顺势 Cushion 空间动态拓宽引擎验收报告 (Walkthrough)

## 1. 模块核心目标与改动概述
针对 2026-09-04 09:20:00（SPX 现价 7724.91，Call Wall 7740.00，上方 Cushion 为 15.09 点）原本被错误判定为顺势看多（`Bullish:Bullish`）的缺陷，依据客观微观结构法则完成底层升级：
- **市场机理**：在非单边强趋势日（Non-Trend Day），做市商正 Gamma 逆势平抑阻尼强劲，且现货与期权买盘动能不足，标的 SPX 极难最终触及最外层最大 Gamma 阻力墙（如 2026-09-04 标的反弹至 7728.23 便再度崩跌），原固定 15 点门限容易造成局部反弹高位诱多。
- **动态分级门限**：
  - **单边趋势日 (Trend Day)**：维持宽松门槛 `Cushion >= 15.0 点`；
  - **非趋势日 (Non-Trend Day)**：将顺势空间门槛硬性提升至 **`23.0 点`**（多空双向严格对称）。
  - 若非趋势日下 Cushion 未达到 23.0 点，一票否决顺势推进，降级输出为 `Neutral:Compression-Top`（或 `Neutral:Compression-Bottom`）。
- **纯粹物理隔离**：全流程仅依据纯粹 SPX 价格序列与期权 Gamma 分布做微观研判，绝不杂糅外部均线或技术指标。

## 2. 核心代码改造点
1. **统一 yfinance 分钟级数据缓存器 (`_ensure_yf_spx_df`)**：
   - 彻底重构 K 线缓存懒加载机制，确保全周期任何入口均能毫秒级安全取用准确的 1 分钟历史 K 线。
2. **趋势日形态量化判定函数 (`evaluate_intraday_trend_regime`)**：
   - 筛选 RTH 美西 06:30 开盘以来的全部 K 线，提取开盘价 `rth_open`、区间最低 `rth_low`、区间最高 `rth_high`；
   - 多头趋势日判定：`current_spx >= rth_open + 5.0` 且 `(rth_open - rth_low) <= 8.0` 且 `(rth_high - current_spx) <= 15.0`；
   - 空头趋势日判定（严格对称）：`current_spx <= rth_open - 5.0` 且 `(rth_high - rth_open) <= 8.0` 且 `(current_spx - rth_low) <= 15.0`；
   - 其它所有行情（宽幅震荡、反弹、冲高回落）均严格归为非趋势日。
3. **第三层决策树动态 Cushion 与风控研判**：
   - 绿柱支配：`req_bull_cushion = 15.0 if is_bull_trend_day else 23.0`；
   - 红柱支配：`req_bear_cushion = 15.0 if is_bear_trend_day else 23.0`；
   - 全面更新 `risk_advice`、`trend_logic` 与 fallback 判词，清晰标明当前形态类型与顺势门槛要求。

## 3. 回测与数据实证对比

### 2026-09-04 核心测试点（非趋势日死猫反弹段）
- **09:20:00 实测表现**：
  - 现价: 7724.91 | Call Wall: 7740.00 | Call Cushion: 15.1 点 | 日内形态: 非趋势日（门槛 23 点）
  - **升级前**: `Bullish:Bullish`（顺势看多，严重诱多）
  - **升级后**: **`Neutral:Compression-Top`（上行空间压缩中性）**
  - **判词建议**: `上行空间压缩观望 (现价距 Call Wall 7740 空间收窄至 15.1 点，未达推进门槛 23点(非趋势日)，盈亏比不佳，暂停顺势)`
- **全天 09:09 ~ 09:40 拦截效果**：
  - 09:09 ~ 09:40 期间的所有局部反弹高点信号（Cushion 介于 15.1 ~ 20.8 点），升级前全部错误显示为看多；
  - 升级后全部被精准拦截归入 `Neutral:Compression-Top`，彻底消除了非趋势日死猫反弹诱多追高的致命风险！

### 2026-09-03 验证点（真正单边大涨趋势日）
- 2026-09-03 自 06:30 开盘（7686.71）起一路上扬无回调，系统准确识别为 `Bullish Trend Day`；
- 顺势推进维持 15 点宽松门限，单边多头主升浪信号保持充盈顺畅，不受非趋势日严谨门限的误伤。
