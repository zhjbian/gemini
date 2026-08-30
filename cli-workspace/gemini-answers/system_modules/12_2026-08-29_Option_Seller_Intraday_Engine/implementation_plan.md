# Option Seller 日内期权卖方自动交易系统实施计划 (SPY 0DTE Vertical Credit Spread Engine)

本方案基于 **BBT.AI (BBT.AI)** 的工业化期权卖方四步闭环体系（`DISCOVER` -> `STRUCTURE` -> `MANAGE` -> `REVIEW`），融合当前量化体系已有的 **Order Flow 5分钟哨兵双引擎、SPX/SPY Gamma 做市商对冲水位、趋势日防护罩**，并在 **TOS / Schwab API (`schwab-py`)** 上构建从信号触发、行权价仲裁、两腿定义风险组合下单、持仓动态风控管理到独立 Web 监控控制台的完整自动化实盘系统。

---

## 策略设计与关键决策说明

> [!IMPORTANT]
> **标的策略与风险限定底线**
> 1. **严禁单腿裸卖（No Naked Selling）**：日内自动化系统 100% 采用**两腿垂直信用价差（Vertical Credit Spread）**，开仓即硬性锁定最大可能亏损，彻底消除因断网或跳水导致的单腿爆仓隐患；
> 2. **首发实盘标的锁定为 SPY 0DTE**：行权价跨度 1.0 点（每手风险基数为 100 美元），以极小且确定可控的试错成本打磨实际成交滑点与执行链路；未来仅需更改参数配置即可平滑无缝升级至 SPX 0DTE；
> 3. **独立监控页面开发**：不增加 `bbt_signals` 原有页面的复杂度，开辟全新独立的 `/bbt_option_seller` 自动化交易专属控制台。

---

## 四大核心业务模块与架构设计

### 1. 模块一：DISCOVER (卖方窗口发现与过滤引擎)
并非全天都适合开仓卖期权，系统必须在胜率处于统计学绝对高位时方可发出准入许可：
- **市场状态过滤 (Regime Filter)**：
  - **正 Gamma 状态 (Net Long Gamma)**：做市商逆势对冲压制波动率，优先允许开仓宽幅价差；
  - **负 Gamma 状态 (Net Negative Gamma)**：市场存在顺势单边暴走风险，仅在极端吸收反转或背离确认时谨慎顺势开仓。
- **趋势日均线带防护罩 (Trend Day Shield)**：
  - 若处于多头趋势日（15m EMA 多头排列且价格运行于通道上方），**严禁卖 Call Spread 逆势摸顶**，只允许顺势做 Bull Put Spread；
  - 若处于空头趋势日，**严禁卖 Put Spread 逆势抄底**，只允许顺势做 Bear Call Spread。
- **微观信号共振 (Micro Sentinel Trigger)**：
  - 5分钟哨兵触发 HIGH 看多信号（或 DOM 冰山单密集吸收 `iceberg_bull >= 2`），触发 Bull Put Spread 备选窗口；
  - 5分钟哨兵触发 HIGH 看空信号，触发 Bear Call Spread 备选窗口；
  - 若命中 DOM 诱多/诱空撤单陷阱，强制封杀对应方向的价差开仓。

### 2. 模块二：STRUCTURE (价差合约组装与行权价仲裁引擎)
根据当前 SPY 现价与实时期权链，秒级动态筛选最优合约对：
- **卖方腿（Short Leg，核心创收端）**：
  - **目标 Delta 区间**：`0.08 ~ 0.15`（对应无风险过期胜率约 85% ~ 92%）；
  - **安全垫距离校验**：卖方行权价距离当前标的现价必须满足：
    - Put 腿：`Short Strike <= SPY 现价 - 0.75%`（或位于当日 Smashelito S1 / Put Wall 下方）；
    - Call 腿：`Short Strike >= SPY 现价 + 0.75%`（或位于当日 Smashelito R1 / Call Wall 上方）。
- **买方保护腿（Long Leg，最大亏损封口端）**：
  - 行权价严格设置在与卖方腿间隔 **1.0 点**（例如 Short 550P，则 Long 549P）；
  - **最大可能亏损公式**：`Max Loss = (Spread Width - Net Credit) * 100`。
- **权利金底线过滤 (Minimum Premium Filter)**：
  - 1.0 点宽度的垂直价差，净权利金必须 `Net Credit >= $0.20`（即每手收取至少 $20 美元，保证收益风险比不低于 1:4）；若因虚值过深导致权利金不足 $0.15，判定为性价比过低，放弃开仓。

### 3. 模块三：MANAGE (自动化动态持仓生命周期管理引擎)
由后台常驻守护线程（`OptionSellerManager`）每 10~15 秒轮询未平仓组合的 Mark 价格，执行三重风控闭环：
- **规则 1：主动提早止盈 (Take Profit at 60% - 75%)**：
  - 净权利金衰减达到 65% 时自动平仓（例如入场卖出收 $0.35，当价差买回成本降至 $0.12 时主动止盈平仓）；
  - 绝不为了赚取最后 $0.10 美分的时间价值而在尾盘承受不可预测的剧烈 Gamma 逆风。
