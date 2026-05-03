# NVDA Big Trade Signal Statistics (Direct Measurement)

## Methodology
- **Source**: `order_flow_big_trade` table, `type in (SingleTickBigTrade, SingleTickDarkTrade, AggregateBigTrade)`, `off_price >= 0`
- **Ticker**: NVDA (Direct measurement)
- **Period Classification**: Uses DB `trading_hour` field (PM/RTH/AH). FirstHour = RTH trades between 6:30-7:30 AM PT.
- **NVDA Base Price**: Execution price of the biggest volume trade in the signal direction (PM/FirstHour), or individual trade price (RTH/AH).
- **Success Criteria**: NVDA price moves ≥ 0.75% in the signal direction within 20 trading days.
- **Late Hit**: Target reached between day 21 and 60 (exclusive of Target Hit).
- **Backtest Period**: 12 months (Apr 2025 – Apr 2026)
- **Total Signals**: 3249

## Signal Aggregation Rules
| Period | Aggregation | Notes |
|---|---|---|
| PM | Combined net volume per day | Baseline: Exec price of the biggest direction trade |
| FirstHour | Combined net volume per day | Baseline: Exec price of the biggest direction trade |
| RTH | Individual trades | Each trade is its own signal/baseline |
| AH | Individual trades | Each trade is its own signal/baseline |

## Hit Rate by Period and Volume Bucket (Direct NVDA measurement)

| Period | NVDA Volume | Count | Overrides | 5% Target Hit (20d) | Avg Days | Late Hit (21-60d) | Avg Days | Max Profit (40d) | Avg Days Max | Drawdown (Pre-Target) | Drawdown (Pre-Late) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **PM** | <100k | 15 | 12 | 100.0% | 1.1 | 0.0% |  | 9.52% | 15.7 | -0.85% |  |
| **PM** | 100k-500k | 11 | 9 | 100.0% | 3.3 | 0.0% |  | 6.65% | 12.5 | -1.22% |  |
| **PM** | 500k-1M | 8 | 6 | 100.0% | 1.1 | 0.0% |  | 12.69% | 9.6 | 0.67% |  |
| **PM** | >1M | 2 | 0 | 100.0% | 2.0 | 0.0% |  | 6.11% | 2.0 | -2.24% |  |
| **FirstHour** | <100k | 10 | 6 | 100.0% | 1.3 | 0.0% |  | 9.27% | 15.8 | -0.6% |  |
| **FirstHour** | 100k-500k | 58 | 41 | 96.55% | 2.0 | 0.0% |  | 10.04% | 21.3 | -0.86% |  |
| **FirstHour** | 500k-1M | 22 | 14 | 100.0% | 1.7 | 0.0% |  | 9.11% | 21.1 | -1.03% |  |
| **FirstHour** | >1M | 19 | 9 | 100.0% | 2.1 | 0.0% |  | 8.76% | 18.9 | -1.83% |  |
| **RTH** | <100k | 690 | 415 | 99.28% | 2.6 | 0.29% | 33.0 | 9.37% | 21.6 | -1.68% | -10.15% |
| **RTH** | 100k-500k | 567 | 307 | 96.47% | 2.3 | 1.23% | 29.6 | 9.91% | 21.6 | -1.38% | -10.48% |
| **RTH** | 500k-1M | 250 | 122 | 95.6% | 2.2 | 1.6% | 26.0 | 11.41% | 21.9 | -1.22% | -8.67% |
| **RTH** | >1M | 124 | 64 | 98.39% | 2.5 | 0.0% |  | 11.31% | 23.0 | -1.64% |  |
| **AH** | <100k | 359 | 211 | 100.0% | 1.7 | 0.0% |  | 9.94% | 19.0 | -0.77% |  |
| **AH** | 100k-500k | 641 | 382 | 99.22% | 1.8 | 0.0% |  | 11.04% | 19.6 | -0.84% |  |
| **AH** | 500k-1M | 257 | 121 | 98.05% | 1.7 | 0.0% |  | 11.89% | 21.8 | -0.83% |  |
| **AH** | >1M | 216 | 115 | 97.69% | 1.7 | 0.0% |  | 11.16% | 19.4 | -0.92% |  |

## Key Findings

### Maturation Insights
1. **Trend Continuance**: Buckets with high 'Late Hit' rates suggest signals that require longer institutional maturation cycles.
2. **Risk Management**: 'Drawdown Pre-Target' provides the historical baseline for institutional 'chase' risk.

---
*Generated: 2026-04-26. NVDA-only backtest using direct measurement. Window: 2025-04-26 to 2026-04-26.*