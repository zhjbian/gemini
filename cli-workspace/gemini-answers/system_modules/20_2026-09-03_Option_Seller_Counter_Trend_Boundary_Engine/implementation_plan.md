# 系统模块 20 实施计划：极值耗竭与震荡边界反向期权卖方独立开仓引擎
## (Module 20: Extreme Exhaustion & Range Boundary Counter-Trend Engine Implementation Plan)

- **模块编号**: 20
- **创建时间**: 2026-09-03
- **涉及核心文件**:
  - `PyTools/option_seller/option_seller_engine.py` (开仓机会判定与行权价锚定)
  - `PyTools/option_seller/option_seller_manager.py` (主轮询挂载、防重入守护与开仓执行)
  - `system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` & `.md` (规则手册第 11 节)

---

### 一、背景与动机 (Motivation & Purpose)

原有的期权卖方全自动开仓通道主要针对“单边大趋势启动时顺势反向开仓”（如大盘暴涨启动时卖 Bull Put Spread）。但在真实的交易实战中，期权卖方另有两大核心盈利场景：
1. **场景 1（大单边趋势日极限终点反向开仓）**：大单边趋势行情推进到极端终点，单日做市商最大 Gamma Bar 所在的 Strike 大概率为日内终点。此时站在终点线外侧卖出反向期权，享有最高的空间安全垫。
2. **场景 2（非趋势震荡日边界反向开仓）**：非趋势震荡拉锯日，依托基于 30 日真实波幅的 QuantPivot H1/H2 与 L1/L2 边界，在触顶/探底时反向开仓吃双向时间价值。

---

### 二、用户定制核心参数规范 (User Specifications)

1. **绝对锚定平衡型 (Balanced) 为基准主力**：
   - 价差宽度 `2.0 点`；
   - 基础安全垫缓冲 `>= 0.45%`；
   - Delta `~0.16`；
   - **叠加刚性外侧防线**：
     - 卖 Call 时：Short Call Strike 必须严格 `>= Max Call Gamma Strike`（且 `>= H2`）；
     - 卖 Put 时：Short Put Strike 必须严格 `<= Max Put Gamma Strike`（且 `<= L2`）。
2. **精准点位触发阈值**：
   - 冲顶卖 Call 触发线：SPX 现价进入 `[Call Wall - 4.0, Call Wall + 2.0]`（例如 Call Wall 7750，SPX 涨至 7746 以上触发）；
   - 探底卖 Put 触发线：SPX 现价进入 `[Put Wall - 2.0, Put Wall + 4.0]`（例如 Put Wall 7750，SPX 跌至 7754 以下触发）。

---

### 三、系统执行与风控闭环

1. **独立通道地位**：不受主趋势 5m 漏斗 55 分门槛限制，满足条件即时触发；
2. **单日单向防重入保护 (One-Shot Guard)**：每个子场景（冲顶/探底/上边界/下边界）单日仅触发一次；
3. **风控接管**：统一移交 10 秒盯市守护线程，执行 40%/75% 止盈、2.20 倍硬止损与 12:30 PST 强制全平。
