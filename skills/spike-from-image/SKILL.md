---
name: spike-from-image
description: Read a MotiveWave screenshot containing a price spike, extract details (ticker, date, time, target price, spot price, and volume), and insert them into the DB tables (spike_mw and spike_mw_agg).
---

# Spike from Image

Use this skill when the user provides a MotiveWave screenshot of a price spike and asks to add it to the database.

## Workflow

### 1. Analyze the Screenshot
Identify the following information from the image:
1. **Ticker**: Look at the top-left of the chart (e.g., `SPCX - 5 min` -> Ticker is `SPCX`).
2. **Date & Time**: Look at the cursor tooltip box displayed on the chart (e.g., `Time: Jul-17 14:20`).
   - Standardize date to `YYYY-MM-DD` (use the current active year, e.g., `2026-07-17`).
   - Standardize time to `HH:MM:SS` (e.g., `14:20:00`).
3. **Target Price**: Look at the `High` field in the cursor tooltip box (e.g., `High: 163.42` -> Price is `163.42`).
4. **Spot Price**: Look at the `Close` or `Open` field in the cursor tooltip box to determine the normal trading price at that time (e.g., `Close: 124.06` -> Spot Price is `124.06`).
5. **Volume**: Look at the DOM panel on the right side of the screenshot. Find the row representing the spike price (or nearest price level) and read the volume number in the Ask/Bid size column (e.g., if there is a number `4` in the row for price `183` or `163`, the volume is `4`).
6. **Trading Hour**: Determine the trading session from the time:
   - Regular Trading Hours (`RTH`): `09:30:00` to `16:00:00` EST (`06:30:00` to `13:00:00` PDT).
   - After Hours (`AH`): `16:00:00` to `20:00:00` EST (`13:00:00` to `17:00:00` PDT).
   - Pre-Market (`PM`): `04:00:00` to `09:30:00` EST (`01:00:00` to `06:30:00` PDT).

### 2. Insert into the Database
Run the manual insertion script with the extracted parameters using python 3.11:
```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/spike_db/insert_spike_manual.py \
  --ticker <TICKER> \
  --date <DATE> \
  --time <TIME> \
  --price <PRICE> \
  --volume <VOLUME> \
  --spot-price <SPOT_PRICE> \
  --trading-hour <RTH|AH|PM>
```

### 3. Report Results
Confirm to the user that the spike has been parsed and successfully inserted into both `spike_mw` and `spike_mw_agg` tables.
