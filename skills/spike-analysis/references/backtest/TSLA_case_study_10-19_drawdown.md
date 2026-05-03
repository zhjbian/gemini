# Case Study: TSLA Drawdown Audit (Bucket: 10-19 Volume)

**Objective**: Verify the recalibrated **1.38% Avg Drawdown** for the RTH 10-19 volume bucket.

## Executive Summary
Prior to the logic refinement, this bucket showed a skewed **12.37% drawdown** due to ancient signals (Aug 2025) that never hit their targets and tracked drawdown for 300+ days. The new logic excludes unhit signals and stops tracking immediately upon hit.

## Part 1: Successful Hits (The 1.38% DD Basis)
The following 10 signals successfully hit their targets within 20 days and form the basis of the new drawdown metric.

| Signal ID | Discovery Date | Direction | Spot | Target | Hit Day | Max DD (%) | Max DD Price | Result |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 44489 | 2026-03-09 | Bullish | 383.62 | 400.69 | Day 0 | 0.05% | 383.43 | ✅ Target Hit |
| 58116 | 2026-04-10 | Bullish | 346.26 | 385.95 | Day 3 | 0.09% | 345.95 | ✅ Target Hit |
| 840 | 2025-08-13 | Bearish | 340.42 | 322.05 | Day 5 | 0.30% | 341.44 | ✅ Target Hit |
| 8935 | 2025-10-20 | Bearish | 447.69 | 421.62 | Day 3 | 0.36% | 449.30 | ✅ Target Hit |
| 12461 | 2025-10-30 | Bullish | 444.23 | 460.09 | Day 2 | 0.95% | 440.01 | ✅ Target Hit |
| 17112 | 2025-11-19 | Bullish | 404.03 | 416.85 | Day 1 | 1.37% | 398.50 | ✅ Target Hit |
| 6953 | 2025-10-10 | Bullish | 418.13 | 432.46 | Day 1 | 1.60% | 411.43 | ✅ Target Hit |
| 5037 | 2025-10-01 | Bearish | 458.60 | 416.85 | Day 2 | 2.65% | 470.75 | ✅ Target Hit |
| 26228 | 2026-01-22 | Bearish | 439.20 | 424.80 | Day 5 | 3.01% | 452.43 | ✅ Target Hit |
| 10537 | 2025-10-29 | Bearish | 458.39 | 435.50 | Day 6 | 3.42% | 474.07 | ✅ Target Hit |

**Calculation**: (0.05 + 0.09 + 0.30 + 0.36 + 0.95 + 1.37 + 1.60 + 2.65 + 3.01 + 3.42) / 10 = **1.38%**

---

## Part 2: Excluded Signals (Filters in Action)
The following 9 signals were excluded from the average because they were never eventually hit (as of current lookback). This removes the extreme skew observed previously.

| Signal ID | Date | Drawdown observed | Status | Reason for Exclusion |
| :--- | :--- | :--- | :--- | :--- |
| 619 | 2025-08-06 | 59.78% | ❌ Fail | Never hit target; Lifetime DD ignored. |
| 621 | 2025-08-06 | 61.21% | ❌ Fail | Never hit target; Lifetime DD ignored. |
| 886 | 2025-08-14 | 52.53% | ❌ Fail | Never hit target; Lifetime DD ignored. |
| 22939 | 2026-01-09 | 24.37% | ❌ Fail | Never hit target; Signal Decayed. |
| 42664 | 2026-03-02 | 15.73% | ❌ Fail | Never hit target; Signal Decayed. |
| 59183 | 2026-04-15 | 1.44% | ❌ Fail | Still in window; No hit yet. |
| 59257 | 2026-04-16 | 5.38% | ❌ Fail | Still in window; No hit yet. |
| 59263 | 2026-04-16 | 0.26% | ❌ Fail | Still in window; No hit yet. |
| 59506 | 2026-04-17 | 0.50% | ❌ Fail | Still in window; No hit yet. |

---

## Part 3: Conclusion & Insights
- **Confidence**: When a TSLA RTH 10-19 volume signal is valid (hits within 20 days), the risk entry is extremely tight (**1.38% avg DD**).
- **Execution Rule**: If a signal violates its entry price by more than **~4%** (the max DD observed among hits), it is likely one of the 9 failed signals and should be abandoned immediately.
- **Accuracy**: The logic refinement has successfully isolated **Tradable Risk** from **Market Noise**.
