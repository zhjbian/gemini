---
name: order-flow-analysis
description: Analyze institutional big trades (SingleTickBigTrade) in ES to identify high-conviction market directional signals. Identifies Tier 1 (≥73% hit rate) and Tier 2 (55-70% hit rate) opportunities based on volume buckets and time periods.
---

# Order Flow Analysis

## Overview

Process institutional order flow (ES "SingleTickBigTrade" records) to identify directional signals. This skill classifies clusters of trades into conviction tiers based on 12 months of historical backtesting using direct ES measurement.

## Workflow

1.  **Fetch Data**: Run the fetching script for a specific date (YYYY-MM-DD).
    ```bash
    python3 /Users/zhijiebian/.gemini/skills/order-flow-analysis/scripts/fetch_big_trades.py <date>
    ```

2.  **Calibrate Targets**: Always cross-reference the latest statistical findings in:
    `references/big_trade_stats.md`

3.  **Classify Signals**: Assign each signal to a Tier based on volume and period (see Decision Rules).

4.  **Aggregate PM/FirstHour**: Combined into single directional signals per day.
5.  **Individual RTH/AH**: Each big trade is treated as an individual signal.

## Decision Rules

### Conviction Tiers (ES ≥0.75% move within 3 days)

#### Tier 1: High Conviction (≥70% Hit Rate)
*   **FirstHour**: Total ES volume ≥ 500 (77-80% hit rate).
*   **PM (Pre-Market)**: Total ES volume > 1000 (71% hit rate).

#### Tier 2: Elevated Conviction (60-69% Hit Rate)
*   **RTH (Regular Hours)**: ES volume < 1000 (66-68% hit rate).
*   **AH (After-Hours)**: ES volume < 1000 (62-69% hit rate).
*   **PM**: Total ES volume ≤ 1000 (57-63% hit rate).
*   **FirstHour**: Total ES volume < 500 (55% hit rate).

#### Noise / Discard (<60% Hit Rate)
*   **RTH**: ES volume ≥ 1000 (42% hit rate) — **avoid**.
*   **AH**: ES volume ≥ 1000 (53-57% hit rate) — **fades rapidly**.


## Output Requirements

When reporting results, always include:
- **Period**: (PM, FirstHour, RTH, AH)
- **Classification**: (Tier 1, Tier 2, or Discard)
- **Direction**: (Bullish if Net Vol > 0, Bearish if Net Vol < 0)
- **ES Volume**: Total ES-equivalent volume.
- **Trade Composition**: `[Total Trades] / [Big Trades ≥ 500]`
- **Historical Context**: "Resolves same-day X% of the time based on history."

## Contextual Intention Engine (Equities)

For stock-specific block flow (e.g., TSLA > 400k volume), we actively override unreliable `mw_side` TRF tagging via historical lit-tape absorption:

1.  **Macro Trend State Exhaustion**: Examines the previous 20-day high/low range.
    -   Prints in the **Top 30%** are overridden to Macro Pivots: **Sell**.
    -   Prints in the **Bottom 30%** are overridden to Macro Pivots: **Buy**.
This rule accurately anticipates mature excursions over 20-60 day spans.

## Implementation Notes

- **Period Definition**: Use the database `trading_hour` field for classification.
- **Sub-classification**: Manually split `RTH` into `FirstHour` (6:30-7:30 AM PT) vs rest of `RTH`.
- **Normalization**: Only ES data is used for analysis. Big trades in other tickers should be ignored for this specific skill.
- **Benchmark**: Measure the 0.75% move from the **direct ES trade execution price**. For PM/FirstHour clusters, use the execution price of the biggest direction trade as the baseline.
- **Weak Signal Filter (Aggregated Periods Only)**: Discard **PM** or **FirstHour** signals if `counter_volume / total_gross_volume >= 0.25`. This indicates diluted institutional conviction (e.g., a mix of buying and selling that cancels out the net direction).

---
*Reference Stats Path: /Users/zhijiebian/.gemini/skills/order-flow-analysis/references/big_trade_stats.md*

## Backtesting

To re-run the statistical validation or update hit rates, use the provided backtest script. This script compares ES big trades against direct ES price action (ES=F) over a specified lookback period (default 180 days).

```bash
python3 /Users/zhijiebian/.gemini/skills/order-flow-analysis/scripts/backtest_big_trades.py <lookback_days>
```

### Diagnostic Drill-down

To inspect every historical trade for a specific period and volume bucket:
```bash
python3 /Users/zhijiebian/.gemini/skills/order-flow-analysis/scripts/analyze_bucket_details.py <period> <vol_bucket>
```
Example: `python3 .../analyze_bucket_details.py PM 500-1000`
Example: `python3 .../analyze_bucket_details.py PM 500-1000`
