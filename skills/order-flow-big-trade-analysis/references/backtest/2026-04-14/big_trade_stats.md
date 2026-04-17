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
- **Total Signals Evaluated**: 770

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
| **AH** | <500 | 100 | 63.0% | 22.0% | 1.1% | 35(1) |
| **AH** | 500-1000 | 42 | 66.67% | 7.14% | 1.21% | 39(1) |
| **AH** | 1000-2000 | 15 | 46.67% | 13.33% | 1.16% | 29(1) |
| **AH** | >2000 | 14 | 50.0% | 0.0% | 1.04% | 38(1) |
| **FirstHour** | <500 | 20 | 55.0% | 35.0% | 1.22% | 22(0) |
| **FirstHour** | 500-1000 | 13 | 69.23% | 7.69% | 0.91% | 48(2) |
| **FirstHour** | 1000-2000 | 18 | 61.11% | 33.33% | 1.15% | 25(1) |
| **FirstHour** | >2000 | 10 | 70.0% | 60.0% | 1.35% | 11(0) |
| **PM** | <500 | 24 | 62.5% | 25.0% | 1.11% | 32(1) |
| **PM** | 500-1000 | 7 | 57.14% | 28.57% | 1.4% | 40(1) |
| **PM** | 1000-2000 | 7 | 71.43% | 0.0% | 0.93% | 41(1) |
| **PM** | >2000 | 7 | 71.43% | 57.14% | 1.51% | 16(0) |
| **RTH** | <500 | 338 | 61.54% | 22.19% | 1.22% | 34(1) |
| **RTH** | 500-1000 | 143 | 62.24% | 16.78% | 1.0% | 42(1) |
| **RTH** | 1000-2000 | 12 | 41.67% | 0.0% | 0.65% | 66(2) |

## Key Findings

### Tier 1 Signals (≥70% Hit Rate)
1. **PM 1000-2000 ES**: 71.43% hit rate (7 signals).
1. **PM >2000 ES**: 71.43% hit rate (7 signals).
1. **FirstHour >2000 ES**: 70.00% hit rate (10 signals).

### Tier 2 Signals (60-69% Hit Rate)
1. **FirstHour 500-1000 ES**: 69.23% hit rate (13 signals).
1. **AH 500-1000 ES**: 66.67% hit rate (42 signals).
1. **AH <500 ES**: 63.00% hit rate (100 signals).
1. **PM <500 ES**: 62.50% hit rate (24 signals).
1. **RTH 500-1000 ES**: 62.24% hit rate (143 signals).
1. **RTH <500 ES**: 61.54% hit rate (338 signals).
1. **FirstHour 1000-2000 ES**: 61.11% hit rate (18 signals).

### Noise / Discard (<60% Hit Rate)
1. **RTH 1000-2000 ES**: 41.67% hit rate (12 signals).
1. **AH 1000-2000 ES**: 46.67% hit rate (15 signals).
1. **AH >2000 ES**: 50.00% hit rate (14 signals).
1. **FirstHour <500 ES**: 55.00% hit rate (20 signals).
1. **PM 500-1000 ES**: 57.14% hit rate (7 signals).

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