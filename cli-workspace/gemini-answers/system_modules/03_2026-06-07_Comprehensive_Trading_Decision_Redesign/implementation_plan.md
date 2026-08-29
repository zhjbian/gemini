# Redesign of Comprehensive Trading Decision (综合交易决策)

This implementation plan outlines the redesign of the comprehensive trading decision engine to support both robust, multi-factor rule-based grading and advanced AI-based synthesis logic. The system integrates three key inputs:
1. **SPX Gamma Option Structure (SPX Gamma方向判断)**
2. **Institutional Big Trades Flow (Order Flow大单方向判断)**
3. **Order Flow Real-time Tape Dynamic (Order Flow实时盘面判断)**

## Possible Outcomes & Styling

We define the 7 comprehensive trading decisions, their representation, colors, and icons:

1. **开仓做多** (Open Long)
   - **Color**: Green (`#10b981`, background `rgba(16, 185, 129, 0.1)`)
   - **Icon**: `<i class="fas fa-arrow-circle-up"></i>`
2. **持有多头仓位** (Hold Long)
   - **Color**: Green (`#10b981`, background `rgba(16, 185, 129, 0.1)`)
   - **Icon**: `<i class="fas fa-chevron-circle-up"></i>`
3. **卖出多头仓位** (Sell Long)
   - **Color**: Orange (`#f59e0b`, background `rgba(245, 158, 11, 0.1)`)
   - **Icon**: `<i class="fas fa-times-circle"></i>`
4. **开仓做空** (Open Short)
   - **Color**: Red (`#ef4444`, background `rgba(239, 68, 68, 0.1)`)
   - **Icon**: `<i class="fas fa-arrow-circle-down"></i>`
5. **持有空头仓位** (Hold Short)
   - **Color**: Red (`#ef4444`, background `rgba(239, 68, 68, 0.1)`)
   - **Icon**: `<i class="fas fa-chevron-circle-down"></i>`
6. **卖出空头仓位** (Sell Short)
   - **Color**: Orange (`#f59e0b`, background `rgba(245, 158, 11, 0.1)`)
   - **Icon**: `<i class="fas fa-times-circle"></i>`
7. **避免开仓交易** (Avoid Trading / Stand Aside)
   - **Color**: Gray (`#64748b`, background `rgba(100, 116, 139, 0.1)`)
   - **Icon**: `<i class="fas fa-hand-paper"></i>` (Avoid sign / Hand symbol)

---

## Decision Mapping Matrix (Rule-Based)

Let the scores of SPX Gamma, Big Trades, and Real-time Tape be $s_{spx}, s_{bt}, s_{sig} \in \{-1, 0, 1\}$.

| $(s_{spx}, s_{bt}, s_{sig})$ | Resulting Decision | Classification / Logic Context |
| :--- | :--- | :--- |
| `(1, 1, 1)` | **开仓做多** | 多头强共振：期权支撑 + 大单流入 + 盘口多头爆发 |
| `(1, 1, 0)` | **持有多头仓位** | 多头占优：期权与大单支撑，盘口偏中性 |
| `(1, 0, 1)` | **开仓做多** | 多头共振：期权支撑 + 盘口主动买盘 |
| `(0, 1, 1)` | **开仓做多** | 多头共振：大单买入 + 盘口主动买盘 |
| `(1, 0, 0)` | **持有多头仓位** | 期权撑盘，无主动大单或盘口买盘配合 |
| `(0, 1, 0)` | **持有多头仓位** | 大单吸筹，期权与盘口呈中性 |
| `(0, 0, 1)` | **避免开仓交易** | 仅盘口短期买盘脉冲，不宜盲目新开仓做多 |
| `(1, 1, -1)` | **卖出多头仓位** | 期权与大单支撑，但盘口突现主动抛压，提示多头平仓 |
| `(1, -1, 1)` | **卖出多头仓位** | 期权与盘口买入，但大单机构出货，提示多头平仓 |
| `(-1, 1, 1)` | **避免开仓交易** | 期权结构压制，但大单与盘口强劲，多空对抗，暂不开仓 |
| `(-1, -1, -1)`| **开仓做空** | 空头强共振：期权压制 + 大单流出 + 盘口空头爆发 |
| `(-1, -1, 0)`| **持有空头仓位** | 空头占优：期权与大单压制，盘口偏中性 |
| `(-1, 0, -1)`| **开仓做空** | 空头共振：期权压制 + 盘口主动卖盘 |
| `(0, -1, -1)`| **开仓做空** | 空头共振：大单流出 + 盘口主动卖盘 |
| `(-1, 0, 0)` | **持有空头仓位** | 期权压制，无主动大单或盘口卖盘配合 |
| `(0, -1, 0)` | **持有空头仓位** | 大单流出，期权与盘口呈中性 |
| `(0, 0, -1)` | **避免开仓交易** | 仅盘口短期卖盘脉冲，不宜盲目新开仓做空 |
| `(-1, -1, 1)`| **卖出空头仓位** | 期权与大单压制，但盘口出现主动抄底，提示空头平仓 |
| `(-1, 1, -1)`| **卖出空头仓位** | 期权与盘口卖出，但大单机构建仓，提示空头平仓 |
| `(1, -1, -1)` | **避免开仓交易** | 期权结构支撑，但大单与盘口强劲，多空对抗，暂不开仓 |
| `(0, 0, 0)` | **避免开仓交易** | 多空绝对平衡：三方信号均偏中性 |
| `(1, -1, 0)` | **避免开仓交易** | 资金分歧：期权支撑但大单流出 |
| `(-1, 1, 0)` | **避免开仓交易** | 资金分歧：期权压制但大单流入 |
| `(1, 0, -1)` | **卖出多头仓位** | 期权支撑但盘口主动砸盘，多单提示平仓/避险 |
| `(-1, 0, 1)` | **卖出空头仓位** | 期权压制但盘口主动拉升，空单提示平仓/避险 |
| `(0, 1, -1)` | **卖出多头仓位** | 大单流入但盘口主动砸盘，多单提示平仓/避险 |
| `(0, -1, 1)` | **卖出空头仓位** | 大单流出但盘口主动拉升，空单提示平仓/避险 |

## AI-Based Synthesis Engine

Gemini will be instructed to evaluate the exact inputs and choose from the same 7 structured decisions.
- **Output Format**:
  `综合决策: [开仓做多/持有多头仓位/卖出多头仓位/开仓做空/持有空头仓位/卖出空头仓位/避免开仓交易] ([具体类型])`
  `核心逻辑: [核心分析, <= 150字]`

## Proposed Changes

### Backend Components

#### [MODIFY] [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py)
- Refactor `get_comprehensive_direction_decision()` route.
- Implement the 27-case score mapping matrix using `score_dir()` logic.
- Update AI prompt template and parsing regex pattern.

### Frontend Components

#### [MODIFY] [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js)
- Update `getOFDirectionBadgeHtml()` function to match the 7 comprehensive trading decisions and styles (Green, Red, Orange, Gray) and display custom icons.

## Verification Plan

### Manual Verification
- Test all backtest timepoints to confirm they match correct case logic.
- Verify status colors and icons render perfectly on the page.

