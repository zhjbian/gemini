# Implementation Plan - 订单流微观机制与价格走势结构二维正交解耦体系

在 Research & Pattern Analytics 平台（`http://127.0.0.1:5005/bbt_research_analytics`）及订单流深度分析引擎中，将原混杂的 P1–P5 形态体系彻底重构并解耦为「二维正交架构」：
1. **第一维度：纯订单流微观机制层 (Pure Order Flow Mechanics: OF-1 至 OF-5)**，纯粹由挂单簿与逐笔成交物理属性裁决，多空完全对立对称；
2. **第二维度：价格走势与拍卖结构层 (Price Action & Auction Structure: PA Structure)**，基于全局走势与价值区区间客观裁决。
每个盘面案例均形式化表示为：`[PA Structure 价格走势结构] × [OF Mechanics 纯订单流微观机理]`。

## User Review Required

> [!NOTE]
> 本次重构保持 100% 向后兼容性：
> 1. 保留 `P1`–`P5` 作为历史别名映射，已有案例（如 `ES_2026-09-18_0955`）平滑过渡；
> 2. 全面维持纯文本数学公式（无 LaTeX）与 Light Theme 浅色主题。

## Proposed Changes

### 1. 微观机制模式识别与双向对称定义

#### [MODIFY] [patterns.py](file:///Users/zhijiebian/.agents/skills/order-flow-deep-analysis/scripts/patterns.py)
- 定义 `OF-1` 至 `OF-5` 纯订单流微观机制：
  - `OF-1`: 被动吸收 (Passive Absorption - Bid/Ask 双向对称)
  - `OF-2`: 由守转攻 / 态势切换 (Initiative Shift - Bid/Ask 双向对称)
  - `OF-3`: 诱导洗盘 / 止损猎杀 (Liquidity Trap & Washout - Bull/Bear 双向对称)
  - `OF-4`: 盘口与成交双频共振 (Order Flow Confluence - Bull/Bear 双向对称)
  - `OF-5`: 结构性 CVD 背离 (Structural CVD Divergence - 1~3 天与日内衰竭研判)
- 建立 `LEGACY_ALIAS_MAP`（`P1->OF-1`, `P2->OF-3`, `P3->OF-1`, `P4->OF-4`, `P5->OF-5`）。
- 升级 `match_patterns(ev, th)`，返回规范化微观机制列表。

### 2. 深度研报生成 Section 0 渲染升级

#### [MODIFY] [run_analysis.py](file:///Users/zhijiebian/.agents/skills/order-flow-deep-analysis/scripts/run_analysis.py)
- 更新 `_render_pattern_section`：
  - 顶栏双维度看板展示：`【订单流微观机制】` 与 `【价格拍卖结构】`；
  - 渲染 5 张独立的 OF-1 至 OF-5 微观机制机检卡片，精准高亮命中状态。
- 更新报告 Section 3 下的 `patterns_block` 说明与置信度标签。

### 3. Web 研报展示与看板表格优化

#### [MODIFY] [bbt_research_analytics.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_research_analytics.html)
- 增加 `ofDeepPatternBadges(c)` 渲染函数，为 `OF-1` 至 `OF-5` 及旧版 `P1`–`P5` 渲染带有中英文说明与颜色状态的精美徽章。
- 更新表格模式列与报告说明脚注。

### 4. 交易系统规则手册归档

#### [MODIFY] [gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md)
#### [MODIFY] [gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html)
- 新增 Section 1.11 / 1.8 决策性规则，包含五大机制详细准则、纯文本计算公式与交易决策指导，同步更新目录导航。

## Verification Plan

### Automated Tests
- 编译检查 `patterns.py` 与 `run_analysis.py`：`python3 -m py_compile ...`
- 重新运行案例 `python3 run_analysis.py --date 2026-09-18 --start 07:55 --end 09:55 --bias bullish --slug low_clean_reversal --log-case`
- 检查数据库落库记录与 JSON 返回。

### Manual Verification
- 访问 `http://127.0.0.1:5005/bbt_research_analytics` 模块二，展开 2026-09-18 案例，确认 Section 0 呈现清晰的双维度结构（价格走势结构 + OF-4/OF-5 微观机制）。
