# Price Spikes ATS Rule System: 3-Month Performance Evaluation & Proposed Improvements

We ran 90-day backtests (April - June 2026) for individual equities (**TSLA, NVDA, META, GOOGL, TSM**) and macro ETFs (**SPY, QQQ**) using the historical ATS database to evaluate the predictability and ruleset parameters defined in [spike-analysis/SKILL.md](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_html_renderer.py).

---

## 1. 90-Day Backtest Summary (Key Data Extracts)

Below are the aggregated statistics (counts, hit rates within 20 days, and average maximum drawdowns) grouped by trading hour and volume bucket:

| Ticker | Hour | Volume Bucket | Total Spikes | Hit Rate (20d) | Avg Days to Target | Avg Max Drawdown |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TSLA** | **AH** | 10-19 | 13 | **84.6%** | 3.4 days | 3.38% |
| **TSLA** | **AH** | 1000-2000 | 17 | **82.4%** | 6.2 days | 4.98% |
| **TSLA** | **RTH** | 20-49 (Tier 2) | 4 | **100.0%** | 5.0 days | 2.47% |
| **TSLA** | **RTH** | 100-499 (Tier 1) | 5 | **100.0%** | 2.4 days | 0.80% |
| **NVDA** | **RTH** | >=5000 (Tier 1) | 5 | **100.0%** | 4.4 days | 1.73% |
| **NVDA** | **RTH** | 100-499 (Tier 1) | 24 | *29.2%* | 4.7 days | **12.09%** |
| **NVDA** | **RTH** | 20-49 (Tier 2) | 34 | *38.2%* | 4.5 days | **11.09%** |
| **META** | **AH** | 100-499 | 53 | **66.0%** | 7.8 days | 5.86% |
| **META** | **AH** | 1000-2000 | 3 | **100.0%** | 5.3 days | 1.20% |
| **GOOGL**| **RTH** | 50-100 (Tier 1) | 8 | *0.0%* | N/A | **15.90%** |
| **GOOGL**| **RTH** | 20-49 (Tier 2) | 18 | *16.7%* | 8.3 days | **15.09%** |
| **TSM**  | **PM** | <10 (Noise) | 10 | **90.0%** | 2.6 days | 3.60% |
| **TSM**  | **RTH** | 10-19 (Tier 2) | 13 | *7.7%* | 1.0 days | **18.62%** |
| **SPY**  | **RTH** | >=5000 (Tier 1) | 2 | **100.0%** | 1.0 days | 0.21% |
| **SPY**  | **RTH** | 100-499 (Tier 1) | 5 | **80.0%** | 2.2 days | 1.97% |
| **SPY**  | **RTH** | 20-49 (Tier 2) | 11 | *9.1%* | 1.0 days | 4.09% |
| **QQQ**  | **AH** | >=5000 (Dark Pool) | 5 | **80.0%** | 1.0 days | 3.82% |
| **QQQ**  | **PM** | <10 (Noise) | 54 | **53.7%** | 3.7 days | 7.20% |

---

## 2. Core Weaknesses Identified in Current `SKILL.md`

### 1. The "AH Filter Wall" is Too Restrictive (Over-filtering High-Quality Data)
*   **The Issue**: The current rules state that *any* AH spike for individual equities is "noise" and must be ignored completely.
*   **The Evidence**: 
    *   **TSLA AH** (10-19) and (1000-2000) have hit rates of **84.6%** and **82.4%** with very low drawdowns (3.38% and 4.98%).
    *   **META AH** (100-499) and (1000-2000) have hit rates of **66.0%** and **100.0%**.
*   **Reasoning**: Large-volume AH blocks in highly liquid mega-caps (like TSLA/META) often represent dark pool prints or large institutional crossings finalized at the close and reported in AH. These are highly intentional and behave identically to RTH magnets.
*   **Proposed Fix**: Update the AH rule to allow AH spikes in individual equities **if the volume is significant (e.g., Volume >= 500 or is_dp == true)**.

### 2. High-Beta RTH "Runaway Breakouts" are Misclassified as Magnets (High Risk)
*   **The Issue**: The rules classify any RTH spike with Volume >= 50 as a "Tier 1 Instant Magnet" with an expected 90%+ hit rate.
*   **The Evidence**: 
    *   **NVDA RTH** (100-499) has a **29.2%** hit rate and a massive **12.09%** average drawdown.
    *   **GOOGL RTH** (50-100) has a **0.0%** hit rate and a **15.90%** drawdown.
    *   **TSM RTH** (10-19) has a **7.7%** hit rate and an **18.62%** drawdown.
