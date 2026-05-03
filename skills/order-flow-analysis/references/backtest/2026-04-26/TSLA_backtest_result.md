# TSLA Big Trade Signal Statistics (Direct Measurement)

## Methodology
- **Source**: `order_flow_big_trade` table, `type in (SingleTickBigTrade, SingleTickDarkTrade, AggregateBigTrade)`, `off_price >= 0`
- **Ticker**: TSLA (Direct measurement)
- **Period Classification**: Uses DB `trading_hour` field (PM/RTH/AH). FirstHour = RTH trades between 6:30-7:30 AM PT.
- **TSLA Base Price**: Execution price of the biggest volume trade in the signal direction (PM/FirstHour), or individual trade price (RTH/AH).
- **Success Criteria**: TSLA price moves ≥ 5.00% in the signal direction within 20 trading days.
- **Late Hit**: Target reached between day 21 and 60 (exclusive of Target Hit).
- **Backtest Period**: 12 months (Apr 2025 – Apr 2026)
- **Total Signals**: 280

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
| **PM** | 500k-1M | 3 | 1 | 66.67% | 4.0 | 33.33% | 42.0 | 13.01% | 21.7 | -4.17% | -12.44% |
| **PM** | >1M | 4 | 1 | 25.0% | 1.0 | 25.0% | 41.0 | 6.4% | 18.5 | -2.46% | -13.73% |
| **FirstHour** | 100k-500k | 4 | 3 | 100.0% | 5.5 | 0.0% |  | 12.89% | 21.5 | -3.02% |  |
| **FirstHour** | 500k-1M | 4 | 1 | 100.0% | 9.0 | 0.0% |  | 13.12% | 21.0 | -4.26% |  |
| **FirstHour** | >1M | 1 | 1 | 100.0% | 3.0 | 0.0% |  | 14.84% | 24.0 | -0.71% |  |
| **RTH** | 100k-500k | 58 | 26 | 77.59% | 5.6 | 6.9% | 40.8 | 14.55% | 19.5 | -2.39% | -12.06% |
| **RTH** | 500k-1M | 71 | 39 | 73.24% | 5.4 | 9.86% | 35.4 | 16.25% | 21.6 | -2.49% | -12.8% |
| **RTH** | >1M | 11 | 2 | 54.55% | 2.8 | 0.0% |  | 13.41% | 13.2 | -0.92% |  |
| **AH** | 100k-500k | 44 | 23 | 65.91% | 4.4 | 18.18% | 30.8 | 11.98% | 21.2 | -2.08% | -10.46% |
| **AH** | 500k-1M | 54 | 34 | 70.37% | 6.1 | 7.41% | 37.2 | 12.74% | 20.9 | -2.75% | -13.05% |
| **AH** | >1M | 25 | 20 | 56.0% | 5.6 | 36.0% | 32.7 | 11.34% | 21.6 | -3.44% | -11.41% |

## Key Findings

### Maturation Insights
1. **Trend Continuance**: Buckets with high 'Late Hit' rates suggest signals that require longer institutional maturation cycles.
2. **Risk Management**: 'Drawdown Pre-Target' provides the historical baseline for institutional 'chase' risk.

---
*Generated: 2026-04-26. TSLA-only backtest using direct measurement. Window: 2025-04-26 to 2026-04-26.*