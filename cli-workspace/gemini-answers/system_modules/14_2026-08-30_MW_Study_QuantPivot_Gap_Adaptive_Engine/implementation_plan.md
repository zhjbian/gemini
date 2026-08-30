# MotiveWave QuantPivot 指标与跳空跨时段自适应计算模块实施计划 (MW Study Implementation Plan)

## 一、 背景与业务目标

本次开发独立归属于 **MotiveWave Study (MW Study)** 体系，旨在将用户在 TradingView 上表现优异的日内量化枢轴指标 `QuantPivots`（源码位于 `PyTools/other_lang/pine_script/BB_QuantPivot.pl`）高精度移植到 MotiveWave，并实现期货跳空跨时段非对称自适应计算：
- `Open` (pO): RTH 官方开盘价 (09:30 EST / 06:30 PST)
- `H1`: 日内平均期望上行耗竭位 (阻力 1)
- `H2`: 极端上行耗竭位 (阻力 2，均值 + 1 倍标准差，约 84% 概率在 H2 之下)
- `L1`: 日内平均期望下行耗竭位 (支撑 1)
- `L2`: 极端下行耗竭位 (支撑 2，均值 - 1 倍标准差，约 84% 概率在 L2 之上)

在看盘实战中（例如 2026-08-28 SPY 经典走势：早盘冲高触及 H1 遇阻暴跌，午盘下探触及 L1 探底企稳回升），日内价格移动到 H1/H2 与 L1/L2 时，大概率遇到统计学波动率耗竭并发生反转，是期权卖方建立高胜率信用价差的极佳机会。

### 核心任务分解：
1. **MotiveWave 端对齐与部署**：排查并修复 `StudyQuantPivot.java` 与 TradingView 之间的计算偏差，确保两者输出 100% 精确一致，并通过 Ant 编译打包部署热生效。
2. **Python 端核心算法与评级模块**：编写高精度 `QuantPivotCalculator`，支持通过历史行情计算 30 日样本均值/标准差及日内反转区间评估。
3. **Option Seller 引擎四维共振升级**：在 5 分钟决策引擎的 **维度 3（关键价位共振）** 中注入 QuantPivot 反转加权（触及 H1/H2 承压 -> 赋予 Bearish 评分卖 Call；触及 L1/L2 企稳 -> 赋予 Bullish 评分卖 Put），并支持与 Smashelito 拍卖枢轴双重共振。
4. **期权行权价优选锚定升级**：卖 Call 优先将 Short Strike 锚定在 `>= H2`，卖 Put 优先将 Short Strike 锚定在 `<= L2`，构筑坚固的统计学波动率护城河。
5. **打通数据巡检管道**：在 `order_flow_sentinel.py` 与 `option_seller_manager.py` 的 5 分钟常态化巡检中注入 QuantPivot 数据流。
6. **单元测试与全量回测**：验证 2026-08-28 SPY 经典反转切片与双向交易逻辑，确保规则通用性与对称性。
7. **规范文档归档**：严格遵循用户规则 10 与 11，更新交易规则手册并在 `system_modules` 中建立模块归档。

---

## 二、 实施方案与技术架构

### 1. 架构模块划分

```
[市场日线历史数据 (纯 RTH 30日)]
              │
              ▼
    QuantPivotCalculator
    (aveUp, upSD, aveDown, downSD)
              │
              ├──> MotiveWave (StudyQuantPivot.java) -> 图表视觉对齐
              │
              └──> Python (PyTools/pivots/quant_pivot.py)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
  5分钟多维共振决策引擎          期权行权价优选引擎
(OptionSellerEngine.evaluate)  (OptionSellerEngine.find_optimal_spread)
  - 维度 3: QuantPivot 反转区      - 卖 Call: Short Strike >= H2
  - H1/H2 承压 -> Bearish +8~12   - 卖 Put: Short Strike <= L2
  - L1/L2 企稳 -> Bullish +8~12
              │
              ▼
   5分钟常规巡检驱动链路
(order_flow_sentinel.py -> option_seller_manager.py)
```

---

## 三、 修改与交付清单

1. **MotiveWave 研究插件**：
   - `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyQuantPivot.java`
2. **Python 量化计算模块**：
   - `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/pivots/quant_pivot.py`
3. **Option Seller 决策引擎**：
   - `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_engine.py`
4. **Option Seller 交易管理器**：
   - `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py`
5. **5分钟常规巡检管道**：
   - `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_sentinel.py`
6. **单元测试集**：
   - `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/test_quant_pivot_option_seller.py`
7. **规则手册与系统模块文档**：
   - `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` & `.md`
   - `system_modules/14_2026-08-30_MW_Study_QuantPivot_Gap_Adaptive_Engine/`
   - 更新 `bbt_trading_modules.html` 并登记模块 14（MW Study 分类）。
