# Institutional Options Backtest Report: TSLA (5-Week Review)

## Original Instruction
"@stock-analysis backtest TSLA, please find valid options data going back to at most 5 weeks"

***

## Overall Backtest Summary: Institutional Floor Activity
- **Lookback Window**: 35 Days (Mar 11 - Apr 15, 2026)
- **High-Confidence Options Captured**: 12 Trades
- **Dominant Activation Date**: **April 9, 2026** (TSLA Bottom)
- **Overall Verdict**: The 5-week tape is characterized by heavy multi-leg "Floor" (FLR) activity. Institutional conviction was highest on April 9th, where individual leg premiums exceeded **$120 Million**, marking the precise inflection point for the recent $50+ rally.

***

## Analytical Rationale
The 35-day options review confirms that the "High Confidence" floor for TSLA in early 2026 is driven primarily by complex multi-leg institutional Positioning rather than single-leg directional bets (D.AUTO).
1. **The April 9 Pivot**: While price was hitting its $338 low, the options tape saw extreme positioning with a 4-leg floor trade featuring a single leg premium of **$123.6M**. This massive size signaled institutional bottom-fishing or a major hedge-cover.
2. **Post-Bottom Follow-through**: From April 10th to April 14th, institutions continued to layer in multi-leg trades with individual leg premiums consistently between **$25M and $40M**, supporting the move toward $393.
3. **Absence of D.AUTO**: In this 5-week window, no trustable directional bets (D.AUTO) crossed the $5M conviction floor, indicating that institutions preferred structured multi-leg strategies over vanilla directional calls/puts.

***

## Signal Audit Trail
Detailed list of high-confidence options 고려된 in this backtest (Medium+ Size: Biggest Leg >= $25M).

| Date | Type | Code | Volume (Total) | Max Leg Premium | Details |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-04-14 | Options Flow | FLR | $58.13M | **$40.42M** | 8 legs |
| 2026-04-14 | Options Flow | FLR | $40.52M | **$25.62M** | 7 legs |
| 2026-04-13 | Options Flow | M2M_FLR | $55.61M | **$33.87M** | 8 legs |
| 2026-04-13 | Options Flow | FLR | $47.17M | **$28.54M** | 7 legs |
| 2026-04-10 | Options Flow | M2M_FLR | $52.21M | **$33.02M** | 5 legs |
| 2026-04-09 | Options Flow | FLR | $161.57M | **$123.60M** | 4 legs |
| 2026-04-09 | Options Flow | FLR | $66.64M | **$50.49M** | 5 legs |

***
**Output Persistence**:
- Markdown: `Stock_Analysis_Query-TSLA-35d_2026-04-15_23-25-46.md`
- HTML: `Stock_Analysis_Query-TSLA-35d_2026-04-15_23-25-46.html`
