# 5分钟订单流微观结构形态平行判定通道与自适应调参系统 实施方案

## 1. 架构总览与背景诊断

### 1.1 核心问题与设计诉求
当前交易系统的 5 分钟 Order Flow 研判引擎（见规则手册 §1.1「两步判定法核心架构」）主要基于 4 核心分支加权与 11 项客观加分。该基准系统在单边顺势行情表现稳健，但在关键结构拐点处存在一定滞后性（例如在 2026-09-18 09:25 最低点 7677.75 处，由于空头大单压制与趋势日防护罩封杀，传统通道输出 `Neutral:Low-Boundary` 防守）。

而在 `http://127.0.0.1:5005/bbt_research_analytics -> 模块二：订单流微观结构与形态案例 (Order Flow & Microstructure)` 的深度报告中，通过订单流微观机制（被动吸收、由守转攻、诱导洗盘、双频共振、CVD背离）能够提前敏锐捕捉到主力资金在极限位置的吸筹与控盘迹象。

### 1.2 核心设计原则
1. **平行解耦与零侵入性**：保持现有 5 分钟两步判定法（基准通道）100% 不变，绝不修改原有打分与 Setup 闸门输出。新规则以独立的**平行判定通道 (Parallel Microstructure Pattern Channel)** 运行。
2. **多空双向严格对称（符合规则 6）**：所有提取的微观量化规则必须具备严密的数学对称性，同时覆盖多头与空头场景，绝不针对单一案例做硬编码。
3. **公式纯文本表达（符合规则 7）**：所有数学表达式与量化判据统一采用纯文本形式书写，杜绝任何 LaTeX 语法符号。
4. **全链路浅色系视觉规范（符合规则 12）**：UI 与图表均采用白底与清新浅色调，信息分层清晰。

---

## 2. 模块一：订单流微观形态特征提取与量化规则定义 (OF-1 ~ OF-5)

基于案例库报告提炼 5 项正交的纯微观订单流机理，形成客观量化数学判据：

### 规则 OF-1：被动吸收 (Passive Absorption)
- **微观机理**：市价主动单猛烈砸盘/买入，但在关键流动性区域被限价大单（挂单墙）全部吃下，价格未跌破/突破，随后出现 Delta 衰竭或反抽。
- **多头判定条件 (OF-1 Bullish)**：
  1. 价格处于折价区：`price_position_pct <= 30.0` 或 测试当日/昨日关键低点支撑；
  2. 主动卖压显著但被吃：`last_5m_delta < -1500` 或 `net_delta_30m < -3000` 或 出现 `sell_absorbed == True`；
  3. 价格抗跌止跌：5 分钟价格跌幅 `abs(price_change_5m) <= 1.50`（价格跌不动），或 探底留下长下影线；
  4. 主力大单未失控砸穿：`big_trade_net_2h > -5000` 且 未出现机构连续主动向下破位单。
- **空头判定条件 (OF-1 Bearish)**：
  1. 价格处于溢价区：`price_position_pct >= 70.0` 或 测试当日/昨日关键高点阻力；
  2. 主动买盘涌入但被阻截：`last_5m_delta > 1500` 或 `net_delta_30m > 3000` 或 出现 `buy_absorbed == True`；
  3. 价格滞涨触顶：5 分钟价格涨幅 `abs(price_change_5m) <= 1.50`（价格涨不动），或 冲高留下长上影线；
  4. 主力大单未失控买破：`big_trade_net_2h < 5000` 且 未出现机构连续主动向上突破单。

### 规则 OF-2：由守转攻 / 主动发力 (Initiative Shift)
- **微观机理**：资金从被动防守承接迅速切换为主动市价推进，短周期动量爆发。
- **多头判定条件 (OF-2 Bullish)**：
  1. 短窗买动量突增：`last_5m_delta > 800` 且 `last_5m_delta > last_10m_delta * 0.6`；
  2. 价格开始向上脱离：`price_change_5m >= 1.50`；
  3. 主动大单买盘主导：`big_trade_score >= 1.0` 或 `big_orders_net_5m > 0`。
- **空头判定条件 (OF-2 Bearish)**：
  1. 短窗卖动量突增：`last_5m_delta < -800` 且 `last_5m_delta < last_10m_delta * 0.6`；
  2. 价格开始向下脱离：`price_change_5m <= -1.50`；
  3. 主动大单卖盘主导：`big_trade_score <= -1.0` 或 `big_orders_net_5m < 0`。

### 规则 OF-3：诱导洗盘 / 流动性陷阱 (Liquidity Trap & Washout)
- **微观机理**：故意击穿关键支撑/阻力以触发止损盘与突破单，随后以超大单瞬间全量反包回抽。
- **多头判定条件 (OF-3 Bullish)**：
  1. 价格曾瞬间跌破日内低点或关键支撑点位（击穿幅度 1.00 至 3.00 点）；
  2. 5 分钟内迅速收复破位点（收盘价重新站回破位点之上）；
  3. 洗盘时伴随爆量但反包时净买入极强（`washout_bull == True` 或 瞬时 Delta 剧烈 V 转）。