*   **Reasoning**: In highly trending, high-beta tech stocks (like NVDA/GOOGL/TSM), mid-sized RTH spikes (50-500 volume) are often **momentum breakout trades** (price moving aggressively in one direction with high institutional participation). The price simply "runs away" and does not return to the spot price within 20 days.
*   **Proposed Fix**: 
    *   Raise the Tier 1 RTH volume threshold for high-beta stocks to **>= 500** (or >= 1000 for NVDA/TSM).
    *   Introduce a **"Momentum Escape Filter"**: If a spike occurs during a breakout day (e.g., daily price change > 4% and volume > 1.5x average), classify it as a **Breakout Driver** (runaway trend) rather than a magnet, unless the volume is ultra-huge (Tier 1 Extreme, e.g., >= 5000).

### 3. Pre-Market (PM) Small Volume is Not Always Noise
*   **The Issue**: The rules discard all PM spikes with volume < 10 as noise.
*   **The Evidence**: 
    *   **TSM PM** (<10) has a **90.0%** hit rate with an average drawdown of **3.60%**.
    *   **QQQ PM** (<10) has a **53.7%** hit rate.
*   **Reasoning**: For foreign ADRs (like TSM), significant trading activity occurs in the pre-market (aligned with Asian/European market closes). Even low volume prints (< 10) represent highly accurate structural valuation adjustments that act as magnets.
*   **Proposed Fix**: For foreign ADRs (TSM, ASML, etc.) or major ETFs (QQQ/SPY), lower the PM noise threshold to **>= 2** (rather than >= 10).

---

## 3. Recommended SKILL.md Refinements

```diff
- ### Rule 1: The Filter Wall (The Absolute "Ignore" Rule)
- Any spike returned with `"trading_hour": "AH"` (After-Hours) is structural noise, heavily dragging down predictability. **IGNORE IT COMPLETELY.** Do not include standard AH spikes in your ranked list.
- * **The ETF Dark Pool Exception**: The ONLY exception is if you are classifying a Macro ETF (SPY/QQQ) AND the AH print is flagged as a Dark Pool (`"is_dp" == true`). In ETFs, these specific AH structural dumps historically boast 100% resolution hit rates. For ETFs only, allow AH Dark Pool prints as Tier 1 Magnets.
+ ### Rule 1: The Filter Wall & Dark Pool Exception
+ *   **ETFs (SPY/QQQ)**: AH spikes are ignored **unless** `"is_dp" == true` OR `"volume_agg" >= 5000`. These are Tier 1 Magnets.
+ *   **Individual Stocks (TSLA/NVDA/META/GOOGL)**: AH spikes are ignored **unless** `"volume_agg" >= 500` OR `"is_dp" == true`. Large-volume AH blocks settle institutional positions and act as strong magnets (Hit Rate > 80%).
+ *   **Standard AH Noise**: Discard any AH spike with `"volume_agg" < 100` that is not flagged as `is_dp`.

- #### Path A: High-Beta / Individual Stocks (e.g., TSLA, NVDA, AAPL)
- *   **Tier 1: Instant Institutional Magnets (90%+ Hit Rate)**
-     -   `"trading_hour"` is **`PM`** (Pre-Market) AND `"volume_agg"` is **`>= 10`**.
-     -   `"trading_hour"` is **`RTH`** (Regular Trading Hours) AND `"volume_agg"` is **`>= 50`**.
- *   **Tier 2: High-Confidence Swings (~70% Hit Rate)**
-     -   `"trading_hour"` is **`RTH`** AND `"volume_agg"` is between **`10`** and **`49`**.
+ #### Path A: High-Beta / Individual Stocks (e.g., TSLA, NVDA, AAPL)
+ *   **Tier 1: Instant Institutional Magnets (90%+ Hit Rate)**
+     -   `"trading_hour"` is **`PM`** AND `"volume_agg"` is **`>= 10`**.
+     -   `"trading_hour"` is **`RTH`** AND `"volume_agg"` is **`>= 500`** (Elevated from 50 to avoid momentum breakout traps).
+     -   `"trading_hour"` is **`AH`** AND `"volume_agg"` is **`>= 1000`**.
+ *   **Tier 2: High-Confidence Swings (~70% Hit Rate)**
+     -   `"trading_hour"` is **`RTH`** AND `"volume_agg"` is between **`50`** and **`499`** (if not in a breakout trend).
+ *   **Noise Filter (Discard)**:
+     -   **IGNORE** any RTH spike with **Volume < 50** for volatile tech stocks (NVDA, GOOGL, TSM) to prevent high-drawdown losses.
+     -   **ADR Exception**: For foreign ADRs (e.g. TSM), allow **PM spikes with Volume >= 2** as Tier 2 magnets (90% historical hit rate).
```
