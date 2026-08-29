# 5分钟 DOM 哨兵规则引擎实施方案 (DOM 5-Min Sentinel Rule Engine - 500ms Uniform Resampling)

将订单流实时哨兵 `order_flow_sentinel.py`（5分钟检测周期）与 DOM 深度微观特征深度融合，建立“**纯规则毫秒级定量扫描 + 盘口极端异动唤醒大模型 AI 深度研判**”的高性能双层混合架构。

---

## 架构升级与采样设计决策

1. **为什么不能只分析哨兵触发时刻的单笔 DOM Snapshot？**
   * **偶发性与瞬态噪音**：单笔挂单快照容易受高频算法瞬间垫单、撤单闪烁（Jitter）误导，无法反映盘口真实的势能积累；
   * **时间序列连续性**：真实的机构吸筹、被动冰山防御或逼空真空需要一定的时间维度持续验证。

2. **500ms 离散重采样网格 (500ms Uniform Grid - 600 Bins)**:
   * 对应 MotiveWave Java 端 `StudyOrderFlowDataExporter.java` 的 `SNAPSHOT_INTERVAL_MS = 500`；
   * 在过去 5 分钟（300 秒）窗口内，建立严格的 `300s / 0.5s = 600` 个离散时间网格；
   * 对 600 个时间步长进行状态前向填充（Forward-Fill），计算每个步长的多梯队失衡度、步长间差分（撤单/堆单）以及流动性真空断层；
   * 提炼出 5 分钟微观动量（`imb_momentum = late_w_imb - early_w_imb`）与真空持续秒数（`vacuum_bid_sec` / `vacuum_ask_sec`）。

3. **极端异动事件驱动唤醒 AI (Event-Driven AI)**:
   * 当 500ms 网格规则引擎检测到**持续真空逼空/破位**、**密集冰山单吸筹**或**防线筑底加固**时，表明盘口发生结构性突变；
   * 哨兵立即唤醒 `run_ai_tape_analyst(date_str, target_time, --sentinel)`，由 Gemini 大模型对 5 分钟 DOM 深度全景与已成交 Ticks 进行全局综合研判。

---

## 实施计划

### 1. [dom_sentinel_evaluator.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/dom_sentinel_evaluator.py)
* **500ms 均匀网格重采样提取器 (`extract_5m_dom_metrics`)**：
  * 构建 `[target_ts - 300,000ms, target_ts]` 内步长为 500ms 的 600 个时间点；
  * 前向推进原始快照，生成 600 组挂单深度指标序列；
  * 计算序列均值：`imb_near`, `imb_mid`, `imb_deep`, `weighted_imbalance`；
  * 计算 5 分钟微观动量：前半段 2.5 分钟均值 vs 后半段 2.5 分钟均值，得出 `imb_momentum`；
  * 计算 500ms 步长差分：`diff < -50` 累计撤单，`diff > 50` 累计堆单；
  * 计算真空持续时间：单档挂单 < 10 手的步长数转换为持续秒数。
* **基于 500ms 序列的核心规则判定 (`evaluate_5m_dom_rules`)**：
  1. **流动性真空逼空/破位触发 (Vacuum Squeeze/Breakdown)**：
     * 卖方真空持续 `>= 1.5s` + 近端失衡或动量看多 + 买方堆单 -> 触发 `is_dom_bull_high`
     * 买方真空持续 `>= 1.5s` + 近端失衡或动量看空 + 卖方堆单 -> 触发 `is_dom_bear_high`
  2. **微观冰山密集吸收触发 (Iceberg Burst)**：
     * 底部冰山吸筹：`iceberg_bull >= 2` 且 `price_position_pct <= 45%` -> 触发 `is_dom_bull_high`
     * 高位冰山派发：`iceberg_bear >= 2` 且 `price_position_pct >= 55%` -> 触发 `is_dom_bear_high`
  3. **虚假撤单诱多/诱空陷阱过滤 (Spoofing Trap Filter)**：
     * 买方撤单激增且占比 >= 70% -> 屏蔽一切多头信号 (`block_bull_by_spoof = True`)
     * 卖方撤单激增且占比 >= 70% -> 屏蔽一切空头信号 (`block_bear_by_spoof = True`)
  4. **四维共识评分 (Consensus)**。

### 2. [order_flow_sentinel.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_sentinel.py)
* 调取 500ms 重采样评估器，打印包含样本数、加权失衡、首尾动量与真空持续时长的详细诊断面板；
* 整合触发信号并执行诱多/诱空陷阱安全防护。

### 3. 归档与规则手册同步 (Rules 10 & 11)
* 更新 `system_modules/11_2026-08-29_DOM_5Min_Sentinel_Rule_Engine/`；
* 同步 `bbt_trading_modules.html`；
* 同步更新规则手册。
