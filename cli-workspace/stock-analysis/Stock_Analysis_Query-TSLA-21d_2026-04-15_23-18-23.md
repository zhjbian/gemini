# Institutional Signal Backtest Report: TSLA (3-Week Bidirectional Analysis)

## Original Instruction
"@stock-analysys backtest TSLA, find both bullish and bearish signals from last 3 weeks to evaluate whether they have forecasted the big rally from 2026-04-09, 338 to 393"

***

## Overall Backtest Summary: The Bidirectional "U-Turn"
- **Bottom Resolution Accuracy**: **100%** (Bearish magnets at $345 resolved at $338 bottom)
- **Rally Forecast Accuracy**: **100%** (Bullish magnets at $392 resolved at $393 peak)
- **Current Status**: **Active Downside Pull** (New spikes at 347.7x printed *during* the rally)

***

## Analytical Rationale
The institutional flow over the last 21 days executed a perfect "Pinball" maneuver, resolving extreme targets on both sides of the market.
1. **The Downside Magnet Cluster (Mar 26 - Apr 2)**: Institutions established a primary downside objective at **345.10 - 347.80**. Price gravitated steadily toward this zone, finally hitting the exhaustion point at **$338** on April 9th.
2. **The Bullish Transition (Apr 7 - Apr 9)**: While price was still falling toward the 345 targets, institutions began aggressively layering in **Bullish "UP" magnets** at **391 - 392**. The largest print (Vol 120) occurred on the morning of Apr 9, signaling that the bearish objective was complete and the $392 objective was next.
3. **The Current Pivot (Apr 13-15)**: During the ascent to $393, institutions printed a **new massive bearish cluster** ($347.7x). This indicates that while the rally to $393 was forecasted and resolved, institutions are already positioning for a potential return to the low-350s.

***

## Signal Audit Trail
Comprehensive list of high-confidence signals considered in this backtest (Backtest Mode).

| Date | Type | Direction | Volume | Target Price | Hit Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-04-14 | Spike (PM) | **Bullish (UP)** | 21 | **399.83** | **ACTIVE** |
| 2026-04-13 | Spike (PM) | **Bearish (DN)** | 825 (Agg) | **347.7x** | **ACTIVE** |
| 2026-04-09 | Spike (PM) | **Bullish (UP)** | 120 | **392.50** | ✅ **HIT** (Apr 15) |
| 2026-04-08 | Spike (RTH) | **Bullish (UP)** | 95 | **392.05** | ✅ **HIT** (Apr 15) |
| 2026-04-07 | Spike (PM) | **Bullish (UP)** | 44 (Agg) | **391.3x** | ✅ **HIT** (Apr 15) |
| 2026-04-02 | Spike (PM) | **Bearish (DN)** | 63 | **347.80** | ✅ **HIT** (Apr 09) |
| 2026-03-27 | Spike (PM) | **Bearish (DN)** | 105 | **345.10** | ✅ **HIT** (Apr 09) |
| 2026-03-26 | Spike (PM) | **Bearish (DN)** | 68 | **345.22** | ✅ **HIT** (Apr 09) |

***
**Output Persistence**:
- Markdown: `Stock_Analysis_Query-TSLA-21d_2026-04-15_23-18-23.md`
- HTML: `Stock_Analysis_Query-TSLA-21d_2026-04-15_23-18-23.html`
