# Implementation Plan - ES Daily Pivot Point Identification Module

This document outlines the finalized implementation details for the ES E-mini futures Daily Pivot Point Identification module.

## Final Decisions & Dynamic Features
* **Look-back Window**: Made fully parameterized, defaulting to 5 trading days. The dates are dynamically resolved using trading days available in the database to accommodate weekends/holidays.
* **SR Flip Margin**: Adjusted to a parameterized 5.0 ES points margin threshold.
* **ES Contract Roll Correction**: Implemented an automated roll-jump correction. By querying both ES and SPY historical daily levels, the algorithm detects points jumps during rollover months and adjusts older contract terms to match the target date contract terms.

## Components Implemented

### 1. Database Schema
* **File**: [schema_pivots.sql](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/schema_pivots.sql)
* Created table `order_flow_pivots` with fields for `pivot_date`, `ticker`, `pivot_price`, `strength_score`, `pivot_type`, and `metrics_breakdown` (JSON).

### 2. Core Pivot Points Engine
* **File**: [es_pivot_identifier.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/es_pivot_identifier.py)
* Implemented the calculation logic aggregating CVP, PIL, DFL, and ASJ. Normalizes and scores candidate levels, selecting the top local maxima pivots. Includes full CLI options.

### 3. Backend Integration
* **File**: [models.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py)
  * Mapped table to SQLAlchemy model `OrderFlowPivot`.
* **File**: [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py)
  * Exposed `/api/order_flow_pivots` endpoint.

### 4. Frontend Integration
* **File**: [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html)
  * Integrated the "获取Pivot" button and the output cards panel.
* **File**: [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js)
  * Added AJAX request handling and interactive HTML visualization of results.
