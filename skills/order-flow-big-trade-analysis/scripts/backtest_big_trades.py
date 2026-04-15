import sys
import os
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
import pytz
import yfinance as yf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add paths to imports
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
try:
    from models import OrderFlowBigTrade, OfBigTradeType, TradeSide
except ImportError:
    print("Error: Could not import models. Ensure shared paths are correct.")
    sys.exit(1)

DATABASE_URL = 'mysql+pymysql://root:fmer244755@127.0.0.1:3306/bb_trade'

# RTH boundaries in Pacific Time (6:30 AM - 1:00 PM PT)
RTH_START_PT = dt_time(6, 30, 0)
RTH_END_PT = dt_time(13, 0, 0)


def run_backtest(lookback_days=180):
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Fetch Big Trades
    start_date = datetime.now() - timedelta(days=lookback_days)
    print(f"Fetching ES trades since {start_date.date()}...")
    trades = session.query(OrderFlowBigTrade).filter(
        OrderFlowBigTrade.t_date >= start_date.date(),
        OrderFlowBigTrade.type == OfBigTradeType.SingleTickBigTrade,
        OrderFlowBigTrade.ticker.in_(["ES"]),
        OrderFlowBigTrade.off_price >= 0
    ).all()

    data = []
    print(f"Processing {len(trades)} trades...")
    for t in trades:
        vol = t.volume
        if t.ticker == "NQ":
            vol *= 3

        db_hour = str(t.trading_hour).strip() if t.trading_hour else None

        if db_hour == "PM":
            period = "PM"
        elif db_hour == "RTH":
            t_time = t.trade_time
            first_hour_end = dt_time(7, 30, 0)
            if t_time < first_hour_end:
                period = "FirstHour"
            else:
                period = "RTH"
        elif db_hour == "AH":
            period = "AH"
        else:
            continue

        data.append({
            "date": t.t_date,
            "time": t.trade_time,
            "ticker": t.ticker,
            "vol": vol,
            "big_count": 1 if vol >= 500 else 0,
            "side": "Buy" if "Buy" in str(t.side) else "Sell",
            "period": period,
            "exec_price": float(t.price) if t.price else None
        })

    df_trades = pd.DataFrame(data)
    if df_trades.empty:
        print("No trades found.")
        return

    # 2. Fetch ES=F Price Data (direct ES measurement)
    print(f"Downloading ES=F 1h data since {start_date.date()}...")
    es_h = yf.download("ES=F", start=start_date.strftime("%Y-%m-%d"), interval="1h")
    print(f"Downloading ES=F daily data since {start_date.date()}...")
    es_d = yf.download("ES=F", start=start_date.strftime("%Y-%m-%d"))

    # Fix yfinance multi-index columns
    if isinstance(es_h.columns, pd.MultiIndex):
        es_h.columns = es_h.columns.get_level_values(0)
    if isinstance(es_d.columns, pd.MultiIndex):
        es_d.columns = es_d.columns.get_level_values(0)

    # Convert 1h index to Pacific Time for RTH filtering
    pt_tz = pytz.timezone('America/Los_Angeles')
    if es_h.index.tz is not None:
        es_h_pt = es_h.copy()
        es_h_pt.index = es_h_pt.index.tz_convert(pt_tz)
    else:
        es_h_pt = es_h.copy()
        es_h_pt.index = es_h_pt.index.tz_localize('UTC').tz_convert(pt_tz)

    # 3. Process Signals
    results = []
    df_trades['date_str'] = df_trades['date'].astype(str)

    for (date_str, period), group in df_trades.groupby(["date_str", "period"]):
        if period in ["PM", "FirstHour"]:
            buy_vol = group[group["side"] == "Buy"]["vol"].sum()
            sell_vol = group[group["side"] == "Sell"]["vol"].sum()
            if buy_vol == 0 and sell_vol == 0:
                continue

            # Weak Signal Filter: counter trade ratio >= 25% for multi-trade groups
            total_gross_vol = buy_vol + sell_vol
            counter_vol = min(buy_vol, sell_vol)
            if len(group) > 1 and counter_vol > 0:
                counter_ratio = counter_vol / total_gross_vol
                if counter_ratio >= 0.25:
                    continue

            # Determine net direction
            net_side = "Buy" if buy_vol > sell_vol else "Sell"

            # Find biggest volume trade in the net direction
            direction_trades = group[group["side"] == net_side]
            if direction_trades.empty:
                continue
            biggest_trade = direction_trades.loc[direction_trades["vol"].idxmax()]

            # Use the biggest trade's execution price as baseline
            baseline_price = biggest_trade["exec_price"]
            baseline_time = biggest_trade["time"]

            results.append({
                "date": date_str,
                "period": period,
                "side": net_side,
                "net_vol": abs(buy_vol - sell_vol),
                "big_count": group["big_count"].sum(),
                "total_count": len(group),
                "time": baseline_time,
                "baseline_price": baseline_price
            })
        else:
            # Individual trades for RTH/AH — use trade's own exec_price
            for idx, row in group.iterrows():
                results.append({
                    "date": date_str,
                    "period": period,
                    "side": row["side"],
                    "net_vol": row["vol"],
                    "big_count": row["big_count"],
                    "total_count": 1,
                    "time": row["time"],
                    "baseline_price": row["exec_price"]
                })

    df_signals = pd.DataFrame(results)
    print(f"Generated {len(df_signals)} signals. Evaluating...")

    def get_rth_candles_for_window(signal_date_str, n_days=4):
        """Get ES=F 1h candles filtered to RTH hours for signal_date + next 3 days."""
        sig_date = pd.to_datetime(signal_date_str)
        # Get n_days of daily data to find actual trading days
        window_daily = es_d.loc[sig_date:].head(n_days)
        if window_daily.empty:
            return pd.DataFrame()

        window_start = window_daily.index[0]
        window_end = window_daily.index[-1] + pd.Timedelta(days=1)

        # Filter 1h candles to this date range
        mask = (es_h_pt.index >= pd.Timestamp(window_start, tz=pt_tz)) & \
               (es_h_pt.index < pd.Timestamp(window_end, tz=pt_tz))
        window_1h = es_h_pt[mask]

        # Filter to RTH hours only (6:30 AM - 1:00 PM PT)
        rth_candles = window_1h.between_time(
            RTH_START_PT.strftime('%H:%M'),
            RTH_END_PT.strftime('%H:%M')
        )
        return rth_candles

    def evaluate(row):
        try:
            price_start = row.get('baseline_price')
            if price_start is None or pd.isna(price_start):
                return pd.Series([None, None, None, None, None])

            # Get RTH 1h candles for 3-day evaluation window
            rth_candles = get_rth_candles_for_window(row['date'], n_days=4)

            if rth_candles.empty:
                return pd.Series([None, None, None, None, None])

            # Calculate mid prices for each candle: (High + Low) / 2
            rth_candles = rth_candles.copy()
            rth_candles['mid'] = (rth_candles['High'] + rth_candles['Low']) / 2

            if row['side'] == "Buy":
                # Max favorable = highest mid during RTH window
                max_favorable = rth_candles['High'].max()
                max_mid = rth_candles['mid'].max()
                max_win_pct = (max_favorable - price_start) / price_start * 100
                hit = max_win_pct >= 0.75
                days_to_hit = None
                if hit:
                    target = price_start * 1.0075
                    # Find first day where High exceeds target
                    for d_date in sorted(rth_candles.index.date):
                        day_candles = rth_candles[rth_candles.index.date == d_date]
                        if day_candles['High'].max() >= target:
                            sig_date = pd.to_datetime(row['date']).date()
                            days_to_hit = (d_date - sig_date).days
                            # Use the max mid of that day as the "To" price
                            max_favorable = day_candles['High'].max()
                            break
            else:
                # Max favorable = lowest mid during RTH window
                max_favorable = rth_candles['Low'].min()
                max_mid = rth_candles['mid'].min()
                max_win_pct = (price_start - max_favorable) / price_start * 100
                hit = max_win_pct >= 0.75
                days_to_hit = None
                if hit:
                    target = price_start * 0.9925
                    for d_date in sorted(rth_candles.index.date):
                        day_candles = rth_candles[rth_candles.index.date == d_date]
                        if day_candles['Low'].min() <= target:
                            sig_date = pd.to_datetime(row['date']).date()
                            days_to_hit = (d_date - sig_date).days
                            max_favorable = day_candles['Low'].min()
                            break

            return pd.Series([hit, max_win_pct, days_to_hit, price_start, max_favorable])
        except Exception as e:
            return pd.Series([None, None, None, None, None])

    df_signals[['hit', 'max_win_pct', 'days_to_hit', 'es_start', 'es_target']] = df_signals.apply(evaluate, axis=1)
    df_signals = df_signals.dropna(subset=['hit'])

    # Drop the intermediate baseline_price column (now stored as es_start)
    if 'baseline_price' in df_signals.columns:
        df_signals = df_signals.drop(columns=['baseline_price'])

    # 4. Summary
    print("\n=== ES Big Trade Statistical Analysis (Direct ES Measurement) ===")
    df_signals['hit'] = df_signals['hit'].astype(float)
    df_signals['vol_bucket'] = pd.cut(df_signals['net_vol'], bins=[0, 500, 1000, 2000, 100000], labels=["<500", "500-1000", "1000-2000", ">2000"])

    df_winners = df_signals[df_signals['hit'] == 1.0].copy()
    summary = df_signals.groupby(['period', 'vol_bucket'], observed=False)[['hit', 'max_win_pct']].agg({'hit': ['count', 'mean'], 'max_win_pct': 'mean'}).reset_index()
    summary.columns = ['Period', 'Vol Bucket', 'Count', 'Hit Rate', 'Avg Max Win %']

    days_avg = df_winners.groupby(['period', 'vol_bucket'], observed=False)['days_to_hit'].mean().reset_index()
    days_avg.columns = ['Period', 'Vol Bucket', 'Avg Days To Hit']

    df_signals['same_day_hit'] = ((df_signals['hit'] == 1.0) & (df_signals['days_to_hit'] == 0)).astype(float)
    same_day = df_signals.groupby(['period', 'vol_bucket'], observed=False)['same_day_hit'].mean().reset_index()
    same_day.columns = ['Period', 'Vol Bucket', 'Same Day Hit Rate']

    summary = summary.merge(same_day, on=['Period', 'Vol Bucket'], how='left')
    summary = summary.merge(days_avg, on=['Period', 'Vol Bucket'], how='left')

    summary['Hit Rate'] = (summary['Hit Rate'] * 100).round(2).astype(str) + "%"
    summary['Same Day Hit Rate'] = (summary['Same Day Hit Rate'] * 100).round(2).astype(str) + "%"
    summary['Avg Max Win %'] = summary['Avg Max Win %'].round(2).astype(str) + "%"
    summary['Avg Days To Hit'] = summary['Avg Days To Hit'].round(1).fillna('-').astype(str)

    summary = summary[['Period', 'Vol Bucket', 'Count', 'Hit Rate', 'Same Day Hit Rate', 'Avg Max Win %', 'Avg Days To Hit']]

    print(summary[summary['Count'] > 0])

    # Save results
    out_path = os.path.expanduser("~/.gemini/skills/order-flow-big-trade-analysis/references/backtest_results.csv")
    df_signals.to_csv(out_path, index=False)
    print(f"\nSaved detailed results to {out_path}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    run_backtest(days)
