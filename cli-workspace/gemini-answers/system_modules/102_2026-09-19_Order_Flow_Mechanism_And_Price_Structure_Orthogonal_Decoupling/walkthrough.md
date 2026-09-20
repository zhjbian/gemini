# Walkthrough - 订单流微观机制与价格走势结构二维正交解耦体系

在 Research & Pattern Analytics 平台（`http://127.0.0.1:5005/bbt_research_analytics`）及订单流深度分析引擎中，将原混杂走势形态的 P1–P5 模式体系全面重构为「二维正交解耦分析体系」，成功消除了走势形态与微观物理机制的混合混淆，建立了严格多空对称的纯物理微观机制层。

## 1. 核心架构重构内容

### 1.1 纯订单流微观机制层 (OF-1 至 OF-5)
- **OF-1: 被动吸收 (Passive Absorption - Bid/Ask 双向对称)**
  - 判定准则：折价/溢价区 + 限价单坚决承接/拦截 + 30m累积Delta异向积累翻转 + 主力大额未失控打穿。
  - 消除旧 P1 与 P3 的不对称混杂，统一抽象为被动限价单对市价单进攻的完全吸收。
- **OF-2: 由守转攻 / 态势切换 (Initiative Shift - Bid/Ask 双向对称)**
  - 判定准则：短窗买/卖脉冲爆发 (d5_max/min 显著且末段同向) + 主力市价大单明确由防守转为主动净买/净卖。
  - 捕捉被动防守向激进市价主攻的动量质变。
- **OF-3: 诱导洗盘 / 止损猎杀 (Liquidity Trap & Washout - Bull/Bear 双向对称)**
  - 判定准则：击穿关键极值点/扫除密集止损单 (washout_bull/bear 触发) + 瞬间伴随大额主力单反包收筹/出货。
  - 捕捉流动性陷阱，作为高盈亏比的反手交易依据。
- **OF-4: 盘口与成交双频共振 (Order Flow Confluence - Bull/Bear 双向对称)**
  - 判定准则：DOM 挂单失衡深度 (imb ±5) 与 TICK 逐笔主动流向 (Δ5m) 方向一致且与研判方向吻合。
  - 趋势动能最高可信度印证。
- **OF-5: 结构性 CVD 背离 (Structural CVD Divergence - 1~3 天与日内衰竭研判)**
  - 判定准则：价格探日内低位/高位或创新极值，但 30m 累积成交量增量 (Delta) 逆势反向或衰竭。
  - 替代原 5m vs 30m 易受日内随机噪声干扰的局部背离，专精于 1~3 天波段衰竭见顶/见底预警。

### 1.2 价格走势与拍卖结构层 (Price Action Structure)
- 基于全局日内全景走势客观量化：
  - `low_clean_reversal` (低位彻底反转)
  - `low_consolidation` (低位维持震荡)
  - `high_clean_reversal` (高位彻底反转)
  - `high_consolidation` (高位维持震荡)
  - `low_absorption` / `high_distribution`
- 每个案例均通过 `[走势结构] × [微观机制]` 双维度联合标定。

## 2. 代码实现清单

| 文件 | 变更性质 | 核心功能与改动 |
| :--- | :---: | :--- |
| `patterns.py` | 重构修改 | 引入 OF-1~OF-5 定义与判定函数 `match_patterns()`；内置 `LEGACY_ALIAS_MAP` 保障历史兼容 |
| `run_analysis.py` | 增强修改 | Section 0 顶栏增加【订单流微观机制】与【价格拍卖结构】双维度看板；渲染 5 张 OF-1~5 机制卡片 |
| `bbt_research_analytics.html` | 增强修改 | 增加 `ofDeepPatternBadges(c)` 支持同时渲染 OF 与 P 徽章标签及浮窗解释；更新说明文字 |
| `rules_manual.md` & `.html` | 文档规则 | 增加 Section 1.11 / 1.8 决策性规则，包含 5 大微观机制准则、纯文本计算公式与历史兼容对照表 |

## 3. 验证与测试结果

### 3.1 语法编译与执行测试
- `python3 -m py_compile patterns.py run_analysis.py` 编译通过，零错误。
- 重新运行案例 `python3 run_analysis.py --date 2026-09-18 --start 07:55 --end 09:55 --bias bullish --slug low_clean_reversal --log-case`：
  - 成功识别出：`patterns=OF-4+OF-5 confidence=medium`；
  - 报告文件成功写入 `order_flow_analysis_ES_2026-09-18_0955_low_clean_reversal_2026-09-19_1925.html`；
  - 数据库 `of_deep_pattern_cases` 成功落库为 `verdict: OF-4+OF-5`，JSON 包含 `OF-4`（双频共振）与 `OF-5`（CVD背离）。

### 3.2 Web 接口与看板验证
- `curl http://127.0.0.1:5005/data/order_flow_deep_analysis?limit=2` 正常返回：
  - `ES_2026-09-18_0955` 返回 `patterns: [OF-4, OF-5]` 及对应新报告文件名；
  - 历史案例 `ES_2026-09-18_0945` 的 `P4` 标签通过 `ofDeepPatternBadges` 依然正常解析显示为 `P4 双频共振`。
- Section 0 呈现 Light Theme 浅色风格，顶栏清晰显示：
  - `【订单流微观机制】: OF-4 · 双频共振 (多头共振) + OF-5 · CVD 背离 (多头背离)  MEDIUM`
  - `【价格拍卖结构】: 低位彻底反转 (Low Clean Reversal)`
  - OF-4 与 OF-5 卡片亮绿高亮命中，其余卡片显示未触发。
