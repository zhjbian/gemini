# TSLA Big Trade Signal Statistics (Direct Measurement)

## Methodology
- **Source**: `order_flow_big_trade` table, `type in (SingleTickBigTrade, SingleTickDarkTrade, AggregateBigTrade)`, `off_price >= 0`
- **Ticker**: TSLA (Direct measurement)
- **Period Classification**: Uses DB `trading_hour` field (PM/RTH/AH). FirstHour = RTH trades between 6:30-7:30 AM PT.
- **TSLA Base Price**: Execution price of the biggest volume trade in the signal direction (PM/FirstHour), or individual trade price (RTH/AH).
- **Success Criteria**: TSLA price moves ≥ 5.00% in the signal direction within 20 trading days.
- **Late Hit**: Target reached between day 21 and 60 (exclusive of Target Hit).
- **Backtest Period**: 12 months (Apr 2025 – Apr 2026)
- **Total Signals**: 274

## Signal Aggregation Rules
| Period | Aggregation | Notes |
|---|---|---|
| PM | Combined net volume per day | Baseline: Exec price of the biggest direction trade |
| FirstHour | Combined net volume per day | Baseline: Exec price of the biggest direction trade |
| RTH | Individual trades | Each trade is its own signal/baseline |
| AH | Individual trades | Each trade is its own signal/baseline |

## Hit Rate by Period and Volume Bucket (Direct TSLA measurement)

| Period | TSLA Volume | Count | Overrides | 5% Target Hit (20d) | Avg Days | Late Hit (21-60d) | Avg Days | Max Profit (40d) | Avg Days Max | Drawdown (Pre-Target) | Drawdown (Pre-Late) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **PM** | 100k-500k | 1 | 1 | 0.0% |  | 0.0% |  | 4.47% | 1.0 |  |  |
| **PM** | 500k-1M | 3 | 2 | 66.67% | 2.5 | 33.33% | 42.0 | 13.0% | 14.3 | 0.14% | -12.44% |
| **PM** | >1M | 4 | 1 | 25.0% | 1.0 | 25.0% | 41.0 | 6.4% | 18.5 | -2.46% | -13.73% |
| **FirstHour** | 100k-500k | 4 | 3 | 100.0% | 5.5 | 0.0% |  | 12.89% | 21.5 | -3.02% |  |
| **FirstHour** | 500k-1M | 4 | 0 | 75.0% | 6.3 | 0.0% |  | 8.49% | 12.8 | -2.18% |  |
| **FirstHour** | >1M | 1 | 1 | 100.0% | 3.0 | 0.0% |  | 14.84% | 24.0 | -0.71% |  |
| **RTH** | 100k-500k | 57 | 25 | 71.93% | 6.7 | 8.77% | 37.6 | 15.01% | 21.2 | -2.92% | -12.45% |
| **RTH** | 500k-1M | 69 | 40 | 56.52% | 5.5 | 10.14% | 37.9 | 10.81% | 16.4 | -3.08% | -13.49% |
| **RTH** | >1M | 9 | 2 | 66.67% | 2.8 | 0.0% |  | 16.4% | 15.9 | -0.92% |  |
| **AH** | 100k-500k | 44 | 23 | 65.91% | 4.4 | 18.18% | 30.8 | 11.98% | 21.2 | -2.08% | -10.46% |
| **AH** | 500k-1M | 53 | 34 | 64.15% | 6.2 | 7.55% | 37.2 | 12.24% | 20.0 | -2.66% | -13.05% |
| **AH** | >1M | 25 | 18 | 48.0% | 7.2 | 40.0% | 33.8 | 10.31% | 22.2 | -4.83% | -11.86% |

## Key Findings

### Maturation Insights
1. **Trend Continuance**: Buckets with high 'Late Hit' rates suggest signals that require longer institutional maturation cycles.
2. **Risk Management**: 'Drawdown Pre-Target' provides the historical baseline for institutional 'chase' risk.

---
*Generated: 2026-04-19. TSLA-only backtest using direct measurement. Window: 2025-04-19 to 2026-04-19.*