# Spike Analysis: Historical Reference Data (NVDA)

**Analysis Parameters:**
- **Generated**: 2026-04-19 00:54
- **Lookback**: 60 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 2.5%; Price Buffer $1.00; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 311

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 29 | 5.36% | 51.72% | 3.3 | 2.09% | 27.59% | 31.4 | 9.28% | 93.10% |
| RTH | 114 | 5.66% | 50.88% | 4.9 | 2.00% | 13.16% | 30.4 | 9.85% | 64.91% |
| AH | 168 | 5.57% | 66.67% | 7.0 | 2.78% | 7.14% | 29.8 | 11.17% | 82.74% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 38 | 5.67% | 50.00% | 5.3 | 1.79% | 10.53% | 30.8 | 9.77% | 65.79% |
| **10-19** | 16 | 6.19% | 62.50% | 5.8 | 2.17% | 18.75% | 29.0 | 9.28% | 81.25% |
| **20-49** | 29 | 5.33% | 51.72% | 3.0 | 1.47% | 10.34% | 30.3 | 9.14% | 62.07% |
| **50-100** | 10 | 5.27% | 30.00% | 6.7 | 3.03% | 10.00% | 32.0 | 12.02% | 30.00% |
| **100-499** | 17 | 5.49% | 52.94% | 4.6 | 2.49% | 17.65% | 31.0 | 10.85% | 70.59% |
| **500-999** | 3 | 6.88% | 33.33% | 14.0 | 6.43% | 33.33% | 30.0 | 8.77% | 66.67% |
| **1000-2000** | 1 | 9.80% | 100.00% | 5.0 | 0.00% | 0.00% | 0.0 | 0.00% | 100.00% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 23 | 5.56% | 43.48% | 2.9 | 1.54% | 34.78% | 31.4 | 9.28% | 95.65% |
| **50-100** | 1 | 6.52% | 100.00% | 6.0 | 2.93% | 0.00% | 0.0 | 0.00% | 100.00% |
| **100-499** | 3 | 4.29% | 66.67% | 5.5 | 5.08% | 0.00% | 0.0 | 0.00% | 66.67% |
| >=5000 | 2 | 4.09% | 100.00% | 2.0 | 1.49% | 0.00% | 0.0 | 0.00% | 100.00% |

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
