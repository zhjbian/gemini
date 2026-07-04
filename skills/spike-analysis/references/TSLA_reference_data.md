# Spike Analysis: Historical Reference Data (TSLA)

**Analysis Parameters:**
- **Generated**: 2026-07-04 10:29
- **Lookback**: 90 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 3.0%; Price Buffer $1.00; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 401

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 12 | 8.52% | 66.67% | 4.9 | 2.50% | 0.00% | 0.0 | 0.00% | 91.67% |
| RTH | 112 | 6.45% | 75.89% | 5.1 | 2.57% | 6.25% | 28.6 | 12.52% | 89.29% |
| AH | 277 | 6.16% | 66.06% | 5.0 | 2.94% | 4.69% | 30.3 | 11.47% | 77.98% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 84 | 6.51% | 73.81% | 5.0 | 2.78% | 7.14% | 27.2 | 11.83% | 90.48% |
| **10-19** | 12 | 7.02% | 75.00% | 8.2 | 3.00% | 8.33% | 37.0 | 16.65% | 83.33% |
| **20-49** | 4 | 5.78% | 100.00% | 5.0 | 2.47% | 0.00% | 0.0 | 0.00% | 100.00% |
| **50-100** | 7 | 6.27% | 71.43% | 2.2 | 0.97% | 0.00% | 0.0 | 0.00% | 71.43% |
| **100-499** | 5 | 4.90% | 100.00% | 2.4 | 0.80% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 7 | 8.49% | 57.14% | 4.2 | 2.24% | 0.00% | 0.0 | 0.00% | 85.71% |
| **10-19** | 3 | 8.52% | 66.67% | 5.5 | 3.21% | 0.00% | 0.0 | 0.00% | 100.00% |
| **20-49** | 1 | 11.53% | 100.00% | 3.0 | 1.04% | 0.00% | 0.0 | 0.00% | 100.00% |
| **50-100** | 1 | 5.78% | 100.00% | 8.0 | 3.56% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Skill Guidelines (TSLA Specific)

1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:
    - Any **PM** spike with **10+** Volume.
    - Any **RTH** spike with **50+** Volume.
2. **Tier 2 (Conviction Swings - 70% Confidence)**:
    - Any **RTH** spike with **20-49** Volume.
3. **Noise Filter (Ignore)**:
    - All **AH** spikes (Overshoot noise).
    - **RTH** spikes with **< 20** Volume.
    - **PM** spikes with **< 10** Volume.
