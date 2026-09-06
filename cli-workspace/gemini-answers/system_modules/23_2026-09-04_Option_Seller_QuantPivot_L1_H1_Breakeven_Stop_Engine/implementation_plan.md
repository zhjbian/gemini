# 实施计划：QuantPivot L1/H1 触发单 30% 浮盈保本止损与双批次联动机制 (Plan)

## 任务背景与核心目标
在 0DTE / 1DTE 期权卖方自动化交易中，**场景二（非趋势震荡日 QuantPivot 边界反向开仓）** 依托 30 日真实日线波动率计算的 L1/L2（下轨支撑）与 H1/H2（上轨阻力）开仓。
然而微观结构规律表明：
- **L1 和 H1 属于一级波动率边界**，当行情存在较强动能或发生假反抽时，价格有一定概率在微幅反弹后迅速衰竭，并接着跌向 L2 或涨向 H2；
- 若双批次仓位仅等待 40% (Tranche 1) 和 75% (Tranche 2) 的常规止盈，极易出现“短暂浮盈 20%~35% 后被反向大单击穿并直接打到 2.2x 硬止损”的不利局面。

### 核心改进方案：
1. **10 秒守护线程高频巡检**：在 `OptionSellerManager._evaluate_active_positions()` 中，针对 QuantPivot L1 或 H1 触发的持仓，计算实时衰减浮盈比例；
2. **浮盈 >= 30% 触发双单保本 (Breakeven Shift)**：一旦浮盈比例达到或超过 30%，系统**同时将两手持仓（Tranche 1 和 Tranche 2）的条件止损价提升至开仓净权利金价格**（`stop_loss_price = net_credit`，即 $0.00 零亏损保本防线）；
3. **阶梯止盈点位保持不变**：Tranche 1 依然维持 40% 快速减仓止盈，Tranche 2 依然维持 75% 深度收割止盈；
4. **平仓状态与通知联动**：若后续反转失败回踩成本价，以 `CLOSED_BREAKEVEN_L1_H1` 状态退出，已实现损益精确结算为 $0.00，并派发专属通知邮件。

---

## 涉及修改的模块与代码

### 1. 决策与订单流预埋引擎 (`PyTools/option_seller/option_seller_engine.py`)
- 在 `evaluate_auto_counter_trend_setups` 的 Case 2A 和 Case 2B 中：
  - 判定触发边界是否为 `'L1'` 或 `'H1'`（相对于 `'L2'` 或 `'H2'`）；
  - 在 `debug_info` 与 `armed_order` 中显式注入 `is_l1_h1_pivot_trade = True` 和 `quant_pivot_level = 'L1' / 'H1'` 标识。

### 2. 生命周期与交易执行管理器 (`PyTools/option_seller/option_seller_manager.py`)
- **持仓加载恢复 (`_reload_active_trades`)**：从数据库 `entry_evidence` 中反序列化恢复 `is_l1_h1_pivot_trade`、`quant_pivot_level` 与 `is_l1_h1_be_activated` 状态；
- **单笔与双批次开仓 (`_open_single_contract` & `open_trade`)**：将 `is_l1_h1_pivot_trade` 与 `quant_pivot_level` 穿透传递至两批次持仓字典与数据库持久化；
- **条件单触发 (`_evaluate_conditional_orders`)**：从预置伏击单中提取 L1/H1 标记并写入开仓 evidence；
- **双批次保本推进逻辑 (`_activate_l1_h1_breakeven_stops`)**：
  - 新增专用方法，查找同组 Tranche 1 与 Tranche 2；
  - 同时修改 `stop_loss_price = net_credit`，标记 `is_l1_h1_be_activated = True`；
  - 持久化更新数据库 `entry_evidence`；
  - 调度邮件通知模块派发保本生效告警；
- **10秒生命周期轮询 (`_evaluate_active_positions`)**：
  - 在常规退出检查前，计算浮盈比例 `profit_pct = (net_credit - current_close_cost) / net_credit`；
  - 若 `is_l1_h1 and not is_l1_h1_be and profit_pct >= 0.30`，触发保本提升；
  - 止损仲裁时区分 `CLOSED_BREAKEVEN_L1_H1`，确保 dry-run 及实盘平仓价精确锚定保本价。

### 3. 告警通知引擎 (`PyTools/option_seller/option_seller_notifier.py`)
- 在 `notify_trade_closed` 中补充 `CLOSED_BREAKEVEN_L1_H1` 专有文案与蓝色保本徽章；
- 新增 `notify_l1_h1_breakeven_activated` 类方法，提供清晰的 30% 浮盈保本激活邮件。

### 4. 前端监控界面 (`bbt_data_web/templates/bbt_option_seller.html`)
- 在活跃持仓卡片中展示 `L1/H1双保本` 徽章，并在止损说明处显示 `已保本损: $0.xx (双批次零风险)`。

### 5. 规则手册与系统索引归档
- 更新 `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` 及 `.md`；
- 更新 `bbt_trading_modules.html`。
