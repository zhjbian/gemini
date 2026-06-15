# Walkthrough - ES Daily Pivot Point Identification Module

This walkthrough documents the successful design, implementation, and verification of the ES E-mini futures Daily Pivot Point Identification module.

## Changes Made

### 1. Database Schema
* **File**: [schema_pivots.sql](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/schema_pivots.sql) [NEW]
* **Action**: Created and executed the database migration script. Created the `order_flow_pivots` table in the `bb_trade` database.
* **Fields**:
  * `id` (int, PK, auto_increment)
  * `pivot_date` (date, indexed)
  * `ticker` (varchar(16), indexed)
  * `pivot_price` (decimal(10, 2))
  * `strength_score` (int, 0-100)
  * `pivot_type` (enum('Bullish_Reclaim', 'Bearish_Breakdown', 'Balanced_HVN'))
  * `metrics_breakdown` (json)
  * `created_at` (datetime)
  * `last_modified` (datetime)

### 2. Core Python Calculation Engine
* **File**: [es_pivot_identifier.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/es_pivot_identifier.py) [NEW]
* **Action**: Implemented the core algorithm containing:
  * **Look-back Window**: Parameterized via `--lookback` (default: 5 days).
  * **Hold Margin**: Parameterized via `--margin` (default: 5.0 ES points).
  * **ES Contract Roll Jumping Correction**: Automatically detects quarterly roll price jumps by comparing the day-to-day changes in ES prices against SPY stock price changes (to isolate true market movement), applying a cumulative basis shift to older contract data.
  * **Classification & Scoring**: Density-based clustering of Crossing Volume Profile (CVP), Passive Iceberg Levels (PIL), Delta Flip Line (DFL), and Aggressive Sweep Jump (ASJ) to yield a normalized strength score (0-100%) and classify pivot types.
  * **Persistence & CLI**: Saves calculated pivots to the database and supports running for any date with console reports.

### 3. Backend Routing & Models
* **File**: [models.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py) [MODIFY]
  * Appended the SQLAlchemy model `OrderFlowPivot` mapping the MySQL `order_flow_pivots` table.
* **File**: [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py) [MODIFY]
  * Created the `/api/order_flow_pivots` route. It queries calculated pivot points from the database, or runs `ESPivotIdentifier` on the fly if no records exist (or if `recalculate=true` is requested), and returns the JSON payload.

### 4. Frontend Integration
* **File**: [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html) [MODIFY]
  * Inserted the "获取Pivot" button inside the Action group.
  * Added the `pivotPointsPanel` card container to hold the visual pivot results.
* **File**: [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js) [MODIFY]
  * Implemented the `fetchPivotPoints()` function. When the user clicks the "获取Pivot" button, it invokes the `/api/order_flow_pivots` API, parses the JSON payload, and renders premium visual cards detailing each level, its strength score (with a progress bar), and its metrics breakdown.

---

## Verification Results

We verified the core Python engine on the dates matching the contract transition week:

### 1. Verification for June 9, 2026
```bash
python3 PyTools/order_flow_analysis/es_pivot_identifier.py --date "2026-06-09" --lookback 5 --margin 5.0
```
* **Output**:
  * Price range in lookback window: 7261 to 7600
  * Level: **7571.00** | Type: Balanced_HVN | Score: 76%
  * Level: **7303.00** | Type: Bullish_Reclaim | Score: 68%
  * Level: **7318.00** | Type: Bullish_Reclaim | Score: 56%

### 2. Verification for June 11, 2026 (Adam Set Post Signal Date)
```bash
python3 PyTools/order_flow_analysis/es_pivot_identifier.py --date "2026-06-11" --lookback 5 --margin 5.0
```
* **Output**:
  * Level: **7303.00** | Type: Bullish_Reclaim | Score: 95%
  * Level: **7319.00** | Type: Bullish_Reclaim | Score: 76%
  * Level: **7370.00** | Type: Balanced_HVN | Score: 60%

### 3. Verification for June 12, 2026
```bash
python3 PyTools/order_flow_analysis/es_pivot_identifier.py --date "2026-06-12" --lookback 5 --margin 5.0
```
* **Output**:
  * Level: **7277.00** | Type: Bullish_Reclaim | Score: 96%
  * Level: **7293.00** | Type: Bullish_Reclaim | Score: 77%
  * Level: **7344.00** | Type: Balanced_HVN | Score: 61% (Very close to the key 7340 pivot level).
