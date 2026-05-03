# ES Big Trade Signal Statistics (Direct ES Measurement)

## Methodology
- **Source**: `order_flow_big_trade` table, `type = SingleTickBigTrade`, `off_price >= 0`
- **Ticker**: ES (Direct measurement)
- **Period Classification**: Uses DB `trading_hour` field (PM/RTH/AH). FirstHour = RTH trades between 6:30-7:30 AM PT.
- **ES Base Price**: Execution price of the biggest volume trade in the signal direction (PM/FirstHour), or individual trade price (RTH/AH).
- **ES Max Profit Price**: Highest High (buy) or lowest Low (sell) of ES daily candle during the next 3 trading days, including the signal day.
- **Success Criteria**: ES price moves ≥ 0.75% in the signal direction within 3 trading days.
- **Backtest Period**: 12 months (Apr 2025 – Apr 2026)
- **Weak Signal Filter**: Discards PM/FirstHour signals if counter-volume ≥ 25% of total gross volume.
- **Extreme Chase Filter**: Excludes signals buying within 10pts of 12h high or selling within 10pts of 12h low from global stats.
- **Total Signals (Qualified)**: 600
- **Total Signals (Excluded Chase)**: 170

## Signal Aggregation Rules
| Period | Aggregation | Notes |
|---|---|---|
| PM | Combined net volume per day | Baseline: Exec price of the biggest direction trade |
| FirstHour | Combined net volume per day | Baseline: Exec price of the biggest direction trade |
| RTH | Individual trades | Each trade is its own signal/baseline |
| AH | Individual trades | Each trade is its own signal/baseline |

## Hit Rate by Period and Volume Bucket (Direct ES measurement)

| Period | ES Volume | Count | Hit Rate | Same Day Hit | Avg Max Win % | Hours to hit |
|---|---|---|---|---|---|---|
| **AH** | <500 | 73 | 64.38% | 21.92% | 1.19% | 31(1) |
| **AH** | 500-1000 | 36 | 69.44% | 8.33% | 1.25% | 39(1) |
| **AH** | 1000-2000 | 15 | 46.67% | 13.33% | 1.16% | 29(1) |
| **AH** | >2000 | 13 | 53.85% | 0.0% | 1.09% | 38(1) |
| **FirstHour** | <500 | 15 | 60.0% | 40.0% | 1.36% | 16(0) |
| **FirstHour** | 500-1000 | 10 | 70.0% | 0.0% | 0.95% | 56(2) |
| **FirstHour** | 1000-2000 | 11 | 63.64% | 36.36% | 1.15% | 24(1) |
| **FirstHour** | >2000 | 8 | 62.5% | 50.0% | 1.11% | 15(0) |
| **PM** | <500 | 16 | 56.25% | 18.75% | 1.13% | 32(1) |
| **PM** | 500-1000 | 3 | 100.0% | 66.67% | 2.11% | 34(1) |
| **PM** | 1000-2000 | 5 | 80.0% | 0.0% | 1.01% | 47(1) |
| **PM** | >2000 | 6 | 83.33% | 66.67% | 1.85% | 16(0) |
| **RTH** | <500 | 268 | 64.18% | 22.39% | 1.28% | 35(1) |
| **RTH** | 500-1000 | 111 | 62.16% | 18.02% | 1.0% | 44(1) |
| **RTH** | 1000-2000 | 10 | 40.0% | 0.0% | 0.59% | 77(3) |

## Key Findings

### Tier 1 Signals (≥70% Hit Rate)
1. **PM 500-1000 ES**: 100.00% hit rate (3 signals).
1. **PM >2000 ES**: 83.33% hit rate (6 signals).
1. **PM 1000-2000 ES**: 80.00% hit rate (5 signals).
1. **FirstHour 500-1000 ES**: 70.00% hit rate (10 signals).

### Tier 2 Signals (60-69% Hit Rate)
1. **AH 500-1000 ES**: 69.44% hit rate (36 signals).
1. **AH <500 ES**: 64.38% hit rate (73 signals).
1. **RTH <500 ES**: 64.18% hit rate (268 signals).
1. **FirstHour 1000-2000 ES**: 63.64% hit rate (11 signals).
1. **FirstHour >2000 ES**: 62.50% hit rate (8 signals).
1. **RTH 500-1000 ES**: 62.16% hit rate (111 signals).
1. **FirstHour <500 ES**: 60.00% hit rate (15 signals).

### Noise / Discard (<60% Hit Rate)
1. **RTH 1000-2000 ES**: 40.00% hit rate (10 signals).
1. **AH 1000-2000 ES**: 46.67% hit rate (15 signals).
1. **AH >2000 ES**: 53.85% hit rate (13 signals).
1. **PM <500 ES**: 56.25% hit rate (16 signals).

## Recommended Classification Thresholds (Direct ES measurement)

### Tier 1: High Conviction (High conviction direction)
- **FirstHour** with total ES volume ≥ 500
- **PM** with total ES volume > 1000

### Tier 2: Elevated Conviction (Supplementary signal)
- **RTH** with ES volume < 1000
- **AH** with ES volume < 1000
- **PM** with total ES volume ≤ 1000
- **FirstHour** with total ES volume < 500

### Discard / Noise (Low statistical edge)
- **RTH** with ES volume ≥ 1000
- **AH** with ES volume ≥ 1000
- Any signal failing the **Weak Signal Filter** (Counter-trade ratio ≥ 25%)

---
*Generated: 2026-04-15. ES-only backtest using direct measurement. Window: 2025-04-15 to 2026-04-15.*