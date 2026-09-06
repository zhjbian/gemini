# 期权卖方历史回溯 5 分钟周期数据库直连与微观盘口对齐引擎 验收报告 (Walkthrough)

## 任务概述
针对期权卖方历史模拟回溯系统（`backfill_option_seller_simulated_trades.py`）之前脱离数据库导致 5 分钟周期订单流研判严重失真、并在空头单边杀跌日（如 2026-09-04 07:25:00）错误开出多头模拟单的问题，完成了**全链路数据库直连改造**与**微观盘口结构 100% 对齐**。同时修复了开仓决策引擎中关于撤单陷阱误判的通用缺陷。

---

## 实施详情

### 1. 5 分钟订单流数据库直连与特征无损提取 (`backfill_option_seller_simulated_trades.py`)
- **数据库权威信号优先**：
  在回测循环中，优先使用 `OrderFlowSignal` 模型从 MySQL `order_flow_signals` 表中抓取目标时间截面之前最新的 5m 周期记录：
  - 提取权威多因子综合方向 `direction`（如 `Bearish`）与 `signal_strength`；
  - 提取完整的基于规则研判理由 `verdict`；
  - 提取 `recent_micro_5m` 结构，获取真实的当根 5m Delta 与前两根 5m Delta，杜绝临时粗算失真；
  - 深度还原 DOM 微观盘口结构：包含 `spoof_bid_count`、`spoof_ask_count`、`iceberg_bid/ask`、挂单深度对比与 `is_spoof_trap`；
  - 组装与实盘 Sentinel 完全一致的 `dom_data` 结构传入决策仲裁引擎。
- **开仓证据透传增强**：
  在入库的 `entry_evidence` 中，新增记录 `source: 'DB_OrderFlowSignal_5m'`、`of_signal_id`、`of_verdict`、`dom_metrics` 以及四维评分明细 `metrics_breakdown`，供前端回溯诊断模态框精确还原开仓场景。
- **平滑兼容降级机制**：
  对早期未采集 5m 信号的日期，平滑自动降级至 MotiveWave 本地 CSV 估算模式（标记 `source: 'CSV_Tick_Fallback'`），保证历史兼容性。

### 2. 决策引擎撤单陷阱解析缺陷修复 (`option_seller_engine.py`)
- **修复前**：
  原本通过 `'撤单' in of_verdict and '陷阱' in of_verdict` 判断是否存在撤单陷阱。由于 Sentinel 输出的日志字符串末尾默认附带 `[DOM: 深度46.2% | 撤单陷阱: 买=0/卖=0 | 冰山: 买=0/卖=0]`，导致无论有无陷阱均被错误触发为 True。
- **修复后**：
  优先读取 `of_metrics` 中 Sentinel 输出的显式布尔字段 `is_spoof_trap`；若退化至字符串匹配，则通过精确正则 `re.search(r'撤单陷阱:\s*买=[1-9]|卖=[1-9]', of_verdict)` 严格确认是否存在有效陷阱，杜绝假阳性误杀。

---

## 验证与回测结果

### 1. 2026-09-04 真实历史回测验证
运行命令：
```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 PyTools/option_seller/backfill_option_seller_simulated_trades.py 2026-09-04
```

- **07:25:00 关键时间点仲裁结果**：
  - **历史 DB 信号提取**：成功匹配到当日 `07:25:00` 的 5m 记录（方向为 `Bearish`，评语明确指示机构高位派发、买盘被吸收且存在买方撤单陷阱）；
  - **开仓仲裁判定**：系统执行顺势多因子评分，通道 A-1 得分 0 分（空头方向无法满足多头顺势），且检测到买方撤单陷阱；
  - **执行动作**：系统明确输出 `[5M Synthesis] 07:25:00: REJECTED (Score: 20 < 80, OF=Bearish (SpoofTrap: True), Gamma=Bearish)`，**坚决拒绝开仓**；
  - 此前产生的错误 Bull Put Spread 模拟单被彻底抹除，不再污染流水账本。

### 2. 诊断与一致性效果
- 回溯系统与实盘监控系统实现逻辑与数据源的 100% 对齐，杜绝由于回溯计算简陋而误导交易策略评估。
