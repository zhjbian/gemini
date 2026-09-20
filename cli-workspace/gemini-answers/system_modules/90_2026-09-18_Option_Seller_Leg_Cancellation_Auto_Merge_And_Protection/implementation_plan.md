# 同合约单腿相消合并的自动撤单、系统重构与追踪保护方案

## 1. 业务背景与问题定义

当自动机制或交易员在同一交易日、同一到期日（例如 0DTE）相继开出两笔或多笔同方向垂直价差时，如果中间单腿行权价重叠：
- **典型案例（实盘 2026-09-18）**：
  - 前序开仓：4 手 SPY 757P/755P Bull Put Spread（卖 757P，买 755P，净权利金 $0.17）。
  - 后续开仓：4 手 SPY 755P/753P Bull Put Spread（卖 755P，买 753P，净权利金 $0.12）。
- **券商底层相消机制（Charles Schwab Netting）**：
  - 券商底层持仓按单腿合约净头寸管理。
  - 755P 被单子 A 买入 4 手，又被单子 B 卖出 4 手，在券商账户中**净头寸归零（相消）**。
  - 券商侧实际剩余的净敞口为：-4 手 757P，+4 手 753P（即 4 手宽 4 点的 757P/753P Bull Put Spread）。
- **致命隐患（Fatal Danger）**：
  - 系统此前已为 755P/753P 挂上了休息型限价止盈单（Resting Limit Order），包含 `BUY_TO_CLOSE 755P`。
  - 由于券商侧 755P 净持仓已为 0，该单在券商端会被视作 **`BUY_TO_OPEN 755P`（新开多头）**。
  - 一旦市场波动触发该挂单成交，券商账户将凭空新买入 4 手 755P，造成持仓变形、保证金暴增及风控彻底失控。

---

## 2. 方案目标

1. **零风险消除在途冲突**：一旦发生单腿相消，立即在 TOS/Schwab 撤回涉及该相消组合的所有 `WORKING` 挂单（止盈单与止损单）。
2. **系统账本原子重构**：将系统内原始的旧单打上 `MERGED_REPLACED` 标记（保留完整审计链，不计入误判盈亏），从内存在管列表中卸载。
3. **按合并后实际敞口建账**：合成与券商实际净持仓一致的全新价差交易（如 757P/753P），自动拆分为批次 1 与批次 2，重算综合净权利金（如 $0.29）、最大亏损与行权价。
4. **重新挂上标准追踪保护**：
   - 针对新单提交全新合法合规的券商限价平仓止盈单（批次 1 对应 40% 衰减，批次 2 对应 75% 衰减）。
   - 重新配置 220% 止损保护与 30% 浮盈保本移位逻辑，进入 10 秒常态化自主监控。

---

## 3. 核心设计与模块架构

### 模块 A：相消拓扑检测算法 (`_detect_leg_cancellations`)
- **检测时机**：
  1. `open_trade()` 执行成功、entry 单确认 FILLED 后立即触发；
  2. 10 秒监控循环 `_reconcile_broker_positions()` 发现券商实际持仓单腿净额为 0 但两端净额匹配时，作为自动容错触发。
- **数学匹配逻辑**：
  - 扫描同一到期日、同一方向（Put Spread 或 Call Spread）的全部在管活跃单。
  - 构建单腿头寸图：对于交易对 (Trade A, Trade B)，若 `Trade_A.long_strike == Trade_B.short_strike` 且数量匹配。
  - 确认券商真实持仓中该中间行权价净持仓为 0，两端行权价持有相反方向净敞口。
  - 命中相消事件，输出相消实体元数据。

### 模块 B：TOS 紧急撤单管线 (`_cancel_broker_orders_for_merge`)
- **执行动作**：
  1. 收集被合并交易列表中的所有挂单 ID：
     - 包括每笔交易的 `tp_broker_order_id` 与 `sl_broker_order_id`。
  2. 批量调用 `BBTOS.cancel_order(order_id)`。
  3. 调用 `BBTOS.get_order_statuses_map()` 确认涉及该行权价（如 755P, 757P, 753P）的平仓单状态均已变为 `CANCELED`。

### 模块 C：系统账本迁移与状态机 (`_execute_leg_cancellation_merge`)
- **原始单标记与归档**：
  - 更新 DB：`status = 'MERGED_REPLACED'`。
  - 记录 `close_reason = 'AUTO_MERGED_INTO_#<NEW_IDS>'`。
  - 记录 `close_time = now_time()`，`realized_pnl = 0.0`。
  - `entry_evidence` 记录关联的新单 ID 和相消原因。
  - 从 `self.active_trades` 移除。
- **新单生成与入库**：
  - 计算合成参数：
    - 行权价：Short = 757P，Long = 753P。
    - 净权利金 = 加权合成（如 $0.17 + $0.12 = $0.29）。
    - 维持双批次分配：总数 4 手，Tranche 1 分配 2 手，Tranche 2 分配 2 手。
  - 写入 `option_seller_trades`，生成新 ID（如 #298, #299）。
  - `entry_evidence` 记录 `{'is_merged_synthetic': True, 'merged_from_trades': [294, 295, 296, 297]}`。
  - 载入 `self.active_trades`。

### 模块 D：重装追踪保护 (`_rearm_merged_trade_protections`)
- **止盈限价单挂单**：
  - Tranche 1 (2 手): 目标买回价 = round($0.29 * (1 - 0.40), 2) = $0.17。
    向 TOS 提交限价平仓单：`BUY_TO_CLOSE 757P (2手)` + `SELL_TO_CLOSE 753P (2手)` @ $0.17。
  - Tranche 2 (2 手): 目标买回价 = round($0.29 * (1 - 0.75), 2) = $0.07。
    向 TOS 提交限价平仓单：`BUY_TO_CLOSE 757P (2手)` + `SELL_TO_CLOSE 753P (2手)` @ $0.07。
  - 保存并更新新单的 `tp_broker_order_id`。
- **止损与保本监控**：
  - 220% 止损目标价 = round($0.29 * 2.20, 2) = $0.64（净亏损达到 2.2 倍权利金时触发）。
  - 30% 浮盈保本点 = round($0.29 * (1 - 0.30), 2) = $0.20。
  - 纳入监控循环常态化管理。

### 模块 E：前端界面与对账适配 (`bbt_option_seller.html`)
- **历史日志**：
  - 新增 `badge-outcome-merged` 样式，显示为清新浅紫色徽标 `[🔄 合并相消]`，清晰表明该单已平稳迁移至新单。
- **持仓监控**：
  - 活跃持仓显示 757P/753P，打上 `[🧩 合成价差]` 徽标。
  - 对账区自动对齐，漂移警报消除。

---

## 4. 实施与验证步骤

1. **单元测试**：
   - 编写测试用例 `test_leg_cancellation_merge.py`，模拟同合约单腿重叠建仓，验证：
     - 是否正确识别相消关系；
     - 是否触发了所有原 working order 的取消；
     - 原始单是否成功标记为 `MERGED_REPLACED`；
     - 合成新单是否正确计算权利金并挂出新止盈单；
     - 监控循环是否正常追踪新单的 mark 和止盈止损。
2. **实盘数据校准**：
   - 提供一个一键维护命令/接口，可直接把今天已经发生的 #294-#297 平滑迁移为合成的 757P/753P 追踪单，恢复当前账户的自动止盈止损管理。
3. **系统文档归档**：
   - 将实施方案与验收报告整理归档至 `system_modules`，更新 `bbt_trading_modules.html`。
