# Gemini Answer - order_flow_signal_strength_rules

## Question
replacing the price distance from high/low constraints with a metric based on the RTH Cumulative Delta percentage of RTH Volume (Delta%Vol). is this all the rule or there are other rules, this is one of them


## Answer
并不是全部规则。$\text{Delta\%Vol}$ 占比是一个**全局预筛选过滤条件（Pre-condition）**，用于在第一步区分当前处于“趋势的前期（翻转区）”还是“趋势的中后期（延续区）”。

在满足该预筛选条件后，信号还必须满足以下**微观订单流验证规则**中的**至少一项**，才会被判定为 `High` 强度：

---

### Bearish (看空) 判定为 `High` 的完整条件
1. **全局预筛选（RTH 累计 Delta 占比）**：
   * $\text{Delta\%Vol} \ge 1.5\%$ （表明市场先前呈强势买入状态，正处于顶部或刚开始回落的翻转区）。
2. **且满足以下微观验证规则之一**：
   * **条件 A (放量主动砸盘)**：最近 15 分钟累计 Delta $\le -8,000$ 手，或任意单根 5 分钟微观 Delta $\le -6,000$ 手。
   * **条件 B (高效下挫与吸收)**：单根 5 分钟价格下跌 $\le -10.0$ 点，**且**伴随负 Delta，或伴随 passive 卖方吸收（研判结论中包含“买盘被吸收”、“Supply Trap”或“买盘竭尽”）。
   * **条件 C (累积背离回撤)**：RTH 累计 Delta 从当日最高点回撤 $\ge 10,000$ 手，或最近 30 分钟累计 Delta $\le -5,000$ 手。
   * **条件 D (持续下行斜率)**：最近 30 分钟价格下跌 $\le -15.0$ 点，且最近 30 分钟 Delta 为负值。

---

### Bullish (看多) 判定为 `High` 的完整条件
1. **全局预筛选（RTH 累计 Delta 占比）**：
   * $\text{Delta\%Vol} \le 1.5\%$ （表明市场先前正处于下跌通道中或已深度调整，Delta 已充分衰竭，处于底部筑底或反弹启动区）。
2. **且满足以下微观验证规则之一**：
   * **条件 A (放量主动拉升)**：最近 15 分钟累计 Delta $\ge 8,000$ 手，或任意单根 5 分钟微观 Delta $\ge 6,000$ 手。
   * **条件 B (高效拉升与吸收)**：单根 5 分钟价格上涨 $\ge 10.0$ 点，**且**伴随正 Delta，或伴随 passive 买方吸收（研判结论中包含“卖盘被吸收”、“Demand Trap”或“卖盘竭尽”）。
   * **条件 C (累积底背离反弹)**：RTH 累计 Delta 从当日最低点反弹上升 $\ge 10,000$ 手，或最近 30 分钟累计 Delta $\ge 5,000$ 手。
   * **条件 D (持续上行斜率)**：最近 30 分钟价格上涨 $\ge 15.0$ 点，且最近 30 分钟 Delta 为正值。

