# Spike Analysis: Historical Reference Data (QQQ)

**Analysis Parameters:**
- **Ticker Analyzed**: QQQ
- **Timeframe**: Last 180 Days (6 Months)
- **Data Source**: Re-run explicitly using the **`SpikeMWAgg`** database table.
- **Methodology**: Evaluated whether the `target_price` of an abnormal off-market print ("Spike") was reached or crossed in the daily trading range (OHLC).
- **Exclusions**: Threw out all `is_prev_close == True` spikes AND strictly excluded all prints with a `price_change < 1%`. *(Note: ETFs utilize a 1% gap threshold because their native beta is too low to reliably trigger 2% day-over-day gaps organically).*
- **Total Valid Spikes Analyzed**: 1,590

---

## High-Level Findings

QQQ perfectly mirrors the macro structural findings of SPY. The `>= 1%` filter isolates extremely high-conviction trades that flawlessly point to forward liquidity pools.
Overall Hit Rate for QQQ `>= 1%` Gaps: **95.91%**

## Time of Day (PM vs RTH vs AH)

| Timing Bracket | Spike Count | Actual Hit Rate | Avg Days to Hit |
| :--- | :--- | :--- | :--- |
| **Pre-Market (PM)** | 1,181 | **98.22%** | **1.7 Days** |
| **Regular Hours (RTH)** | 136 | **85.29%** | 14.0 Days |
| **After-Hours (AH)** | 273 | **91.21%** | 12.1 Days |

* **Conclusion**: Pre-Market (`PM`) prints exhibiting a `>= 1%` gap are extraordinarily accurate. Across nearly 1,200 instances, they hit at 98.2% within roughly 2 days.

## Total Aggregated Volume (Regardless of Time of Day)

Zooming out to aggregated block sizes, QQQ verifies the exact same scaling behavior as SPY.

| Aggregated Volume Bucket | Spike Count | Actual Hit Rate | Avg Days to Hit |
| :--- | :--- | :--- | :--- |
| < 100 Volume | 882 | 93.65% | 5.1 Days |
| **100 - 499 Volume** | 473 | **98.52%** | **3.7 Days** |
| **500 - 999 Volume** | 121 | **100.00%** | **2.5 Days** |
| **1,000 - 4,999 Volume** | 93 | **98.92%** | **2.4 Days** |
| **>= 5,000 Volume** | 21 | **95.24%** | **4.2 Days** |

* **Conclusion**: Volume holds immense gravity. Over `500` volume, the hit rate ranges from 95% to 100%, completing reliably in cleanly 2 to 4 days across all buckets.

## Deep Dive: After-Hours (AH) and Dark Pools (`is_dp`)

| AH Segmentation | Spike Count | Actual Hit Rate | Avg Days to Hit |
| :--- | :--- | :--- | :--- |
| AH + `is_dp == False` | 231 | 89.61% | 14.1 Days |
| **AH + `is_dp == True`** | **42** | **100.00%** | **2.3 Days** |
| **AH + Volume >= 1,000 + `is_dp == True`** | **26** | **100.00%** | **2.4 Days** |

* **Conclusion**: The Golden ETF Rule holds up beautifully on QQQ. While unstructured AH prints drift, **every single After-Hours Dark Pool trade (`is_dp == True`) over the last 6 months hit perfectly.** It resolves with a 100% completion rate in 2.3 days. 

### Skill Implications for QQQ
The rules map identically to the Macro ETF Fallback Matrix in `SKILL.md`:
1. **Tier 1 (Instant Macro Magnets)**: Any `PM` spike (gap `>= 1%`), or any spike with `volume >= 500` which practically hits 100%. Also, **ANY AH print flagged as a Dark Pool (`is_dp == True`)**.
2. **Tier 2 (The Multi-Week Swing Magnets)**: Any spike carrying `100 - 499` volume securely pulls QQQ directionally with 98.5% certainty over roughly ~3 days.
3. **Filter**: Dismiss low-volume `< 100` prints or arbitrary `AH` prints that are NOT Dark Pools.
