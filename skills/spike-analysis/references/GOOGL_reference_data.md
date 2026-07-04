# Spike Analysis: Historical Reference Data (GOOGL)

**Analysis Parameters:**
- **Generated**: 2026-07-04 10:29
- **Lookback**: 90 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **Delayed Logic**: Targets hit strictly AFTER 20 days.
- **Drawdown Logic**: Calculated **ONLY for successful hits**; tracks max excursion until moment of hit.
- **Filters**: Min Change 3.0%; Price Buffer $1.00; Clusters Merged.
- **De-duplication**: Bursts on special days ['2026-02-06'] aggregated by minute/bucket.
- **Total Valid Spikes (Normalized)**: 213

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| PM | 30 | 7.37% | 23.33% | 3.6 | 2.07% | 16.67% | 25.8 | 7.78% | 46.67% |
| RTH | 96 | 6.93% | 14.58% | 6.2 | 1.39% | 10.42% | 30.3 | 7.79% | 36.46% |
| AH | 87 | 7.23% | 44.83% | 5.9 | 2.05% | 0.00% | 0.0 | 0.00% | 60.92% |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 47 | 6.93% | 14.89% | 5.9 | 1.32% | 6.38% | 33.0 | 5.07% | 36.17% |
| **10-19** | 19 | 5.99% | 21.05% | 5.2 | 1.21% | 21.05% | 27.5 | 8.71% | 47.37% |
| **20-49** | 18 | 6.94% | 16.67% | 8.3 | 1.80% | 5.56% | 33.0 | 6.90% | 22.22% |
| **50-100** | 8 | 7.39% | 0.00% | 0.0 | 0.00% | 25.00% | 30.5 | 10.51% | 25.00% |
| **100-499** | 4 | 10.39% | 0.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 75.00% |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Move | Target Hit Rate | Avg Days (T) | DD (Target) | Delayed Hit Rate | Avg Days (D) | DD (Delayed) | Min Hit Rate |
|---|---|---|---|---|---|---|---|---|---|
| <10 | 19 | 4.35% | 31.58% | 3.3 | 1.73% | 15.79% | 26.3 | 7.94% | 42.11% |
| **10-19** | 4 | 13.40% | 25.00% | 5.0 | 4.07% | 25.00% | 21.0 | 6.17% | 100.00% |
| **20-49** | 5 | 12.77% | 0.00% | 0.0 | 0.00% | 20.00% | 29.0 | 8.91% | 20.00% |
| **50-100** | 2 | 10.60% | 0.00% | 0.0 | 0.00% | 0.00% | 0.0 | 0.00% | 50.00% |

---

### Skill Guidelines (GOOGL Specific)

1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:
    - Any **PM** spike with **10+** Volume.
    - Any **RTH** spike with **50+** Volume.
2. **Tier 2 (Conviction Swings - 70% Confidence)**:
    - Any **RTH** spike with **20-49** Volume.
3. **Noise Filter (Ignore)**:
    - All **AH** spikes (Overshoot noise).
    - **RTH** spikes with **< 20** Volume.
    - **PM** spikes with **< 10** Volume.
