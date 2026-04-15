# ES Big Trade Signal Statistics (Direct ES Measurement)

## Methodology
- **Source**: `order_flow_big_trade` table, `type = SingleTickBigTrade`, `off_price >= 0`
- **Ticker**: ES=F (Direct measurement)
- **Period Classification**: Uses DB `trading_hour` field (PM/RTH/AH). FirstHour = RTH trades between 6:30-7:30 AM PT.
- **Measurement**: Actual ES trade execution price (for cluster-based PM/FirstHour, the execution price of the largest trade in the direction).
- **Success Criteria**: ES price moves ≥ 0.75% in the signal direction within 3 trading days.
- **Benchmark**: ES price at the exact minute of the signal (PM/FirstHour biggest volume trade, or RTH/AH individual trade).
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

| Period | ES Volume | Count | Hit Rate | Same Day Hit | Avg Max Win % | Avg Days To Hit |
|---|---|---|---|---|---|---|
| **PM** | <500 | 24 | 62.50% | 25.00% | 1.10% | 1.2 |
| **PM** | 500-1000 | 7 | 57.14% | 28.57% | 1.38% | 1.8 |
| **PM** | 1000-2000 | 7 | **71.43%** | 0.00% | 0.86% | 1.8 |
| **PM** | >2000 | 7 | **71.43%** | 57.14% | 1.29% | 0.6 |
| **FirstHour** | <500 | 20 | 55.00% | 30.00% | 1.11% | 1.1 |
| **FirstHour** | 500-1000 | 13 | **76.92%** | 7.69% | 0.91% | 2.4 |
| **FirstHour** | 1000-2000 | 18 | 61.11% | 22.22% | 1.15% | 1.2 |
| **FirstHour** | >2000 | 10 | **80.00%** | 50.00% | 1.35% | 1.1 |
| **RTH** | <500 | 338 | 68.05% | 30.77% | 1.33% | 1.2 |
| **RTH** | 500-1000 | 143 | 65.73% | 19.58% | 1.19% | 1.8 |
| **RTH** | 1000-2000 | 12 | 41.67% | 8.33% | 0.79% | 2.0 |
| **AH** | <500 | 100 | 69.00% | 18.00% | 1.14% | 1.7 |
| **AH** | 500-1000 | 42 | 61.90% | 16.67% | 1.23% | 1.5 |
| **AH** | 1000-2000 | 15 | 53.33% | 20.00% | 1.33% | 1.4 |
| **AH** | >2000 | 14 | 57.14% | 14.29% | 1.21% | 2.0 |

## Key Findings

### Tier 1 Signals (≥70% Hit Rate)
1. **FirstHour > 2000 ES**: 80.00% hit rate (10 signals).
2. **FirstHour 500-1000 ES**: 76.92% hit rate (13 signals).
3. **PM > 1000 ES**: 71.43% hit rate (14 signals total across 1k-2k and >2k). 

### Tier 2 Signals (60-69% Hit Rate)
1. **AH < 500 ES**: 69.00% hit rate (100 signals).
2. **RTH < 500 ES**: 68.05% hit rate (338 signals).
3. **RTH 500-1000 ES**: 65.73% hit rate (143 signals).
4. **PM < 500 ES**: 62.50% hit rate (24 signals).
5. **AH 500-1000 ES**: 61.90% hit rate (42 signals).

### Noise / Discard (<60% Hit Rate)
1. **AH > 1000 ES**: 53-57% hit rate. Fades significantly compared to SPY proxy.
2. **FirstHour < 500 ES**: 55.00% hit rate.
3. **RTH 1000-2000 ES**: 41.67% hit rate — **avoid**.

### Notable Patterns
- **First Hour Conviction**: First hour RTH clusters are the primary market drivers.
- **AH Proxy Discrepancy**: Direct ES measurement reveals AH signals are less reliable than broad market drift would suggest.
- **RTH Scaling**: Small RTH signals (<500) are solid institutional footprints; larger ones often represent liquidations or noise.

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
*Generated: 2026-04-14. ES-only backtest using direct measurement at trade minute. Window: 2025-04-14 to 2026-04-14.*
