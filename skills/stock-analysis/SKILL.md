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

## Structure the Report
### Report File
1. Generate markdown report file under /Users/zhijiebian/.gemini/cli-workspace
File name: Stock_Analysis-<ticker>-<time_range>.md
E.g., Stock_Analysis-TSLA-2026-03-13.md, Stock_Analysis-TSLA-2026-03-09_2026-03-13.md

2. Generate html report file under /Users/zhijiebian/.gemini/cli-workspace
File name: Stock_Analysis-<ticker>-<time_range>.html
E.g., Stock_Analysis-TSLA-2026-03-13.html, Stock_Analysis-TSLA-2026-03-09_2026-03-13.html

*Note*: To convert the markdown text to an HTML string and properly apply inline colors for Gmail, use the comprehensive Python script provided below in the "Generate HTML & Send Email" section.

### Report Template
Always present the information in a professional, well-formatted Markdown structure exactly following the sections below. **CRITICAL: You MUST include a blank line immediately before every markdown table, otherwise the HTML parser will fail to render the table correctly.**
```markdown
# 📈 Stock Analysis: [Ticker/Market] - [date or date range]
**Date**: [Current Date] (Lookback: [Start Date] to [End Date])

## 1. 整体分析

<table>
<tr>
<td><b>技术分析</b></td>
<td><b>看多 / 看空</b></td>
<td>&lt;高度总结的原因 based on Price vs SMA, RSI, EMA&gt;</td>
</tr>
<tr>
<td><b>BBT分析</b></td>
<td><b>看多 / 看空</b></td>
<td>&lt;高度总结的原因 based on Options flows, Orders flows, Spikes, Dark Pool&gt;</td>
</tr>
</table>

**结论**: [Combine technicals + BBT data into one final synthesized outlook]

## 2. Overall Analysis

<table>
<tr>
<td><b>Technicals</b></td>
<td><b>Bullish / Bearish</b></td>
<td>&lt;高度总结的原因 based on Price vs SMA, RSI, EMA&gt;</td>
</tr>
<tr>
<td><b>BBT</b></td>
<td><b>Bullish / Bearish</b></td>
<td>&lt;高度总结的原因 based on Options flows, Orders flows, Spikes, Dark Pool&gt;</td>
</tr>
</table>

**Conclusion**: [Combine technicals + BBT data into one final synthesized outlook]

## 3. General Technical Analysis
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

## 3. BBT Analysis
### 2.1 Options Flows
**Notable Big Flows**:

| Date & Time | Contract | Call/Put | Dir | Premium |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

**Prediction**: [Overall Bullish or Bearish prediction based on Options]

### 2.2 Order Flows
**Big Order Flow Trades**:

| Date & Time | Side | Type | Volume | Price | Value |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

**Prediction**: [Overall Bullish or Bearish prediction based on Orders]

### 2.3 Spikes
**Recent Spikes**:

| Date & Time | Dir | Target Price | Spot Price | Volume | Prev Close |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

### 2.4 Dark Pool
**Prints**:

| Date & Time | Type | Price | Size | Notional Value |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

```

## Generate HTML & Send Email
After generating the markdown report, create and run the following python script to reliably convert the markdown to HTML, apply inline CSS for table formatting and row colors (crucial for Gmail), and send the email:

```python
import sys
import re
import markdown
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")
from py_lib.sms import BBSms

# Insert your actual ticker and time range
ticker = "<ticker>"
time_range = "<time_range>"

md_path = f"/Users/zhijiebian/.gemini/cli-workspace/Stock_Analysis-{ticker}-{time_range}.md"
html_path = f"/Users/zhijiebian/.gemini/cli-workspace/Stock_Analysis-{ticker}-{time_range}.html"

with open(md_path, "r", encoding="utf-8") as f:
    md_content = f.read()

# Convert markdown to html with tables support
html_content = markdown.markdown(md_content, extensions=['tables'])

# Inject basic CSS borders directly into HTML tags for Gmail compatibility
html_content = html_content.replace('<table>', '<table style="border-collapse: collapse; width: 100%; margin-bottom: 20px; font-family: sans-serif;">')
html_content = html_content.replace('<th>', '<th style="border: 1px solid #cccccc; padding: 8px; text-align: left; background-color: #f2f2f2;">')
html_content = html_content.replace('<td>', '<td style="border: 1px solid #cccccc; padding: 8px; text-align: left;">')

# Regex to safely find all <tr> elements and colorize based on content
def colorize_row(match):
    row_html = match.group(0)
    # Check for sentiment keywords (including Chinese)
    if re.search(r'\b(Bull|Bullish|Buy|UP)\b|看多', row_html, re.IGNORECASE):
        return row_html.replace('<tr>', '<tr style="background-color: #e8f5e9;">')
    elif re.search(r'\b(Bear|Bearish|Sell|DN)\b|看空', row_html, re.IGNORECASE):
        return row_html.replace('<tr>', '<tr style="background-color: #ffebee;">')
    return row_html

# Apply coloring to each table row
html_content = re.sub(r'(?si)<tr>.*?</tr>', colorize_row, html_content)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

BBSms.send_to_gmail_html_from_ai(html_content, title=f"Stock Analysis Daily: {ticker}")
```
Run this script to send the email and then notify the user that it has been completed.
