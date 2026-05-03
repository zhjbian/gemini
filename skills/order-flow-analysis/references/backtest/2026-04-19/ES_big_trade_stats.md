# ES Big Trade Signal Statistics (Direct ES Measurement)

## Methodology
- **Source**: `order_flow_big_trade` table, `type = SingleTickBigTrade`, `off_price >= 0`
- **Ticker**: ES (Direct measurement)
- **Period Classification**: Uses DB `trading_hour` field (PM/RTH/AH). FirstHour = RTH trades between 6:30-7:30 AM PT.
- **ES Base Price**: Execution price of the biggest volume trade in the signal direction (PM/FirstHour), or individual trade price (RTH/AH).
- **ES Max Profit Price**: Highest High (buy) or lowest Low (sell) of ES daily candle during the next 3 trading days, including the signal day.
- **Success Criteria**: ES price moves ≥ 0.75% in the signal direction within 3 trading days.
- **Backtest Period**: 10 days (Apr 2026 – Apr 2026)
- **Weak Signal Filter**: Discards PM/FirstHour signals if counter-volume ≥ 25% of total gross volume.
- **Extreme Chase Filter**: Excludes signals buying within 10pts of 12h high or selling within 10pts of 12h low from global stats.
- **Total Signals (Qualified)**: 24
- **Total Signals (Excluded Chase)**: 6

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
| **AH** | <500 | 2 | 50.0% | 0.0% | 0.69% | 74(3) |
| **AH** | 500-1000 | 1 | 100.0% | 0.0% | 1.32% | 74(3) |
| **FirstHour** | 1000-2000 | 1 | 100.0% | 100.0% | 0.78% | 2(0) |
| **PM** | >2000 | 2 | 100.0% | 100.0% | 2.38% | 2(0) |
| **RTH** | <500 | 12 | 41.67% | 0.0% | 0.9% | 57(2) |
| **RTH** | 500-1000 | 5 | 80.0% | 0.0% | 0.95% | 77(3) |
| **RTH** | 1000-2000 | 1 | 0.0% | 0.0% | 0.21% | - |

## Key Findings

### Tier 1 Signals (≥70% Hit Rate)
1. **AH 500-1000 ES**: 100.00% hit rate (1 signals).
1. **FirstHour 1000-2000 ES**: 100.00% hit rate (1 signals).
1. **PM >2000 ES**: 100.00% hit rate (2 signals).
1. **RTH 500-1000 ES**: 80.00% hit rate (5 signals).

### Tier 2 Signals (60-69% Hit Rate)
None identified in this backtest period.

### Noise / Discard (<60% Hit Rate)
1. **RTH 1000-2000 ES**: 0.00% hit rate (1 signals).
1. **RTH <500 ES**: 41.67% hit rate (12 signals).
1. **AH <500 ES**: 50.00% hit rate (2 signals).

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
*Generated: 2026-04-19. ES-only backtest using direct measurement. Window: 2026-04-09 to 2026-04-19.*