- **空头判定条件 (OF-3 Bearish)**：
  1. 价格曾瞬间刺破日内高点或关键阻力点位（假突破 1.00 至 3.00 点）；
  2. 5 分钟内迅速跌回突破点之下；
  3. 诱多时伴随散户追多但反手时大单断崖砸落（`washout_bear == True` 或 瞬时 Delta 剧烈倒 V 转）。

### 规则 OF-4：双频共振 (Order Book & Flow Confluence)
- **微观机理**：静态 DOM 挂单堆叠优势与动态成交流市价推进形成合力。
- **多头判定条件 (OF-4 Bullish)**：
  1. DOM 盘口买方占优：`imb_short > 0.10` 且 `stack_bid_val > stack_ask_val * 1.3`；
  2. 成交流主动买盘推进：`last_5m_delta > 500` 且 `delta_ratio_5m > 0.15`；
  3. 买单真实性验证：无严重撤单诱捕陷阱（`block_bull_by_spoof == False`）。
- **空头判定条件 (OF-4 Bearish)**：
  1. DOM 盘口卖方占优：`imb_short < -0.10` 且 `stack_ask_val > stack_bid_val * 1.3`；
  2. 成交流主动卖盘推进：`last_5m_delta < -500` 且 `delta_ratio_5m < -0.15`；
  3. 卖单真实性验证：无严重撤单诱捕陷阱（`block_bear_by_spoof == False`）。

### 规则 OF-5：CVD 背离与动能衰竭 (Structural CVD Divergence)
- **微观机理**：价格创出波段极值，但累计成交 Delta 动能未能确认，形成结构性量价背离。
- **多头判定条件 (OF-5 Bullish)**：
  1. 价格处于低位极值区：`price_position_pct <= 25.0` 或 价格逼近日内低点；
  2. CVD 逆势走强：近 15m/30m 净 Delta 较前期低点收窄或翻正（`delta_divergence_bull == True` 或 `last_5m_delta > 0 且 net_delta_30m 比前期低点显著改善`）；
  3. 抛盘耗尽标志：主动市价卖单速率较前期低谷下降 50% 以上。
- **空头判定条件 (OF-5 Bearish)**：
  1. 价格处于高位极值区：`price_position_pct >= 75.0` 或 价格逼近日内高点；
  2. CVD 逆势走弱：近 15m/30m 净 Delta 较前期高点收窄或翻负（`delta_divergence_bear == True` 或 `last_5m_delta < 0 且 net_delta_30m 比前期高点显著走弱`）；
  3. 买盘耗尽标志：主动市价买单速率较前期高峰下降 50% 以上。

---

## 3. 模块二：5分钟周期平行判定通道架构实现

### 3.1 架构设计
- 在 `PyTools/order_flow_analysis/order_flow_pattern_evaluator.py`（新模块）中封装平行评测引擎：
  `evaluate_order_flow_pattern_channel(context_data) -> PatternChannelResult`
- 在 `order_flow_sentinel.py`（盘中实时）与 `recompute_order_flow_signals.py`（历史回算）中：
  - 维持原有 `evaluate_order_flow_tiered_scoring` 完整执行与返回值；
  - 并行调用 `evaluate_order_flow_pattern_channel`；
  - 汇总双通道输出结构，写入 `quantitative_metrics['parallel_pattern_channel']`。

### 3.2 双通道输出契约 (Output Contract)
```json
{
  "parallel_pattern_channel": {
    "version": "2026-09-20-v1",
    "channel_direction": "Bullish",
    "channel_score": 8.5,
    "hit_mechanisms": [
      {
        "id": "OF-1",
        "name": "被动吸收 (买盘承接)",
        "bias": "Bullish",
        "confidence": "High",
        "key_metrics": "delta_5m=-274, rth_low=7677.75, pos=0.0%, big_trade_ok"
      },
      {
        "id": "OF-4",
        "name": "双频共振 (多头共振)",
        "bias": "Bullish",
        "confidence": "Medium",
        "key_metrics": "stack_bid=54, stack_ask=38, delta_ratio=0.18"
      }
    ],
    "resonance_analysis": {
      "base_channel_direction": "Neutral",
      "pattern_channel_direction": "Bullish",
      "resonance_state": "EARLY_TURNING_SIGNAL",
      "summary": "传统基准通道受宏观趋势日压制保持中性防守，微观形态通道提前捕捉到底部被动吸收与多头共振，提示左侧结构性拐点。"
    }
  }
}
```

---

## 4. 模块三：UI 前端双通道可视化呈现设计

保持浅色主题（Light Theme），在两个核心入口深度集成：

### 4.1 BBT信号图 (ECharts Chart)
1. **控制栏组件**：
   - 增加独立过滤开关：`[✔] Order Flow 微观形态 (OF-1~5)`。
