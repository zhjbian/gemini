# Spike Analysis: Historical Reference Data (NVDA)

**Analysis Parameters:**
- **Generated**: 2026-07-04 10:29
- **Lookback**: 90 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 2.5%; Price Buffer $1.00; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 496

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 34 | 5.75% | 52.94% | 4.1 | 2.45% | 11.76% | 35.2 | 13.96% | 76.47% |
| RTH | 187 | 6.11% | 47.06% | 5.0 | 2.97% | 9.09% | 29.6 | 11.63% | 72.19% |
| AH | 275 | 6.98% | 53.82% | 5.2 | 3.03% | 4.73% | 38.4 | 15.32% | 80.00% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 65 | 6.01% | 46.15% | 3.6 | 2.67% | 13.85% | 32.0 | 11.77% | 73.85% |
| **10-19** | 17 | 6.36% | 52.94% | 8.3 | 4.28% | 11.76% | 25.5 | 10.26% | 82.35% |
| **20-49** | 34 | 6.26% | 38.24% | 4.5 | 2.19% | 2.94% | 21.0 | 9.37% | 58.82% |
| **50-100** | 35 | 6.54% | 54.29% | 5.2 | 2.70% | 8.57% | 24.3 | 10.08% | 80.00% |
| **100-499** | 24 | 6.02% | 29.17% | 4.7 | 4.06% | 8.33% | 35.0 | 15.82% | 58.33% |
| **500-999** | 4 | 5.94% | 75.00% | 14.3 | 8.12% | 0.00% | 0.0 | 0.00% | 100.00% |
| **1000-2000** | 1 | 3.30% | 100.00% | 1.0 | 0.07% | 0.00% | 0.0 | 0.00% | 100.00% |
| **2000-4999** | 2 | 2.92% | 50.00% | 3.0 | 1.26% | 0.00% | 0.0 | 0.00% | 50.00% |
| >=5000 | 5 | 4.94% | 100.00% | 4.4 | 1.73% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 16 | 4.03% | 75.00% | 3.4 | 2.88% | 6.25% | 49.0 | 19.63% | 81.25% |
| **10-19** | 1 | 3.75% | 0.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 100.00% |
| **20-49** | 6 | 8.51% | 16.67% | 18.0 | 5.51% | 33.33% | 34.5 | 16.28% | 66.67% |
| **50-100** | 3 | 7.57% | 66.67% | 2.0 | 0.19% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 7 | 7.26% | 28.57% | 5.5 | 1.79% | 14.29% | 23.0 | 3.66% | 57.14% |
| >=5000 | 1 | 2.72% | 100.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Skill Guidelines (NVDA Specific)

1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:
    - Any **PM** spike with **10+** Volume.
    - Any **RTH** spike with **50+** Volume.
2. **Tier 2 (Conviction Swings - 70% Confidence)**:
    - Any **RTH** spike with **20-49** Volume.
3. **Noise Filter (Ignore)**:
    - All **AH** spikes (Overshoot noise).
    - **RTH** spikes with **< 20** Volume.
    - **PM** spikes with **< 10** Volume.
