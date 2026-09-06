# 期权卖方风格权利金门槛优化与回溯 SPY 真实盘口对齐 实施计划 (Implementation Plan)

## 背景与目标
在期权卖方日内交易平台中，前期设定的最低权利金门槛（平衡型 $0.18，保守型 $0.08，激进型 $0.28）在低波动率（Low IV）交易日或日内深度极值支撑位（如 QuantPivot L1/L2）往往过高，导致系统即便精准研判出左侧高胜率反弹机会（QUALIFIED），却因 0DTE 远端价差权利金被压缩至 $0.05 左右而屡屡错失开仓良机。
同时，历史模拟回溯脚本（`backfill_option_seller_simulated_trades.py`）中此前简单使用 `ES / 10` 估算 SPY 现价，因期货基差（Basis Gap 约 2.5 点）导致回溯误判距离未破 L1。

为了攻克上述问题，需要：
1. **全局调低权利金准入门槛**：
   - 🛡️ **保守型 (CONSERVATIVE)**：最低净权利金由 $0.08 降至 **$0.03**；
   - ⚖️ **平衡型 (BALANCED)**：最低净权利金由 $0.18 降至 **$0.05**；
   - ⚡ **激进型 (AGGRESSIVE)**：最低净权利金由 $0.28 降至 **$0.12**。
2. **回溯脚本 SPY 真实盘口现价对齐**：
   - 彻底废除 `round(curr_p / 10.0, 2)` 粗算，优先从 QuantData 期权合约底层现价字段提取高精度 1 分钟 SPY 真实价格；
3. **闭环重放验证**：
   - 在 2026-09-04 真实历史上验证 08:30:00 L1（768.99）处成功开仓 765/763 Put Spread（Net Credit $0.05），并在随后的 08:41 与 08:55 自动双批次全胜止盈。

---

## 架构设计与改动范围

### 1. 核心策略配置更新 (`PyTools/option_seller/option_seller_engine.py`)
- 更新 `OptionSellerEngine.RISK_PROFILES` 中三个风格字典的 `min_credit` 与 `desc` 描述。

### 2. 实盘执行与降级参数对齐 (`PyTools/option_seller/option_seller_manager.py` & `bbt_data_web/data_app/bbt_option_seller.py`)
- 更新 `OptionSellerManager._evaluate_conditional_orders` 中的默认最低权利金，与新版平衡型 $0.05 对齐；
- 同步更新 Web API 接口中的缺省权利金逻辑。

### 3. 回溯引擎高精度盘口对齐 (`PyTools/option_seller/backfill_option_seller_simulated_trades.py`)
- 在 5m 仲裁循环中，直接读取 `ref_df`（SPY 真实 1 分钟 Underlying Close），彻底消除 ES 基差干扰；
- 继承 `OptionSellerEngine` 最新的最低权利金标准进行合约遴选。

---

## 验证与验收方案
1. **真实数据回测验证**：针对 2026-09-04 执行完整回溯，验证 08:30:00 是否精准开仓与双批次止盈。
2. **全系统交易规则手册更新**：更新 `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` 及 `.md` 规则手册中的权利金底线定义。
