# Spike Analysis: Historical Reference Data (QQQ)

**Analysis Parameters:**
- **Generated**: 2026-04-18 21:49
- **Lookback**: 180 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 1.0%; Price Buffer $0.50; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 352

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 105 | 1.91% | 82.86% | 2.0 | 0.94% | 2.86% | 63.3 | 5.22% | 71.43% |
| RTH | 142 | 2.62% | 69.01% | 5.5 | 1.64% | 10.56% | 50.1 | 5.44% | 62.68% |
| AH | 105 | 5.15% | 56.19% | 8.4 | 0.79% | 19.05% | 46.6 | 2.97% | 74.29% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 90 | 2.46% | 74.44% | 4.8 | 1.50% | 4.44% | 53.2 | 5.85% | 64.44% |
| **10-19** | 16 | 3.16% | 62.50% | 6.3 | 1.59% | 25.00% | 46.0 | 3.59% | 56.25% |
| **20-49** | 15 | 2.96% | 73.33% | 10.3 | 2.41% | 6.67% | 56.0 | 5.20% | 66.67% |
| **50-100** | 4 | 3.52% | 0.00% | 0.0 | 0.00% | 100.00% | 53.5 | 5.08% | 50.00% |
| **100-499** | 7 | 3.18% | 57.14% | 3.0 | 1.25% | 14.29% | 28.0 | 6.28% | 71.43% |
| **2000-4999** | 3 | 1.93% | 33.33% | 8.0 | 3.96% | 0.00% | 0.0 | 0.00% | 33.33% |
| >=5000 | 7 | 1.88% | 71.43% | 4.8 | 1.64% | 14.29% | 56.0 | 12.00% | 57.14% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 59 | 2.14% | 71.19% | 2.5 | 1.32% | 5.08% | 63.3 | 5.22% | 57.63% |
| **10-19** | 2 | 1.81% | 100.00% | 3.0 | 1.36% | 0.00% | 0.0 | 0.00% | 100.00% |
| **20-49** | 2 | 2.70% | 100.00% | 7.0 | 1.86% | 0.00% | 0.0 | 0.00% | 100.00% |
| **50-100** | 3 | 1.41% | 100.00% | 0.0 | 0.13% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 5 | 1.38% | 100.00% | 1.8 | 1.18% | 0.00% | 0.0 | 0.00% | 80.00% |
| **500-999** | 2 | 1.62% | 100.00% | 5.0 | 1.53% | 0.00% | 0.0 | 0.00% | 100.00% |
| **1000-2000** | 6 | 1.92% | 83.33% | 3.6 | 0.73% | 0.00% | 0.0 | 0.00% | 83.33% |
| **2000-4999** | 6 | 1.29% | 100.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 100.00% |
| >=5000 | 20 | 1.59% | 100.00% | 0.7 | 0.36% | 0.00% | 0.0 | 0.00% | 85.00% |

---

### Skill Guidelines (QQQ Specific)

1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:
    - Any **PM** spike with **10+** Volume.
    - Any **RTH** spike with **50+** Volume.
2. **Tier 2 (Conviction Swings - 70% Confidence)**:
    - Any **RTH** spike with **20-49** Volume.
3. **Noise Filter (Ignore)**:
    - All **AH** spikes (Overshoot noise).
    - **RTH** spikes with **< 20** Volume.
    - **PM** spikes with **< 10** Volume.
