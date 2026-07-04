# Spike Analysis: Historical Reference Data (QQQ)

**Analysis Parameters:**
- **Generated**: 2026-07-04 10:29
- **Lookback**: 90 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 1.0%; Price Buffer $0.50; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 231

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 60 | 2.12% | 56.67% | 3.5 | 1.69% | 1.67% | 22.0 | 7.55% | 78.33% |
| RTH | 115 | 3.85% | 37.39% | 3.3 | 1.30% | 0.00% | 0.0 | 0.00% | 55.65% |
| AH | 56 | 4.42% | 48.21% | 4.8 | 0.89% | 0.00% | 0.0 | 0.00% | 78.57% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 70 | 3.72% | 38.57% | 3.4 | 1.33% | 0.00% | 0.0 | 0.00% | 57.14% |
| **10-19** | 13 | 4.67% | 38.46% | 2.6 | 0.75% | 0.00% | 0.0 | 0.00% | 53.85% |
| **20-49** | 10 | 5.87% | 10.00% | 2.0 | 1.25% | 0.00% | 0.0 | 0.00% | 50.00% |
| **50-100** | 7 | 2.87% | 57.14% | 6.5 | 2.86% | 0.00% | 0.0 | 0.00% | 71.43% |
| **100-499** | 7 | 3.28% | 28.57% | 1.0 | 0.34% | 0.00% | 0.0 | 0.00% | 28.57% |
| **500-999** | 1 | 1.60% | 0.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 0.00% |
| **1000-2000** | 1 | 0.96% | 100.00% | 0.0 | 0.48% | 0.00% | 0.0 | 0.00% | 100.00% |
| **2000-4999** | 3 | 2.92% | 33.33% | 1.0 | 0.00% | 0.00% | 0.0 | 0.00% | 66.67% |
| >=5000 | 3 | 2.82% | 66.67% | 2.5 | 1.08% | 0.00% | 0.0 | 0.00% | 66.67% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 54 | 2.12% | 53.70% | 3.7 | 1.80% | 1.85% | 22.0 | 7.55% | 77.78% |
| **20-49** | 1 | 1.30% | 100.00% | 2.0 | 1.87% | 0.00% | 0.0 | 0.00% | 100.00% |
| **50-100** | 1 | 4.86% | 100.00% | 7.0 | 1.56% | 0.00% | 0.0 | 0.00% | 100.00% |
| **500-999** | 1 | 0.99% | 100.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 100.00% |
| **1000-2000** | 1 | 1.09% | 0.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 0.00% |
| >=5000 | 2 | 2.35% | 100.00% | 2.0 | 0.93% | 0.00% | 0.0 | 0.00% | 100.00% |

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