2. **图表绘制逻辑**：
   - 当检测到该 5 分钟柱命中了微观形态（`hit_mechanisms` 非空）：
     - 多头形态：在 K 线低点下方标注专属浅翠绿徽章标记（如 `[OF-1 吸收]`、`[OF-4 共振]`）；
     - 空头形态：在 K 线高点上方标注专属浅珊瑚红徽章标记（如 `[OF-1 拦截]`、`[OF-5 背离]`）；
     - 双通道共振：若基准通道与形态通道同时看多/看空，标记放大并带有金色光晕边框。
3. **Tooltip 增强呈现**：
   - 浮窗中新增「平行通道：微观结构形态」分区，详细展示命中的模式名称、置信度、量化证据与双通道共振结论。

### 4.2 Order Flow 实时信号列表与详情面板
1. **表格行呈现**：
   - 在 `Direction` 列右侧或 `Verdict` 开头增加紧凑微型徽标（如 `[OF-1]`, `[OF-4]`），鼠标悬浮展示简要描述。
2. **展开详情面板 (`detail-panel`)**：
   - 新增 **【微观结构形态平行研判通道 (Microstructure Pattern Channel)】** 专区：
     - **双通道对比卡片**：左侧「传统 5m 两步法通道」vs 右侧「微观形态通道」；
     - **共振状态徽章**：`双通道顺势共振 (CONVERGENT)` / `微观左侧反转 (EARLY TURNING)` / `多空分歧背离 (CONFLICT)`；
     - **五维机理矩阵表**：列表列出 OF-1 至 OF-5 的状态（未命中、多头触发、空头触发）、关键量化数值及判断依据。

---

## 5. 模块四：盘后自适应规则微调与演进机制 (After-hours Auto-Tuning)

### 5.1 运行模式
- 编写任务脚本 `PyTools/jobs/daily_order_flow_pattern_autotune.py`；
- 每天美西 13:30（收盘后）自动触发或手动运行。

### 5.2 调参逻辑与算法
1. **样本提取**：
   - 从 `of_deep_pattern_cases` 读取所有已完成正向收益验证的成功案例（`fwd_hit_15m == 1` 或 `fwd_hit_30m == 1`）；
2. **参数分布统计**：
   - 提取各成功案例触发时刻的核心特征分位数分布（如 `delta_thresholds`, `imbalance_mean`, `price_position_cutoffs`, `stack_ratios`）；
3. **安全自适应更新（带平滑阻尼）**：
   - 新参数 = 原参数 * (1 - 学习率) + 本期样本统计均值 * 学习率（学习率设为 0.15，确保参数平滑渐进，绝不发生剧烈漂移）；
   - 将更新后的参数写回 `PyTools/order_flow_analysis/order_flow_pattern_params.json`；
4. **审计与版本管理**：
   - 在 `order_flow_pattern_params.json` 中自动记录修改时间戳、更新样本数及新旧参数差值，确保完全可追溯。

---

## 6. 模块五：2026-09-18 09:25 核心测试与验证方案

### 6.1 目标测试场景
- **时间**：2026-09-18 09:25（美西时间）
- **标的**：ES
- **实盘背景**：
  - ES 在 09:25 探底当日最低点 7677.75；
  - 传统通道判定：`Neutral:Low-Boundary`（强度 0/10，受空头趋势日防护罩拦截，判定 HOLD）；
  - 实际后续走势：从 7677.75 强劲彻底反转推升至 7710 以上。

### 6.2 预期测试结果
1. **基准通道**：完全保持 `Neutral:Low-Boundary` 原样不变；
2. **平行通道**：
   - 成功捕获 **OF-1: 被动吸收 (多头承接)**（低位 0.0% 分位、主动抛压被限价挂单吸收、大单未砸穿）；
   - 成功捕获 **OF-4: 双频共振 (多头共振)**（买方挂单堆叠优势 54 vs 38、末端市价买单回升）；
   - 形态通道综合方向：`Bullish`；
   - 共振分析：准确给出 `EARLY_TURNING_SIGNAL`（左侧反转预警）。
3. **UI 渲染**：
   - 页面 09:25 行展开正确呈现双通道并列，图表上 09:25 位置显示形态徽标。

---

## 7. 规范与文档维护计划（符合规则 10 & 11）

1. **规则手册维护 (Rule 11)**：
   - 在 `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html`（及对应 `.md`）的「第一部分：订单流规则体系」中，新增 **§1.10 5分钟微观结构形态平行判定通道规范**，记录 OF-1 至 OF-5 的量化决策规则与双通道共振机制。
2. **模块索引维护 (Rule 10)**：
   - 在 `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/` 归档本实施计划及后续的验收报告；
   - 更新 `bbt_trading_modules.html`，新增本模块的条目、技术栈标记与直达超链接。

---

## 用户确认事项 (Review Required)

请确认以上设计方案是否符合您的预期。待您确认后，我将立即开始执行核心评测引擎、数据持久化、UI 展示及盘后调参的落地编码。
