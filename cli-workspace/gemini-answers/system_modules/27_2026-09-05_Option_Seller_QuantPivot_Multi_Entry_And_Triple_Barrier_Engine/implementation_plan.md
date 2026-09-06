# 场景二 QuantPivot 边界多轮复利开仓机制与三维风控拦截 实施计划

## 背景与目标
在期权卖方系统的【场景二：非趋势震荡日 QuantPivot 边界反向开仓】中，此前采用了严格的单日单向只触发一次（One-Shot Per Sub-Scenario Per Day）的刚性限制，导致在全天反复震荡筑底或触顶行情中（例如 2026-09-04 08:30 L1 探底全胜止盈后，10:45 ~ 11:00 再次回踩 L1），系统错失了第二次高确定性的收租复利良机。

用户要求将单日仅限 1 次放宽为**可多次开仓**，并在每个具体点位（`L1`, `L2`, `H1`, `H2`）上严格执行以下三维开仓条件：
1. **条件 (1)**：该点位当前没有处于已开仓但未完全平仓（`not completely closed`）的活跃仓位；
2. **条件 (2)**：该点位历史上没有已平仓但亏损（`realized_pnl < 0`）的仓位（一旦该点位破位造成实质亏损，单日内该点位永久关闭，绝不在已击穿的支撑/阻力上反复接飞刀）；
3. **条件 (3)**：距离该点位上一次开仓时间已经超过 **45 分钟**（`cooldown > 45 mins`）。

---

## 架构设计与改动范围

### 1. 核心状态追踪与校验引擎 (`PyTools/option_seller/option_seller_manager.py`)
- **废除粗糙的单日单次锁**：
  - 将原本简单的 `self.counter_trend_triggered_today: set` 升级为面向具体点位的精细化生命周期仲裁器：
    `can_open_quant_pivot_level(target_level: str, current_time: str) -> Tuple[bool, str]`
- **精细化三维过滤器实现**：
  - **检查 1（活跃单互斥）**：遍历 `self.active_trades`，若存在任意活跃单的 `quant_pivot_level == target_level`，拦截开仓（原因：`Holding active position on {target_level}`）；
  - **检查 2（亏损点位熔断）**：查询当日数据库中该点位已平仓的所有交易流水，若存在任意交易 `realized_pnl < 0`（包括硬止损或亏损离场），拦截开仓（原因：`Loss recorded on {target_level} today (PnL < $0)`）；
  - **检查 3（45分钟冷却保护）**：获取该点位当日最新一次开仓时间 `last_open_time`，计算流逝分钟数：
    若 `elapsed_minutes <= 45`，拦截开仓（原因：`Cooldown active on {target_level} ({elapsed_minutes}m <= 45m)`）；
- **联动伏击条件单预置与触发**：
  - 在装配 `ARMED` 伏击条件单以及 10 秒高频轮询触发时，均统一调用 `can_open_quant_pivot_level`，杜绝重复挂单或违规触发。

### 2. 历史模拟回溯系统同步重构 (`PyTools/option_seller/backfill_option_seller_simulated_trades.py`)
- 在回溯脚本中维护与实盘 100% 对齐的 `level_trade_history = {'L1': [], 'L2': [], 'H1': [], 'H2': []}` 状态机；
- 回溯遍历到每个 5 分钟截面时，若触发场景二，严格按三维规则检查是否放行第二次/多次开仓；
- 开仓时记录开仓时间与点位，平仓时更新其盈亏结果，实现 2026-09-04 真实数据上第二次 L1 回踩（约 10:50 附近）的合规开仓与回测。

### 3. 全系统规则手册与模块文档归档
- 更新 `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` 及 `.md` 规则手册中的场景二规则定义（从 One-Shot 修正为点位独立的三维复利准入规则）；
- 归档模块实施计划与验收报告至 `system_modules`，并更新 `bbt_trading_modules.html`（增至 27 项模块）。

---

## 验证与验收方案
1. **单元与逻辑测试**：
   - 验证同一时间已有活跃单时的拦截；
   - 验证上一单发生亏损时的永久阻断；
   - 验证 45 分钟以内（如 30 分钟）的冷却拦截；
   - 验证大于 45 分钟且前单盈利结案时的成功放行。
2. **2026-09-04 真实全日回测验证**：
   - 验证 08:30:00 第一次 L1 触发正常开仓（08:55:00 全部盈利结案）；
   - 验证盘中第二次回踩 L1（相隔 > 45 分钟，且无持仓无亏损）时成功开出第二轮复利开仓。
