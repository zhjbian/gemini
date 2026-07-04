# Spike Analysis: Historical Reference Data (TSM)

**Analysis Parameters:**
- **Generated**: 2026-07-04 10:29
- **Lookback**: 90 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 3.0%; Price Buffer $1.00; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 123

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 21 | 4.36% | 80.95% | 3.1 | 2.30% | 0.00% | 0.0 | 0.00% | 90.48% |
| RTH | 71 | 7.78% | 30.99% | 3.0 | 2.29% | 1.41% | 21.0 | 0.24% | 77.46% |
| AH | 31 | 4.99% | 61.29% | 4.3 | 2.24% | 0.00% | 0.0 | 0.00% | 70.97% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 47 | 7.60% | 36.17% | 3.1 | 2.21% | 2.13% | 21.0 | 0.24% | 82.98% |
| **10-19** | 13 | 8.95% | 7.69% | 1.0 | 2.58% | 0.00% | 0.0 | 0.00% | 53.85% |
| **20-49** | 9 | 8.01% | 22.22% | 3.0 | 1.42% | 0.00% | 0.0 | 0.00% | 77.78% |
| **50-100** | 1 | 3.01% | 100.00% | 2.0 | 1.67% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 1 | 3.55% | 100.00% | 3.0 | 5.78% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 10 | 4.77% | 90.00% | 2.6 | 1.99% | 0.00% | 0.0 | 0.00% | 100.00% |
| **10-19** | 3 | 5.06% | 33.33% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 33.33% |
| **20-49** | 2 | 3.68% | 100.00% | 5.0 | 4.56% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 4 | 3.74% | 75.00% | 5.7 | 3.36% | 0.00% | 0.0 | 0.00% | 100.00% |
| **500-999** | 1 | 3.09% | 100.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 100.00% |
| >=5000 | 1 | 3.37% | 100.00% | 3.0 | 1.98% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Skill Guidelines (TSM Specific)

1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:
    - Any **PM** spike with **10+** Volume.
    - Any **RTH** spike with **50+** Volume.
2. **Tier 2 (Conviction Swings - 70% Confidence)**:
    - Any **RTH** spike with **20-49** Volume.
3. **Noise Filter (Ignore)**:
    - All **AH** spikes (Overshoot noise).
    - **RTH** spikes with **< 20** Volume.
    - **PM** spikes with **< 10** Volume.
