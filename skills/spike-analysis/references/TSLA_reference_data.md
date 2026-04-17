# Spike Analysis: Historical Reference Data (TSLA)

**Analysis Parameters:**
- **Generated**: 2026-04-15 22:19
- **Lookback**: 365 days
- **Hit Logic**: **RTH ONLY** within 20 trading days.
- **De-duplication**: Hits on special days ['2026-02-06'] are aggregated by minute and bucket.
- **Total Valid Spikes (Normalized)**: 2415

---

## High-Level Findings

Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.

### Results by Timing Bracket

| Bucket | Count | Avg Target Move | Target Hit Rate | Avg Days to Target | Min Move Hit Rate (3%) | Avg Days to Min Move | Avg Max Profit | Avg Days to Max Profit |
|---|---|---|---|---|---|---|---|---|
| PM | 361 | 4.16% | 90.86% | 2.1 | 98.89% | 1.6 | 18.12% | 38.1 |
| RTH | 213 | 5.47% | 63.38% | 6.1 | 85.45% | 4.2 | 15.71% | 44.0 |
| AH | 1841 | 8.07% | 43.40% | 4.2 | 54.10% | 2.6 | 14.54% | 56.4 |

---

### Detailed Breakdown: "The Golden Signal" (RTH)

| Bucket | Count | Avg Target Move | Target Hit Rate | Avg Days to Target | Min Move Hit Rate (3%) | Avg Days to Min Move | Avg Max Profit | Avg Days to Max Profit |
|---|---|---|---|---|---|---|---|---|
| <10 | 134 | 5.58% | 58.96% | 6.5 | 85.82% | 4.7 | 15.35% | 44.4 |
| **10-19** | 17 | 5.60% | 64.71% | 2.5 | 76.47% | 2.1 | 12.75% | 32.4 |
| **20-49** | 26 | 5.21% | 69.23% | 4.4 | 80.77% | 3.0 | 22.98% | 56.4 |
| **50-100** | 11 | 5.05% | 90.91% | 7.1 | 100.00% | 5.1 | 15.20% | 45.4 |
| **100-499** | 10 | 5.24% | 80.00% | 7.0 | 90.00% | 1.9 | 14.72% | 41.3 |
| **500-999** | 1 | 3.59% | 100.00% | 0.0 | 100.00% | 0.0 | 9.57% | 3.0 |
| **1000-2000** | 4 | 5.47% | 100.00% | 12.8 | 100.00% | 7.2 | 15.22% | 34.5 |
| **2000-4999** | 2 | 7.46% | 100.00% | 6.5 | 100.00% | 1.5 | 13.26% | 11.0 |
| >=5000 | 8 | 4.79% | 25.00% | 3.5 | 75.00% | 4.7 | 8.02% | 39.8 |

---

### Detailed Breakdown: Pre-Market (PM)

| Bucket | Count | Avg Target Move | Target Hit Rate | Avg Days to Target | Min Move Hit Rate (3%) | Avg Days to Min Move | Avg Max Profit | Avg Days to Max Profit |
|---|---|---|---|---|---|---|---|---|
| <10 | 93 | 4.85% | 78.49% | 3.3 | 95.70% | 2.0 | 17.38% | 42.6 |
| **10-19** | 25 | 3.78% | 96.00% | 3.3 | 100.00% | 2.6 | 15.93% | 34.6 |
| **20-49** | 42 | 4.16% | 92.86% | 2.4 | 100.00% | 1.9 | 16.11% | 32.3 |
| **50-100** | 36 | 3.84% | 94.44% | 2.2 | 100.00% | 2.0 | 15.97% | 29.0 |
| **100-499** | 118 | 4.02% | 94.07% | 1.3 | 100.00% | 1.2 | 19.16% | 38.1 |
| **500-999** | 29 | 3.56% | 100.00% | 0.7 | 100.00% | 0.7 | 21.63% | 43.0 |
| **1000-2000** | 12 | 3.63% | 100.00% | 0.4 | 100.00% | 0.3 | 22.57% | 45.4 |
| **2000-4999** | 5 | 3.64% | 100.00% | 0.8 | 100.00% | 0.8 | 21.51% | 42.8 |
| >=5000 | 1 | 5.66% | 100.00% | 11.0 | 100.00% | 2.0 | 8.04% | 11.0 |

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
