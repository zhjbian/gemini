# Spike Analysis: Historical Reference Data (TSLA)

**Analysis Parameters:**
- **Generated**: 2026-04-19 00:52
- **Lookback**: 365 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 3.0%; Price Buffer $1.00; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 1108

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 47 | 5.77% | 72.34% | 5.2 | 3.10% | 12.77% | 64.5 | 19.97% | 91.49% |
| RTH | 191 | 5.55% | 67.54% | 6.2 | 3.59% | 10.99% | 44.4 | 15.06% | 85.34% |
| AH | 870 | 9.72% | 51.26% | 5.5 | 2.70% | 14.71% | 68.8 | 15.56% | 69.54% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 115 | 5.66% | 66.96% | 6.4 | 3.59% | 12.17% | 29.2 | 11.31% | 85.22% |
| **10-19** | 19 | 5.56% | 52.63% | 2.8 | 1.38% | 0.00% | 0.0 | 0.00% | 73.68% |
| **20-49** | 25 | 5.28% | 72.00% | 5.3 | 4.21% | 12.00% | 65.7 | 18.30% | 84.00% |
| **50-100** | 10 | 5.20% | 90.00% | 7.9 | 4.66% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 9 | 5.42% | 77.78% | 5.6 | 3.56% | 11.11% | 130.0 | 30.45% | 88.89% |
| **1000-2000** | 3 | 6.10% | 100.00% | 17.0 | 5.91% | 0.00% | 0.0 | 0.00% | 100.00% |
| **2000-4999** | 1 | 11.35% | 100.00% | 13.0 | 2.53% | 0.00% | 0.0 | 0.00% | 100.00% |
| >=5000 | 9 | 4.66% | 44.44% | 2.2 | 2.58% | 33.33% | 65.7 | 24.24% | 88.89% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 39 | 5.80% | 66.67% | 4.8 | 2.95% | 15.38% | 64.5 | 19.97% | 89.74% |
| **10-19** | 2 | 3.66% | 100.00% | 12.0 | 6.02% | 0.00% | 0.0 | 0.00% | 100.00% |
| **20-49** | 3 | 7.65% | 100.00% | 4.7 | 2.42% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 1 | 4.66% | 100.00% | 1.0 | 0.91% | 0.00% | 0.0 | 0.00% | 100.00% |
| **500-999** | 1 | 4.73% | 100.00% | 1.0 | 0.90% | 0.00% | 0.0 | 0.00% | 100.00% |
| >=5000 | 1 | 5.66% | 100.00% | 11.0 | 7.67% | 0.00% | 0.0 | 0.00% | 100.00% |

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
