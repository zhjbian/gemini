# Implementation Plan - Futures Rollover Trade Side Direction Correction

This document outlines the proposed changes to correct trade side detection (BID vs ASK) during quarterly futures rollover weeks. During these 4 to 5 trading days, back-adjusted price differences cause the MotiveWave Exporter to report incorrect trade directions (e.g., marking almost all trades as ASK). We will implement a rollover week detection algorithm and apply the Lee-Ready algorithm (Tick Test) across both the Java Exporter and python analysis modules.

## User Review Required

> [!IMPORTANT]
> The changes affect the core delta calculation logic in both the Java-based MotiveWave Exporter and the Python analytical pipelines. Legacy and newly-exported data for rollover periods will both be automatically corrected.

## Open Questions

There are no open questions. The algorithm is designed based on standard futures delivery schedules and standard Tick Test heuristics.

## Proposed Changes

### Java Exporter Component

#### [MODIFY] [StudyOrderFlowDataExporter.java](file:///Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java)
* Add helper method `isFuturesRolloverWeek(long timeMs)` to detect if the target timestamp falls within the Monday-to-Friday window of the 3rd Friday of March, June, September, or December.
* Add tracking state for last price and side in both real-time `onTick` export and binary backfill `parseTickDataFile` modes.
* When inside the rollover week, override the default tick side classification using the Tick Test logic:
  - If current price > previous price: ASK
  - If current price < previous price: BID
  - If current price == previous price: keep previous side
  - If no previous price exists: fall back to the default side from MotiveWave

---

### Python Data Analysis & Feature Generation

#### [MODIFY] [order_flow_feature_generator.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_feature_generator.py)
* Add method `get_date_from_timestamp(ts, tz_name="America/Los_Angeles")` to retrieve the trading date from epoch milliseconds.
* Add method `is_futures_rollover_week(dt)` to determine whether a given date falls within a rollover week.
* Modify `preprocess_data(dom_df, tick_df, trade_date=None)` to detect the trading date from tick data and check if it is a rollover week.
* If a rollover week is detected, apply a vectorized pandas implementation of the Lee-Ready Tick Test:
  - `price_diff = merged['Price'].diff()`
  - `change_dir = np.sign(price_diff).replace(0, np.nan).ffill()`
  - Any initial NaN values are backfilled using the original `Side` column values.
  - Set `tick_delta = change_dir * Size` instead of using the raw `Side` column.

#### [MODIFY] [order_flow_sentinel.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_sentinel.py)
* Correct the tick line parsing check from `if len(parts) != 4: continue` to `if len(parts) < 4: continue` to support 5-column CSV layouts (e.g. including Contract).
* Add `is_futures_rollover_week(dt)` helper function.
* Check if the target check date is a rollover week, and if so, correct tick directions via the Tick Test during real-time sentinel processing.

#### [MODIFY] [mw_tick_parser_backfill_raw.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/mw_tick_parser_backfill_raw.py)
* Add `is_futures_rollover_week(dt)` helper function.
* Apply Tick Test trade direction correction when parsing binary `.tick_data` files if they match a rollover week date.

## Verification Plan

### Automated Tests
* Run a test script to verify that `is_futures_rollover_week` correctly identifies dates like `2026-06-15` through `2026-06-19` as rollover week, and dates outside that window as normal weeks.
* Run `order_flow_feature_generator.py` for `2026-06-15` and check the calculated Delta in the resulting CSV/HDF5 file. Verify that the Delta in the `12:55-13:00` window is corrected to approximately -2900 (instead of +13480).
* Run `order_flow_sentinel.py` for `2026-06-15` with `--dry-run` to verify that it correctly parses non-zero tick counts and applies correct direction logic.

### Manual Verification
* Re-run feature generation and database backfilling for ES on `2026-06-15` and verify that the progression logs in database table `whale_trade_case_studies` show the correct delta numbers.
