# Implementation Plan - Order Flow Signal Strength Integration

Add a quantitative signal strength indicator (`Low`, `Medium`, `High`) to the Order Flow Real-time Signals (`OrderFlowSignal`) for both Bullish and Bearish directions. This will distinguish between minor intraday pullbacks and major high-momentum reversals by combining price movements with order flow validation.

## User Review Required

### Revised Signal Strength Rules (Price + Order Flow Validation)
To address the critique of purely price-move based rules, we have integrated order flow confirmations (delta direction, cumulative delta drawdowns, depth imbalance, and preceding absorption signatures) to validate the price action:

- **Bearish Signal Strength**:
  - **High**: 
    - **Massive Selling Delta**: Cumulative delta in the last 15 minutes $\le -8,000$ OR any single 5-minute delta $\le -6,000$.
    - **Sharp Price Drop + OF Validation**: A single 5-minute price drop in the recent window is $\le -10.0$ points **AND** is accompanied by negative delta ($delta < 0$) or negative depth imbalance, or immediately follows a passive selling absorption block (e.g. `dp_label == "买盘被吸收"` in the last 15 mins).
    - **Major Reversal from High + OF Confirmation**: Cumulative price drop from RTH high is $\ge 15.0$ points **AND** RTH cumulative delta has declined from its session peak by $\ge 10,000$ contracts OR the recent 30-minute delta is negative.
    - **Decline Consistency**: Recent 30m price change is $\le -15.0$ points **AND** recent 30m delta is negative ($recent\_30m\_delta < 0$).
  - **Medium**:
    - Cumulative delta in the last 15 minutes $\le -3,000$ OR any single 5-minute delta $\le -2,500$.
    - OR a single 5-minute price drop is $\le -5.0$ points **AND** accompanied by negative delta ($delta < 0$).
    - OR the cumulative price drop from RTH high is $\ge 8.0$ points **AND** recent 30-minute delta is negative.
    - OR the recent 30m price change is $\le -6.0$ points **AND** recent 30m delta is negative.
    - OR it is a confirmed `Supply Trap` (买盘竭尽).
  - **Low**: Otherwise.

- **Bullish Signal Strength**:
  - **High**: 
    - **Massive Buying Delta**: Cumulative delta in the last 15 minutes $\ge 8,000$ OR any single 5-minute delta $\ge 6,000$.
    - **Sharp Price Rise + OF Validation**: A single 5-minute price rise in the recent window is $\ge 10.0$ points **AND** is accompanied by positive delta ($delta > 0$) or positive depth imbalance, or immediately follows a passive buying absorption block (e.g. `dp_label == "卖盘被吸收"` in the last 15 mins).
    - **Major Bounce from Low + OF Confirmation**: Cumulative price rise from RTH low is $\ge 15.0$ points **AND** RTH cumulative delta has increased from its session trough by $\ge 10,000$ contracts OR the recent 30-minute delta is positive.
    - **Rally Consistency**: Recent 30m price change is $\ge 15.0$ points **AND** recent 30m delta is positive ($recent\_30m\_delta > 0$).
  - **Medium**:
    - Cumulative delta in the last 15 minutes $\ge 3,000$ OR any single 5-minute delta $\ge 2,500$.
    - OR a single 5-minute price rise is $\ge 5.0$ points **AND** accompanied by positive delta ($delta > 0$).
    - OR the cumulative price rise from RTH low is $\ge 8.0$ points **AND** recent 30-minute delta is positive.
    - OR the recent 30m price change is $\ge 6.0$ points **AND** recent 30m delta is positive.
    - OR it is a confirmed `Demand Trap` (卖盘竭尽).
  - **Low**: Otherwise.

---

## Proposed Changes

### Database & Models

#### [MODIFY] [models.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py)
- Add the `signal_strength` column to the `OrderFlowSignal` class:
  ```python
  signal_strength = db.Column(db.String(16), nullable=True)
  ```

#### [NEW] [alter_order_flow_signals_strength.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/scratch/alter_order_flow_signals_strength.py)
- Create a scratch DDL migration script:
  ```sql
  ALTER TABLE order_flow_signals ADD COLUMN signal_strength VARCHAR(16) DEFAULT NULL;
  ```

---

### Signal Analysis Scripts

#### [MODIFY] [ai_tape_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/ai_tape_analyst.py)
- Implement `calculate_signal_strength(direction, verdict_text, micro_intervals, micro_stats, rth_stats)` based on the updated quantitative rules.
- To detect cumulative delta peak drawdowns, calculate the historical session peak/trough delta from `rth_delta_progression` or the raw intervals.
- Update `_save_signal_to_db()` to compute and assign `sig.signal_strength`.

#### [MODIFY] [backfill_order_flow_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/backfill_order_flow_signals.py)
- Integrate the `calculate_signal_strength` logic into the backfilling loop.
- Save the calculated strength to `sig.signal_strength` during instantiation and updates.

---

### Backend API Route

#### [MODIFY] [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py)
- Update `/data/order_flow_signals` to serialize `'signal_strength': sig.signal_strength or 'Low'`.
- Support strength filtering query parameter (`strength`) in `/data/order_flow_signals`.
- Update `/data/order_flow_signal_decision` to return the new `'signal_strength': sig.signal_strength or 'Low'` field in the JSON payload.

---

### Frontend UI Integration

#### [MODIFY] [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html)
- Add a dropdown filter for **Strength** (All / High / Medium / Low).
- Add the `<th style="width: 80px;">Strength</th>` column header to the `#signalsTable`.
- Define badge styles for strength levels in the `<style>` block:
  - `badge-strength-high`: Red background/border with bold red text.
  - `badge-strength-medium`: Amber background/border with bold amber text.
  - `badge-strength-low`: Slate gray background/border with gray text.

#### [MODIFY] [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js)
- Insert the `signal_strength` column renderer into the DataTable columns list (placed after Direction).
- Include `strength` in the Ajax request parameters object.
- Render the strength badge in the expanded details panel (`format` function) within the **Recent 30-Min Metrics** card.
- Render the strength badge in the real-time panel next to the direction badge.

---

## Verification Plan

### Automated DDL Migration
- Execute `python3 /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/scratch/alter_order_flow_signals_strength.py` to perform the column add operation.

### Signal Generation & Backfill Testing
- Run `python3 /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/backfill_order_flow_signals.py` to backfill all historical signals and verify they compute the correct signal strength.
- Run `python3 /Users/zhijiebian/.gemini/antigravity-ide/brain/f2162aab-702a-4253-8a00-9fbbb8a55d40/scratch/query_reversal_signals.py` (updated to query signal_strength) to verify that the target days are correctly cataloged as **High** strength.

### Manual UI Verification
- The user will start the server and load the web UI at `http://127.0.0.1:5005/bbt_signals` to verify columns, filters, and rendering cards (we will not launch the browser automatically).
