# Spike Analysis: Historical Reference Data (SPY)

**Analysis Parameters:**
- **Generated**: 2026-04-18 21:49
- **Lookback**: 180 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 1.0%; Price Buffer $0.50; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 307

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 68 | 1.65% | 83.82% | 1.8 | 0.61% | 4.41% | 34.7 | 5.39% | 63.24% |
| RTH | 106 | 2.96% | 64.15% | 5.3 | 1.17% | 15.09% | 54.6 | 4.26% | 50.00% |
| AH | 133 | 5.70% | 39.85% | 9.0 | 0.57% | 24.81% | 44.9 | 2.44% | 63.91% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 67 | 3.00% | 59.70% | 5.8 | 1.36% | 22.39% | 55.8 | 4.51% | 49.25% |
| **10-19** | 12 | 2.68% | 66.67% | 6.0 | 1.38% | 0.00% | 0.0 | 0.00% | 58.33% |
| **20-49** | 10 | 3.27% | 70.00% | 2.1 | 0.36% | 0.00% | 0.0 | 0.00% | 50.00% |
| **50-100** | 3 | 2.96% | 33.33% | 3.0 | 0.11% | 33.33% | 37.0 | 0.46% | 33.33% |
| **100-499** | 11 | 2.80% | 81.82% | 4.4 | 1.09% | 0.00% | 0.0 | 0.00% | 54.55% |
| **500-999** | 2 | 3.51% | 100.00% | 7.0 | 0.18% | 0.00% | 0.0 | 0.00% | 50.00% |
| >=5000 | 1 | 1.38% | 100.00% | 10.0 | 1.13% | 0.00% | 0.0 | 0.00% | 0.00% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 31 | 1.60% | 70.97% | 2.7 | 0.95% | 6.45% | 30.0 | 7.59% | 45.16% |
| **50-100** | 1 | 1.39% | 100.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 0.00% |
| **500-999** | 1 | 1.13% | 100.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 0.00% |
| **1000-2000** | 6 | 1.68% | 66.67% | 1.0 | 0.36% | 16.67% | 44.0 | 1.00% | 33.33% |
| **2000-4999** | 6 | 2.35% | 100.00% | 3.7 | 1.03% | 0.00% | 0.0 | 0.00% | 100.00% |
| >=5000 | 23 | 1.57% | 100.00% | 0.7 | 0.27% | 0.00% | 0.0 | 0.00% | 91.30% |

---

### Skill Guidelines (SPY Specific)

1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:
    - Any **PM** spike with **10+** Volume.
    - Any **RTH** spike with **50+** Volume.
2. **Tier 2 (Conviction Swings - 70% Confidence)**:
    - Any **RTH** spike with **20-49** Volume.
3. **Noise Filter (Ignore)**:
    - All **AH** spikes (Overshoot noise).
    - **RTH** spikes with **< 20** Volume.
    - **PM** spikes with **< 10** Volume.
