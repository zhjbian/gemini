# Walkthrough: Comprehensive Trading Decision & Chasing Protection

We have successfully redesigned the comprehensive trading decision engine (`综合交易决策`) to support a 27-case score mapping matrix with 7 structured decisions, and implemented dynamic intraday-range and time-of-day based chasing protection rules (`避免追高/追空`).

## Changes Made

### 1. Dynamic Chasing Protection (避免追高/追空)

To protect short-term (1-5DTE) and intraday (0DTE) trading decisions from entering trades at extreme daily price levels, we implemented the following algorithm:

#### Range & Time Threshold Matrix (Seattle PST time):
- **Morning Breakout Period (06:30 - 07:30 PST)**: Volatility is high.
  - Avoid buying if price is at or above **92%** of RTH range.
  - Avoid shorting if price is at or below **8%** of RTH range.
- **Midday Mean-Reversion Period (07:30 - 12:00 PST)**: Sideways market dominates.
  - Avoid buying if price is at or above **80%** of RTH range.
  - Avoid shorting if price is at or below **20%** of RTH range.
- **Power Hour Period (12:00 - 13:00 PST)**: Late session trends.
  - Avoid buying if price is at or above **85%** of RTH range.
  - Avoid shorting if price is at or below **15%** of RTH range.
- **Minimum Range**: Only applies if RTH High - Low range is $\ge 15.0$ points.

#### Rule-based Path Integration:
- In [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py#L822-L878), after querying the 27-case score matrix, if the decision is `开仓做多` or `开仓做空`, the server checks the RTH range and time.
- If it meets the threshold for chasing, the decision is downgraded to `避免开仓交易` and the explanation reason is updated.

#### AI Path Integration:
- In [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py#L730-L815), the current price position, RTH range high/low, and signal time are passed to Gemini in the prompt context.
- Gemini is explicitly instructed via systemic guidelines to downgrade new opening decisions to `避免开仓交易` if the threshold rules are breached.

#### Frontend Payload Updates:
- Updated [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js#L1640-L1695) to resolve and return `rth_price_low`, `rth_price_high`, `recent_micro_5m`, and `signal_time` from the Order Flow signal.
- In `Promise.all`, it resolves the current ES price (`esSpot`) and range position percentage (`pricePosPct`), passing them as AJAX parameters to `/data/comprehensive_direction_decision`.

---

### 2. Redesign of 27-Case Matrix (Implemented Prior)

- The simplified total-score logic was replaced with an explicit `decision_matrix` dictionary mapping all 27 `(spx_score, of_bt_score, of_sig_score)` tuples to one of 7 structured decisions:
  - **开仓做多** (Open Long)
  - **持有多头仓位** (Hold Long)
  - **卖出多头仓位** (Sell Long)
  - **开仓做空** (Open Short)
  - **持有空头仓位** (Hold Short)
  - **卖出空头仓位** (Sell Short)
  - **避免开仓交易** (Avoid Trading / Stand Aside)
- Replaced the time text input with a typeable dropdown (combobox).
- Corrected the zero-padding bug for single-digit minutes.
- Widened the direction column to `220px` to prevent wrapping.

## Verification

- The backend python file [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py) was compiled successfully under Python 3 with zero syntax errors.
- Client-side parameters are correctly collected from completed sub-signal responses and sent synchronously during the comprehensive synthesis step.
