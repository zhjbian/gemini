---
name: trading-report
description: Generates a daily or weekly report for a given ticker or the general stock market.
---

# Trading Report Skill

This skill allows you to generate a detailed daily or weekly trading report for a specific ticker symbol or for the general stock market.

## Capabilities

When the user requests a trading report, follow these systematic steps:

### 1. Identify Requirements
- **Target**: Determine if the report is for a specific ticker (e.g., AAPL) or the general market (e.g., SPY, QQQ).
- **Timeframe**: Determine if it is a daily or weekly report.
- **Context**: Check if the user has specific areas of interest (e.g., option flows, technical levels).

### 2. Formulate Data Gathering Plan
Leverage the user's existing `BBTrading` workspace or external libraries appropriately.
- **Price Action & Volume**: Use `yfinance` or the user's database to fetch recent Open, High, Low, Close, and Volume data.
- **Technical Analysis**: Identify moving averages, RSI, support/resistance levels. 
- **BBT Data**: Use APIs in `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/db_query.py` or create your own queries to fetch Options Flows, Order Flows, Spikes, and Dark Pool data.

### 3. Analyze the Data
- Summarize the percentage change, volume, moving averages, and RSI.
- Analyze the notable big options flows and provide a bullish/bearish prediction based on total premium.
- Analyze the big order flow trades and provide a bullish/bearish prediction.
- Evaluate recent Spikes and Dark Pool prints.
- Synthesize an overall final prediction combining technicals and BBT flow data.

**Data Cleaning Rules:**
- **Time Columns**: When fetching `trade_time` or `time` from the DB, strip out the `0 days ` prefix string if it appears (e.g., `0 days 13:02` -> `13:02`).
- **Dark Pool Notional Value**: The `notional_value` database column is often already stored in millions (e.g., `62.33`). If populated, use it directly as `$X.XM`. If null or `0.0`, manually calculate it as `(Price * Size) / 1,000,000`. Ensure values output to the table are scaled to millions (`$XM`).

### 4. Structure the Report
Always present the information in a professional, well-formatted Markdown structure exactly following the sections below:

**Template:**
```markdown
# 📈 Trading Report: [Ticker/Market] ([Daily/Weekly])
**Date**: [Current Date] (Lookback: [Start Date] to [End Date])

## 1. General Technical Analysis
- **Price & Metrics**: Close $..., ...% change, Volume ... (X% of 3mo avg)
- **Moving Averages**: SMA20: $... | SMA50: $... | SMA200: $...
- **RSI (14)**: ...
- **Key Levels (Weekly)**: High $... / Low $...

## 2. BBT Analysis
### 2.1 Options Flows Analysis
**Notable Big Flows**:
| Date | Call/Put | Dir | Code | Premium |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

**Prediction**: [Overall Bullish or Bearish prediction based on Options]

### 2.2 Order Flows Analysis
**Big Order Flow Trades**:
| Date & Time | Side | Type | Volume | Price | Value |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

**Prediction**: [Overall Bullish or Bearish prediction based on Orders]

### 2.3 Spikes Analysis
**Recent Spikes**:
| Date & Time | Dir | Target Price | Spot Price | Volume |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

### 2.4 Dark Pool
**Prints**:
| Date & Time | Type | Price | Size | Notional Value |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

## 3. Overall Analysis
**Synthesis & Final Outlook**:
- Technicals lean **[Bullish/Bearish]** (Price vs SMA, RSI)
- BBT Flow Data (Options & Orders) leans **[Bullish/Bearish]**.
- **Conclusion**: [Combine technicals + BBT data into one final synthesized outlook]
```

### 5. Delivery
Present the requested report to the user. Offer to save it as a markdown file within their workspace or as an artifact for future reference.