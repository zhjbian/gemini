# Order Flow 大单方向判断 Rule-based 决策规则独立与并行实现方案

本方案旨在实现对机构订单流大单（ES/NQ 大单大宗成交）的通用 Rule-based 综合方向研判，并将分析模块作为独立、并行的计算引擎与数据实体实现，不与已有的 `spx_gamma_analyst.py` 混淆。

## User Review Required

> [!IMPORTANT]
> **独立计算引擎与数据实体 (Separation of Concerns)**：
> 1. **独立脚本**：新建 `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow/order_flow_big_trade_analyst.py` 作为大宗订单流方向的独立分析器。
> 2. **独立表结构**：新建 `order_flow_big_trade_signals` 数据库物理表（由 SQLAlchemy 实体 `OrderFlowBigTradeSignal` 映射），专用于持久化大宗订单流的研判结果。
> 3. **独立 API 接口**：添加 `/data/order_flow_big_trade_decision` 路由，前端并行调用该接口，与 `/data/spx_gamma_decision` 实现解耦和并行。

> [!IMPORTANT]
> **L1 / L2 信号权重提升策略 (Signal Weight Amplification)**：
> * **识别源**：同时从**数据库持久化字段 (`signal` 列)** 与**动态重算**两个维度识别 ES PM 和 RTH_FH 的 L1 / L2 信号：
>   - **判断规则**：Net Volume >= 900 且反向成交占比 Counter Pct < 25%。
>     - L1 级别：900 <= Net Volume < 2000。
>     - L2 级别：Net Volume >= 2000。
> * **权重倍率**：
>   - 触发 **L1** 信号的 session 中，同向大单的权重乘以 **$2.0$**。
>   - 触发 **L2** 信号的 session 中，同向大单的权重乘以 **$3.0$**。
>   - 其它普通大单或不符合信号方向的大单保持原始权重（$1.0$）。

> [!TIP]
> **衰减与折算参数（Scoring Rules）**：
> 1. **PM 对齐**：所有 PM 盘大单的“虚拟发生时刻”在开盘后（`target_time >= 06:25`）均对齐到 `06:25 PT`，以防止盘前大单在盘中计算时衰减殆尽。
> 2. **衰减速度**：半衰期（Half-life）设为 $2.0$ 小时（以小时为单位，衰减因子 $\lambda \approx 0.34657$）。
> 3. **NQ 折算系数**：NQ 权重折算系数设定为 `NQ_TO_ES_MULTIPLIER = 0.5`（即 1 手 NQ 折算为 0.5 手等值 ES 主力大单）。
> 4. **多空共振/背离**：同向共振乘以 $1.2$ 加成，反向背离乘以 $0.8$ 削减。
> 5. **阈值映射**：加权分数 $\ge 800 \implies$ `Bullish`； $\le -800 \implies$ `Bearish`；其它 $\implies$ `Neutral`。

## Proposed Changes

---

### 1. 数据库定义与迁移（Database Layer）

#### [NEW] [order_flow_big_trade_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow/order_flow_big_trade_analyst.py)
* **独立建表**：在 `init_signals_table` 函数中建表 `order_flow_big_trade_signals`：
  - `id` (`INT AUTO_INCREMENT PRIMARY KEY`)
  - `ticker` (`VARCHAR(10)`)
  - `signal_date` (`DATE`)
  - `signal_time` (`TIME`)
  - `direction` (`VARCHAR(32)`)
  - `verdict` (`TEXT`)
  - `created_at` (`DATETIME`)

#### [MODIFY] [models.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py)
* 在 SQLAlchemy 中声明对应的实体 `OrderFlowBigTradeSignal`，以支持后端快速 ORM 查询：
  - `class OrderFlowBigTradeSignal(db.Model)`

---

### 2. 量化计算引擎（Quant Analyst Core）

#### [NEW] [order_flow_big_trade_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow/order_flow_big_trade_analyst.py)
* 核心方法 `analyze_order_flow_big_trade(target_date, target_time_str, save_db=True)`：
  1. 拉取 `order_flow_big_trade` 表中当日且时间小于等于 `target_time_str` 的 `ES` / `NQ` 所有非 Aggregate 大单。
  2. **信号动态识别**：
     - 分别统计当日 ES PM 盘（01:00-06:30）与 RTH_FH 盘（06:30-07:30）的大单净额与 Counter Pct。
     - 若满足 L1 或 L2 门槛，标记该 session 的信号级别与方向。
  3. 对齐 PM 盘交易时间：当 `ref_dt` 达到 `06:25 PT` 时，将 PM 交易的虚拟时间设为 `06:25 PT`，否则用实际时间。
  4. **大单加权计算**：
     - 分别计算 ES 与 NQ 的时间加权得分：$Score_i = S_i \times V_i \times W_i \times M_i$，其中 $M_i$ 为信号乘数（L1 对应 $2.0$，L2 对应 $3.0$，普通对应 $1.0$），$W_i$ 为衰减权重。
     - 对于 NQ 的交易量，额外乘以折算系数 $0.5$。
  5. 计算总分并应用 $1.2$（共振）或 $0.8$（背离）乘数。
  6. 映射方向并生成中文研判判词 `verdict`。
  7. 物理写入数据库（ON DUPLICATE KEY UPDATE）。

---

### 3. Web 后端数据转发层（Web Backend）

#### [MODIFY] [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py)
* 新增路由：`@bp_bbt_signals.route('/data/order_flow_big_trade_decision')`。
* 接收 `date` 与 `time` 参数，查询 `OrderFlowBigTradeSignal` 记录，并在缓存未击中或请求特定条件时，动态调用 `order_flow_big_trade_analyst.py` 触发计算并写入数据库，最后返回 JSON。

---

### 4. 前端 UI 动态呈现（Frontend UI）

#### [MODIFY] [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js)
* **元素 ID 预埋**：在渲染决策表 HTML 模板（第 3 行：`Order Flow大单方向判断`）时，为方向 TD、简短依据 TD 及详情的 DIV 预埋专属 ID 占位符。
* **异步并行加载**：
  - 在 `window.fetchRealtimeSignals` 中，触发完 `/data/spx_gamma_decision` 后，在并行区域内异步请求 `/data/order_flow_big_trade_decision`。
  - 数据返回时，将结果缓存至闭包变量 `lastOrderFlowBigTradeSignal` 中，并调用 `updateOrderFlowBigTradeUI(ofSignal)` 更新 DOM 元素。
  - 在 `updateSpxGammaMetricsUI`（重新渲染整张表格）之后，立即重播该缓存以确保在竞态（Race Condition）下大单结果能正常载入表格。
* **浏览器缓存强刷**：在模板文件 [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html) 中将静态引用版本提升为 `?v=1.1.0`。

---

## Verification Plan

### Automated Tests
- 运行测试回测命令：
  `python3 PyTools/order_flow/order_flow_big_trade_analyst.py -d 2026-06-05 -t 11:00`
  验证终端打印的大单指数衰减明细，核实 `direction` 和 `verdict` 生成无语法报错，并成功在数据库中建立 `order_flow_big_trade_signals` 表并插入数据。

### Manual Verification
- 启动 Flask 服务器，访问 `/bbt_signals`。
- 执行 Backtest（如 2026-06-05 11:00），核对“Order Flow大单方向判断”行的 Badge 从 Loading 状态变为具体的方向和依据，保证无硬编码 Dummy 信息。
