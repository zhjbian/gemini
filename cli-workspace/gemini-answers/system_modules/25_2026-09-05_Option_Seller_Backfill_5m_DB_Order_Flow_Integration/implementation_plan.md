# 期权卖方历史回溯 5 分钟周期数据库直连与微观盘口对齐引擎 实施计划 (Implementation Plan)

## 背景与目标
在期权卖方历史模拟回溯系统（`PyTools/option_seller/backfill_option_seller_simulated_trades.py`）中，原本为了脱离数据库独立运行，仅通过 MotiveWave 本地导出的 Tick CSV 临时粗算当前 5 分钟单根 K 线的累计 Delta。这种离线粗算方式存在严重缺陷：
1. **研判失真**：丢失了 30 分钟大级别背景 Delta 吸收与积累、EMA 均线排列、QuantPivot 极值以及 DOM 200 档盘口微观结构；
2. **假信号频发**：例如在 2026-09-04 07:25:00，当日开盘后空头极度强势且买方存在明显的高频撤单陷阱（Spoof Trap），实盘基于规则的 Sentinel 5m 权威研判明确为 `Bearish`；但回溯脚本仅凭单根 5m 局部反弹的 +315 Delta 误判为 `Bullish` 顺势推进，在空头杀跌背景下开出了错误的 Bull Put Spread 模拟单。

为了彻底消除历史回溯与实盘实况的脱节，需要：
1. 重构回溯脚本，在评估 5 分钟主周期开仓时，优先直接读取数据库 `order_flow_signals` 表中的权威 5 分钟周期记录；
2. 提取并透传完整的 `dom_metrics`（撤单陷阱、冰山委托、买卖挂单差）、微观多因子研判方向 `direction` 与 `verdict`，确保历史回测逻辑与实盘 Sentinel 监控 100% 对齐；
3. 保留无数据库记录历史日期的本地 CSV 降级兼容机制，并在开仓证据中明确标注入库来源。

---

## 架构设计与改动范围

### 1. 数据库直连与特征重构 (`PyTools/option_seller/backfill_option_seller_simulated_trades.py`)
- **引入实体模型**：引入 `from py_lib.order_flow_signal import OrderFlowSignal`，在指定回测日期内精准查询当日 5 分钟周期的所有订单流信号。
- **动态时间截面匹配**：遍历历史时间点 `curr_time` 时，基于 `order_flow_signals` 表匹配最贴合且在开仓时间之前的权威 5m 信号。
- **全量微观特征还原**：
  - 提取权威 `direction`、`signal_strength`、`verdict`；
  - 深度解析 `dom_metrics`（提取 `spoof_bid_count`、`spoof_ask_count`、`iceberg_bid/ask`、`bids_depth`、`asks_depth` 及布尔标签 `is_spoof_trap`）；
  - 从 `recent_micro_5m` 提取真实的当根 5m Delta 与前两根 5m Delta；
  - 构造与实盘 Sentinel 100% 结构一致的 `dom_data` 字典供 `OptionSellerEngine` 仲裁。
- **平滑降级支持**：若特定历史日期数据库无记录，自动平滑退化至本地 CSV 粗算，并在日志与证据中标注 `source: 'CSV_Tick_Fallback'`。
- **开仓证据透传**：在 `entry_evidence` 中持久化记录 `source: 'DB_OrderFlowSignal_5m'`、`of_signal_id`、`of_verdict` 及因子得分明细。

### 2. 撤单陷阱误判缺陷修复 (`PyTools/option_seller/option_seller_engine.py`)
- **根因分析**：`OptionSellerEngine` 在解析 `is_spoof_trap` 时，原本采用简单的文本包含匹配：`'撤单' in of_verdict and '陷阱' in of_verdict`。而 `order_flow_sentinel.py` 生成的 `verdict` 字符串末尾无论有无陷阱均会附带统计标签（如 `[DOM: 深度46.2% | 撤单陷阱: 买=0/卖=0 | 冰山: 买=0/卖=0]`），导致所有包含该标签的研判均被误判为存在撤单陷阱！
- **修复方案**：优先从 `of_metrics` 中获取显式布尔字段 `is_spoof_trap`；若通过文本回退，严格使用正则表达式校验买/卖陷阱计数是否真实大于 0（`买=[1-9]` 或 `卖=[1-9]`）。

---

## 验证与验收方案
1. **针对 2026-09-04 真实数据全天回测**：
   - 验证 07:25:00 时间戳是否成功提取到数据库中真实的 `Bearish` 研判与买方撤单陷阱；
   - 验证该点位是否被系统坚决拒绝开仓（REJECTED），杜绝生成错误模拟多头单；
   - 验证全天其他时间段是否保持理性、严谨的开仓判断。
2. **语法与依赖校验**：在项目 Python 运行环境中进行模块导入与静态编译检查。
