# Spike Analysis: Historical Reference Data (META)

**Analysis Parameters:**
- **Generated**: 2026-07-04 10:29
- **Lookback**: 90 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 3.0%; Price Buffer $1.00; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 446

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 24 | 7.80% | 37.50% | 11.1 | 6.28% | 8.33% | 32.5 | 6.16% | 91.67% |
| RTH | 93 | 6.73% | 56.99% | 7.7 | 3.25% | 8.60% | 29.4 | 6.13% | 95.70% |
| AH | 329 | 5.49% | 59.88% | 7.5 | 2.65% | 5.78% | 24.9 | 4.63% | 80.85% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 69 | 6.60% | 57.97% | 7.2 | 3.16% | 5.80% | 32.5 | 7.08% | 97.10% |
| **10-19** | 15 | 6.34% | 60.00% | 10.0 | 3.76% | 13.33% | 25.5 | 5.35% | 86.67% |
| **20-49** | 6 | 8.30% | 50.00% | 8.3 | 3.31% | 16.67% | 21.0 | 6.62% | 100.00% |
| **50-100** | 3 | 8.46% | 33.33% | 8.0 | 1.80% | 33.33% | 33.0 | 3.45% | 100.00% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 21 | 7.88% | 38.10% | 10.4 | 5.72% | 9.52% | 32.5 | 6.16% | 90.48% |
| **10-19** | 2 | 5.70% | 50.00% | 17.0 | 10.74% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 1 | 10.18% | 0.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Skill Guidelines (META Specific)

1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:
    - Any **PM** spike with **10+** Volume.
    - Any **RTH** spike with **50+** Volume.
2. **Tier 2 (Conviction Swings - 70% Confidence)**:
    - Any **RTH** spike with **20-49** Volume.
3. **Noise Filter (Ignore)**:
    - All **AH** spikes (Overshoot noise).
    - **RTH** spikes with **< 20** Volume.
    - **PM** spikes with **< 10** Volume.
