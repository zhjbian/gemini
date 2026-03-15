---
name: stock-analysis
description: Generates a daily or weekly report for a given ticker or the general stock market.
---

# Stock Analysis

This skill allows you to generate a detailed daily or weekly trading report for a specific ticker symbol or for the general stock market.

## Capabilities

When the user requests a trading report, follow these systematic steps:

### 1. Identify Requirements
- **Target**: Determine if the report is for a specific ticker (e.g., AAPL) or the general market (e.g., SPY, QQQ).
- **Timeframe**: Determine if it is a daily or weekly report.
- **Context**: Check if the user has specific areas of interest (e.g., option flows, technical levels).

### 2. Formulate Data Gathering Plan
Use the following Python scripts located in `/Users/zhijiebian/.gemini/skills/stock-analysis/scripts/` to fetch data. Ensure you run them with the local Python environment at `/usr/local/bin/python3`.
- **Price Action, Volume & Technicals**: Run `/usr/local/bin/python3 /Users/zhijiebian/.gemini/skills/stock-analysis/scripts/get_tech_data.py <ticker> <date YYYY-MM-DD>`
- **BBT Data (Options, Orders, Spikes, Dark Pool)**: Run `/usr/local/bin/python3 /Users/zhijiebian/.gemini/skills/stock-analysis/scripts/get_bbt_data.py <ticker> <date YYYY-MM-DD>`

### 3. Analyze the Data
- Summarize the percentage change, volume, moving averages, and RSI into tables.
- **MA Analysis**: Calculate the percentage difference between the current price and each MA. State what it means (e.g., Price > MA indicates Bullish short-term trend).
- **RSI Analysis**: Evaluate RSI status (e.g., < 30 is Oversold, > 70 is Overbought, otherwise Neutral).
- Analyze the notable big options flows and provide a bullish/bearish prediction based on total premium.
- Analyze the big order flow trades and provide a bullish/bearish prediction.
- Evaluate recent Spikes and Dark Pool prints.
- Synthesize an overall final prediction combining technicals and BBT flow data.

**Data Cleaning Rules:**
- **Time Columns**: When fetching `trade_time` or `time` from the DB, strip out the `0 days ` prefix string if it appears (e.g., `0 days 13:02` -> `13:02`).
- **Dark Pool Notional Value**: The `notional_value` database column is often already stored in millions (e.g., `62.33`). If populated, use it directly as `$X.XM`. If null or `0.0`, manually calculate it as `(Price * Size) / 1,000,000`. Ensure values output to the table are scaled to millions (`$XM`).

### 4. Structure the Report
#### Report File
Generate report file under /Users/zhijiebian/.gemini/cli-workspace
File name: Stock_Analysis-<ticker>-<time_range>.md
E.g., Stock_Analysis-TSLA-2026-03-13.md, Stock_Analysis-TSLA-2026-03-09_2026-03-13.md

### Report Template
Always present the information in a professional, well-formatted Markdown structure exactly following the sections below:
```markdown
# 📈 Stack Analysis Report: [Ticker/Market] ([Daily/Weekly])
**Date**: [Current Date] (Lookback: [Start Date] to [End Date])

## 1. General Technical Analysis
**Key Metrics**:
| Metric | Value | Context/Change |
|---|---|---|
| **Close Price** | $... | ...% |
| **Volume** | ...M | ...% of 3mo avg |
| **RSI (14)** | ... | [Overbought (>70) / Oversold (<30) / Neutral] |
| **Weekly Range**| High $... | Low $... |

**Moving Averages Overview**:
| MA | Price | Distance from Close | Trend Signal | Note |
|---|---|---|---|---|
| **SMA20** | $... | ...% | [Bullish (Price > MA) / Bearish (Price < MA)] | Short-term trend |
| **SMA50** | $... | ...% | [Bullish / Bearish] | Medium-term trend |
| **SMA200** | $... | ...% | [Bullish / Bearish] | Long-term trend, very bearish if lose |

## 2. BBT Analysis
### 2.1 Options Flows Analysis
**Notable Big Flows**:
| Date & Time | Contract | Call/Put | Dir | Premium |
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