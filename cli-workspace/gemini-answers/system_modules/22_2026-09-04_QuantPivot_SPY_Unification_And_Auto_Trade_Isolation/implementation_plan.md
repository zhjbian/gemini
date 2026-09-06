# Implementation Plan: Fix QuantPivot SPY Price Unification and Option Seller Trigger Bugs

Fix all root causes that prevented **Scenario 2 (Non-Trend Range-Bound QuantPivot Boundary Reversal)** and Conditional Orders from triggering during SPY's drop to QuantPivot L1. Unify all QuantPivot calculations, price comparisons, and trigger sentinels strictly to **SPY**.

## User Review Required

> [!IMPORTANT]
> - **Unified Symbol Rule**: For QuantPivot L1, L2, H1, H2, the calculation and price check are now strictly anchored to **SPY** across all modules. If any module passes an SPX or ES price (> 2000), an automated defensive normalization (`price / 10.0`) is enforced.
> - **Position Limit Isolation**: MANUAL trades from the UI scan will no longer block AUTO trades or conditional orders. The 2-position ceiling applies strictly to active `trade_mode == 'AUTO'` trades.

---

## Proposed Changes

### Component 1: QuantPivot Calculator Helper

#### [MODIFY] [quant_pivot.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/pivots/quant_pivot.py)
- Add `QuantPivotCalculator.get_spy_current_price()`:
  - Primary source: Real-time SPY quote mark/last via `BBTOS.get_option_chain_for_symbol('SPY', strike_count=2)`.
  - Fallback 1: Database latest SPX spot normalized to SPY (`spx_spot / 10.0`).
  - Fallback 2: Defensive auto-scaling if caller supplies ES/SPX scale.

---

### Component 2: Sentinel & Comprehensive Signals Orchestrators

#### [MODIFY] [order_flow_sentinel.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_sentinel.py)
- **Line 571**: Change `not mgr.active_trades` to `not mgr.has_active_auto_trades()`, preventing existing manual UI positions from skipping the 5-minute routine evaluation.
- **Line 626~644**: Replace buggy `curr_p = float(rth_high_val)` with `spy_price = QuantPivotCalculator.get_spy_current_price()`. Pass `spy_price` into `QuantPivotCalculator.get_quant_pivot('SPY', current_price=spy_price)` and build `pivot_dict = {'price': spy_price, 'quant_pivot': qp_dict}`.

#### [MODIFY] [comprehensive_signals_job.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/comprehensive_signals_job.py)
- **Line 966~977**: Stop passing SPX spot price (~7700) into `QuantPivotCalculator.get_quant_pivot('SPY')`. Retrieve real-time SPY price via `QuantPivotCalculator.get_spy_current_price()` and populate `pivot_dict['price'] = spy_price`.

---

### Component 3: Option Seller Decision Engine & Manager

#### [MODIFY] [option_seller_engine.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_engine.py)
- **Scenario 2 (Lines 968~1050)**:
  - Ensure `qp_curr_p` strictly uses SPY price. Add defensive normalization: if `qp_curr_p > 2000.0` and `h1_val < 1000.0`, convert `qp_curr_p = round(qp_curr_p / 10.0, 2)`.
  - In Case 2B (Lower Boundary Bounce), include `TESTING_L1_SUPPORT` in `qp_zone` checks so that testing the L1 band triggers immediate `QUALIFIED` or `ARMED` order for SPY.
  - In Case 2A (Upper Boundary Rejection), include `TESTING_H1_RESISTANCE` in `qp_zone` checks.
  - Set `trigger_symbol = 'SPY'` unconditionally for QuantPivot boundary triggers.

#### [MODIFY] [option_seller_manager.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py)
- **Line 400~406**: In `_open_single_contract`, count only `trade_mode == 'AUTO'` active trades against the 2-position limit:
  ```python
  active_auto_trades_count = sum(
      1 for t in self.active_trades.values()
      if (t.get('entry_evidence') or {}).get('trade_mode') == 'AUTO'
  )
  if trade_mode == 'AUTO' and active_auto_trades_count >= 2:
      ...
  ```
  This prevents MANUAL trades from consuming AUTO trade capacity, resolving the rejection of triggered conditional orders.

---

## Verification Plan

### Automated Verification
1. Run Python unit test script verifying:
   - `QuantPivotCalculator.get_spy_current_price()` returns live/valid SPY price (~768-772).
   - `QuantPivotCalculator.get_quant_pivot('SPY', current_price=769.0)` accurately detects `TESTING_L1_SUPPORT` and `BULLISH_REVERSAL_ZONE`.
   - `OptionSellerEngine.evaluate_counter_trend_boundary_opportunity` with today's market metrics at L1 evaluates to `QUALIFIED` or `ARMED` for `BULLISH [BALANCED]` on SPY.
   - `OptionSellerManager` allows AUTO order opening when there are multiple active MANUAL trades.