- **规则 2：硬性止损保护 (Stop Loss at 2.0x - 2.5x)**：
  - 若盘面反向击穿安全垫，价差买回成本上升至开仓权利金的 2.2 倍（例如收 $0.30，成本涨到 $0.66），系统无条件执行市价买回止损平仓，保住绝大部分保证金本金。
- **规则 3：强制时间出场 (Time Stop at 12:30 PST)**：
  - 美西时间 12:30（收盘前半小时），无论盈亏状态，系统全自动发起全部未平仓合约清零平仓，坚决杜绝持有到期引发的美式期权正股交割风险。

### 4. 模块四：REVIEW (全维审计、决策日志与独立 Web 控制台)
- **数据库表结构**：
  - 新增 `order_flow_option_seller_trades` 表，持久化记录每一笔订单的：开仓时间、标的、价差类型、Short/Long 行权价、入场权利金、出场权利金、平仓原因（Take Profit / Stop Loss / Time Stop）、盈亏金额、开仓时的微观信号证据链。
- **独立 Web 页面 (`/bbt_option_seller`)**：
  - 采用现代专业交易台设计，涵盖账户概况条（当日已实现盈亏、保证金占用、胜率）、当前持仓卡片（距离行权价安全垫动态指示条、收益进度环、实时 Greeks）、策略状态机实时雷达以及一键急停与全平开关。

---

## 实施工程分解与修改文件清单

### Component 1: Option Seller 核心策略与状态机 (`PyTools/option_seller/`)
- #### [NEW] [option_seller_engine.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_engine.py)
  - 实现 `OptionSellerEngine` 核心类：
    - `find_optimal_spread(direction, current_price, target_delta=0.12, width=1.0)`
    - `evaluate_entry_conditions(sentinel_signal, gamma_regime, trend_shield)`
    - `execute_order(spread_candidate, dry_run=True)`
- #### [NEW] [option_seller_manager.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py)
  - 独立后台风控线程：
    - 每 15 秒轮询活跃持仓的最新买卖报价与 Mark；
    - 执行止盈（65%）、止损（2.2x 权利金）、时间止损（12:30 PST）；
    - 支持安全模式开关（Dry-run 纸面模拟 vs Live 实盘模式）；
    - 提供手动紧急平仓接口 `emergency_close_all()`。

### Component 2: 底层执行与期权链计算 (`PyTools/tos_api/`)
- #### [MODIFY] [bb_tos.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/tos_api/bb_tos.py)
  - 扩展 Schwab API 订单组装接口：增加 `place_vertical_credit_spread(symbol, exp_date, short_strike, long_strike, spread_type, quantity, limit_credit)` 与 `close_vertical_spread(...)`。
  - 增加 SPY 0DTE 链的高效单次拉取与 Greeks 缓存机制。

### Component 3: 数据库持久化 (`PyTools/db_query.py` & DB Script)
- #### [MODIFY] [db_query.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/db_query.py)
  - 增加 `option_seller_trade_add`、`option_seller_trade_close`、`option_seller_trades_today_query` 等查询与写入函数。

### Component 4: 独立 Web 监控控制台 (`bbt_data_web/`)
- #### [NEW] [bbt_option_seller.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_option_seller.py)
  - 注册 Flask Blueprint `bp_option_seller`，提供：
    - 页面路由：`/bbt_option_seller`
    - 数据接口：`/api/option_seller/status`（实时持仓、Greeks、安全垫、当日交易记录、引擎状态）
    - 操作接口：`/api/option_seller/toggle_engine`、`/api/option_seller/panic_close`、`/api/option_seller/close_position`、`/api/option_seller/scan_now`
- #### [NEW] [bbt_option_seller.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html)
  - 专为期权卖方打造的深色/现代半透明量化控制台页面，支持实时 WebSocket/轮询刷新。
- #### [MODIFY] [bbt_data_app.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/bbt_data_app.py)
  - 注册 `bp_option_seller` 蓝图，并在导航首页追加工具入口，启动持仓监控守护线程。

---

## 验证与验收计划 (Verification Plan)

### 1. 单元测试与询价链验证
- 运行脚本拉取当前 SPY 0DTE（或近月）期权链，测试 `find_optimal_spread()` 能否在 Delta 0.08~0.15 内准确定位 1.0 点宽度的行权价配对；
- 验证计算出的 Net Credit、Max Loss、POP 胜率及安全垫距离计算完全正确。

### 2. 模拟下单与纸面生命周期全流程演练 (Dry-Run Mode)
- 启动 `OptionSellerManager(dry_run=True)`；
- 人工触发一次模拟看多信号，验证系统能否自动记录开仓、实时计算浮动盈亏、并在达到虚拟止盈/止损线时自动触发平仓。

### 3. 独立页面前端交互验证
- 访问 `http://127.0.0.1:5005/bbt_option_seller`，检查：
  - 账户盈亏及统计条正确展示；
  - 活跃持仓卡片、安全垫进度条、Greeks 显示无误；
  - 状态机雷达能正确展示 DISCOVER / STRUCTURE / MANAGE 状态。

### 4. 规范归档 (遵循 User Rule 10 & 11)
- 在 `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/` 下建立 `12_2026-08-29_Option_Seller_Intraday_Engine/`；
- 完整同步 `implementation_plan.md` 与 `walkthrough.md`；
- 更新 `bbt_trading_modules.html`、`README.md` 与 `README.html`。
