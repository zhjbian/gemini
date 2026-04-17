import sys
import os
import pandas as pd
from datetime import datetime, timedelta, time as dt_time
import pytz
import yfinance as yf
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Define the minimal models inline to avoid Flask-SQLAlchemy dependency issues
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, Date, Time, Enum, Numeric, DECIMAL

Base = declarative_base()

class OfBigTradeType:
    SingleTickBigTrade = "SingleTickBigTrade"
    SingleTickDarkTrade = "SingleTickDarkTrade"
    AggregateBigTrade = "AggregateBigTrade"

class TradeSide:
    BuySide = "Buy"
    SellSide = "Sell"

class OrderFlowBigTrade(Base):
    __tablename__ = 'order_flow_big_trade'

    id = Column(Integer, primary_key=True, autoincrement=True)
    t_date = Column(Date, nullable=False, index=True)
    trading_hour = Column(String(10), nullable=True)  # Pre-market, RTH, After-hours, PM, AH
    trade_time = Column(Time, nullable=False)
    ticker = Column(String(10), nullable=False, index=True)
    type = Column(String(50), nullable=False)  # SingleTickBigTrade, SingleTickDarkTrade, AggregateBigTrade
    side = Column(String(10), nullable=False)  # Buy or Sell
    volume = Column(Integer, nullable=False)
    price = Column(DECIMAL(10, 2), nullable=True)  # trade price
    off_price = Column(DECIMAL(10, 2), nullable=True)  # off_price
    dark_volume = Column(Integer, nullable=True)
    note = Column(String(300), nullable=True)

DATABASE_URL = 'mysql+pymysql://root:fmer244755@127.0.0.1:3306/bb_trade'

# RTH boundaries in Pacific Time (6:30 AM - 1:00 PM PT)
RTH_START_PT = dt_time(6, 30, 0)
RTH_END_PT = dt_time(13, 0, 0)


def format_hrs_days(total_hours):
    if total_hours is None or pd.isna(total_hours):
        return "-"
    hrs = int(round(total_hours))
    days = int(hrs // 24)
    return f"{hrs}({days})"


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
            period = "RTH"
        elif db_hour == "RTH_FH":
            period = "FirstHour"
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

    # 2. Fetch ES=F intraday data (1h)
    print(f"Downloading ES=F hourly data since {start_date.date()}...")
    es_h = yf.download("ES=F", start=start_date.strftime("%Y-%m-%d"), interval="1h", progress=False)

    # Fix yfinance multi-index columns
    if isinstance(es_h.columns, pd.MultiIndex):
        es_h.columns = es_h.columns.get_level_values(0)

    # We also keep a daily version for trading day logic
    es_d = es_h.resample('D').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()

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

            # Use execution time and price as baseline
            baseline_time = biggest_trade["time"]
            baseline_price = biggest_trade["exec_price"]

            results.append({
                "date": date_str,
                "period": period,
                "side": net_side,
                "net_vol": abs(buy_vol - sell_vol),
                "big_count": group["big_count"].sum(),
                "total_count": len(group),
                "time": baseline_time,
                "baseline_time": baseline_time,
                "baseline_price": baseline_price if baseline_price else None  # Use biggest trade's exec price as ES Base price
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
                    "baseline_time": row["time"],
                    "baseline_price": row["exec_price"]
                })

    df_signals = pd.DataFrame(results)
    print(f"Generated {len(df_signals)} signals. Evaluating...")

    def get_es_hourly_for_window(signal_date_str, n_days=4):
        """Get ES=F hourly data for signal_date + next trading days."""
        sig_date = pd.to_datetime(signal_date_str).replace(tzinfo=None) # Start naive
        tz_pacific = pytz.timezone('US/Pacific')
        
        # Localize target date to Pacific then to UTC to match Yahoo Index
        sig_date_utc = tz_pacific.localize(sig_date).astimezone(pytz.UTC)

        # Find the end of the window using daily index
        # We must use the same index type as es_d
        daily_days = es_d.loc[sig_date_utc.normalize():].head(n_days)
        if daily_days.empty:
            return pd.DataFrame()
        
        last_day = daily_days.index[-1]
        
        # Slice hourly data until the end of that last day
        window = es_h.loc[sig_date_utc : last_day + pd.Timedelta(hours=23, minutes=59)]
        return window.copy()


    def evaluate(row):
        try:
            baseline_price = row.get('baseline_price')
            if baseline_price is None or pd.isna(baseline_price):
                return pd.Series([None, None, None, None, None, None, None, None])

            price_start = float(baseline_price)
            sig_date_obj = pd.to_datetime(row['date']).replace(tzinfo=None)
            t_time = row['time'] 
            sig_dt_naive = datetime.combine(sig_date_obj, t_time)
            
            tz_pacific = pytz.timezone('US/Pacific')
            sig_dt = tz_pacific.localize(sig_dt_naive).astimezone(pytz.UTC)
            
            # Get ES hourly data for window
            es_window = get_es_hourly_for_window(row['date'], n_days=4)
            if es_window.empty:
                return pd.Series([None, None, None, None, None, None, None, None])

            # Strip any bars BEFORE the signal's hour bar
            # yfinance 1h bars are marked by start time.
            sig_dt_floor = sig_dt.replace(minute=0, second=0, microsecond=0)
            eval_window = es_window.loc[sig_dt_floor:]
            if eval_window.empty:
                # Fallback if window is empty
                eval_window = es_window.loc[sig_dt:]
                if eval_window.empty:
                     return pd.Series([None, None, None, None, None, None, None, None])

            target_pct = 0.75
            hit = 0
            hrs_to_hit = None
            max_favorable = price_start
            hrs_to_max = 0

            if row['side'] == "Buy":
                target_price = price_start * (1 + target_pct/100)
                # Max favorable move
                max_favorable = eval_window['High'].max()
                max_row = eval_window[eval_window['High'] == max_favorable].iloc[0]
                max_dt = max_row.name
                hrs_to_max = max(0, (max_dt - sig_dt).total_seconds() / 3600)
                
                # Hit evaluation
                hit_bars = eval_window[eval_window['High'] >= target_price]
                if not hit_bars.empty:
                    hit = 1
                    hit_dt = hit_bars.index[0]
                    hrs_to_hit = max(0, (hit_dt - sig_dt).total_seconds() / 3600)
                max_win_pct = (max_favorable - price_start) / price_start * 100
            else:
                target_price = price_start * (1 - target_pct/100)
                # Max favorable move
                max_favorable = eval_window['Low'].min()
                max_row = eval_window[eval_window['Low'] == max_favorable].iloc[0]
                max_dt = max_row.name
                hrs_to_max = max(0, (max_dt - sig_dt).total_seconds() / 3600)
                
                # Hit evaluation
                hit_bars = eval_window[eval_window['Low'] <= target_price]
                if not hit_bars.empty:
                    hit = 1
                    hit_dt = hit_bars.index[0]
                    hrs_to_hit = max(0, (hit_dt - sig_dt).total_seconds() / 3600)
                max_win_pct = (price_start - max_favorable) / price_start * 100

            # --- Extreme Chase Filter (Obvious Highs/Lows) ---
            # Lookback 12 hours from signal
            lookback_start = sig_dt - pd.Timedelta(hours=12)
            lookback_window = es_h.loc[lookback_start : sig_dt]
            is_extreme_chase = False
            extreme_price = None
            
            if not lookback_window.empty:
                range_high = lookback_window['High'].max()
                range_low = lookback_window['Low'].min()
                
                if row['side'] == "Buy":
                    extreme_price = range_high
                    if price_start >= (range_high - 10):
                        is_extreme_chase = True
                elif row['side'] == "Sell":
                    extreme_price = range_low
                    if price_start <= (range_low + 10):
                        is_extreme_chase = True

            eval_status = 1 if len(es_window.resample('D').count().dropna()) < 4 else 0

            return pd.Series([hit, max_win_pct, hrs_to_hit, price_start, max_favorable, eval_status, hrs_to_max, is_extreme_chase, extreme_price])
        except Exception as e:
            print(f"Error evaluating signal: {e}")
            import traceback
            traceback.print_exc()
            return pd.Series([None, None, None, None, None, None, None, None, None])

    df_signals[['hit', 'max_win_pct', 'hrs_to_hit', 'es_start', 'es_target', 'eval_status', 'hrs_to_max', 'is_extreme_chase', 'extreme_price']] = df_signals.apply(evaluate, axis=1)
    df_signals = df_signals.dropna(subset=['hit'])

    # Drop the intermediate columns (now stored as es_start/es_target)
    if 'baseline_price' in df_signals.columns:
        df_signals = df_signals.drop(columns=['baseline_price'])
    if 'baseline_time' in df_signals.columns:
        df_signals = df_signals.drop(columns=['baseline_time'])

    # 4. Summary (EXCLUDING Extreme Chase signals from global stats)
    print("\n=== ES Big Trade Statistical Analysis (Direct ES Measurement) ===")
    df_signals['hit'] = df_signals['hit'].astype(float)
    df_signals['vol_bucket'] = pd.cut(df_signals['net_vol'], bins=[0, 500, 1000, 2000, 100000], labels=["<500", "500-1000", "1000-2000", ">2000"])

    # Filter for non-chase signals for stats
    df_stats = df_signals[df_signals['is_extreme_chase'] == False].copy()
    
    df_winners = df_stats[df_stats['hit'] == 1.0].copy()
    summary = df_stats.groupby(['period', 'vol_bucket'], observed=False)[['hit', 'max_win_pct']].agg({'hit': ['count', 'mean'], 'max_win_pct': 'mean'}).reset_index()
    summary.columns = ['Period', 'Vol Bucket', 'Count', 'Hit Rate', 'Avg Max Win %']

    hrs_avg = df_winners.groupby(['period', 'vol_bucket'], observed=False)['hrs_to_hit'].mean().reset_index()
    hrs_avg.columns = ['Period', 'Vol Bucket', 'Avg Hrs To Hit']

    df_stats['same_day_hit'] = ((df_stats['hit'] == 1.0) & (df_stats['hrs_to_hit'] <= 16)).astype(float)
    same_day = df_stats.groupby(['period', 'vol_bucket'], observed=False)['same_day_hit'].mean().reset_index()
    same_day.columns = ['Period', 'Vol Bucket', 'Same Day Hit Rate']

    summary = summary.merge(same_day, on=['Period', 'Vol Bucket'], how='left')
    summary = summary.merge(hrs_avg, on=['Period', 'Vol Bucket'], how='left')

    summary['Hit Rate'] = (pd.to_numeric(summary['Hit Rate'], errors='coerce') * 100).round(2).astype(str) + "%"
    summary['Same Day Hit Rate'] = (pd.to_numeric(summary['Same Day Hit Rate'], errors='coerce') * 100).round(2).astype(str) + "%"
    summary['Avg Max Win %'] = pd.to_numeric(summary['Avg Max Win %'], errors='coerce').round(2).astype(str) + "%"
    summary['Avg Hrs To Hit'] = summary['Avg Hrs To Hit'].apply(format_hrs_days)

    summary = summary[['Period', 'Vol Bucket', 'Count', 'Hit Rate', 'Same Day Hit Rate', 'Avg Max Win %', 'Avg Hrs To Hit']]

    print(summary[summary['Count'] > 0])

    # Save results
    out_path = os.path.expanduser("~/.gemini/skills/order-flow-big-trade-analysis/references/backtest_results.csv")
    df_signals.to_csv(out_path, index=False)
    print(f"\nSaved detailed results to {out_path}")

    # Generate markdown report
    generate_report(summary, df_signals, start_date, lookback_days)


def generate_report(summary, df_signals, start_date, lookback_days):
    """Generate big_trade_stats.md, all_bucket_details.md, and individual bucket_analysis_*.md files."""
    ref_dir = os.path.expanduser("~/.gemini/skills/order-flow-big-trade-analysis/references")
    os.makedirs(ref_dir, exist_ok=True)
    end_date = datetime.now()
    total_signals = len(df_signals)
    # Calculate actual lookback span
    months = round(lookback_days / 30)
    period_str = f"{months} months" if months > 0 else f"{lookback_days} days"

    # ========== 1. big_trade_stats.md ==========
    md_lines = []
    md_lines.append("# ES Big Trade Signal Statistics (Direct ES Measurement)")
    md_lines.append("")
    md_lines.append("## Methodology")
    md_lines.append("- **Source**: `order_flow_big_trade` table, `type = SingleTickBigTrade`, `off_price >= 0`")
    md_lines.append("- **Ticker**: ES (Direct measurement)")
    md_lines.append("- **Period Classification**: Uses DB `trading_hour` field (PM/RTH/AH). FirstHour = RTH trades between 6:30-7:30 AM PT.")
    md_lines.append("- **ES Base Price**: Execution price of the biggest volume trade in the signal direction (PM/FirstHour), or individual trade price (RTH/AH).")
    md_lines.append("- **ES Max Profit Price**: Highest High (buy) or lowest Low (sell) of ES daily candle during the next 3 trading days, including the signal day.")
    md_lines.append("- **Success Criteria**: ES price moves ≥ 0.75% in the signal direction within 3 trading days.")
    md_lines.append(f"- **Backtest Period**: {period_str} ({start_date.strftime('%b %Y')} – {end_date.strftime('%b %Y')})")
    md_lines.append("- **Weak Signal Filter**: Discards PM/FirstHour signals if counter-volume ≥ 25% of total gross volume.")
    md_lines.append("- **Extreme Chase Filter**: Excludes signals buying within 10pts of 12h high or selling within 10pts of 12h low from global stats.")
    
    df_stats = df_signals[df_signals['is_extreme_chase'] == False]
    md_lines.append(f"- **Total Signals (Qualified)**: {len(df_stats)}")
    md_lines.append(f"- **Total Signals (Excluded Chase)**: {len(df_signals[df_signals['is_extreme_chase'] == True])}")
    md_lines.append("")
    md_lines.append("## Signal Aggregation Rules")
    md_lines.append("| Period | Aggregation | Notes |")
    md_lines.append("|---|---|---|")
    md_lines.append("| PM | Combined net volume per day | Baseline: Exec price of the biggest direction trade |")
    md_lines.append("| FirstHour | Combined net volume per day | Baseline: Exec price of the biggest direction trade |")
    md_lines.append("| RTH | Individual trades | Each trade is its own signal/baseline |")
    md_lines.append("| AH | Individual trades | Each trade is its own signal/baseline |")
    md_lines.append("")
    md_lines.append("## Hit Rate by Period and Volume Bucket (Direct ES measurement)")
    md_lines.append("")
    md_lines.append("| Period | ES Volume | Count | Hit Rate | Same Day Hit | Avg Max Win % | Hours to hit |")
    md_lines.append("|---|---|---|---|---|---|---|")

    for _, row in summary.iterrows():
        count = int(row['Count']) if row['Count'] != '-' else 0
        if count > 0:
            md_lines.append(
                f"| **{row['Period']}** | {row['Vol Bucket']} | {count} "
                f"| {row['Hit Rate']} | {row['Same Day Hit Rate']} "
                f"| {row['Avg Max Win %']} | {row['Avg Hrs To Hit']} |"
            )

    md_lines.append("")

    # Key Findings
    md_lines.append("## Key Findings")
    md_lines.append("")

    tier1 = []
    tier2 = []
    noise = []

    for _, row in summary.iterrows():
        count = int(row['Count']) if row['Count'] != '-' else 0
        if count == 0:
            continue
        hit_rate_str = row['Hit Rate'].replace('%', '')
        try:
            hit_rate = float(hit_rate_str)
        except:
            continue
        label = f"**{row['Period']} {row['Vol Bucket']} ES**"
        if hit_rate >= 70:
            tier1.append((label, hit_rate, count))
        elif hit_rate >= 60:
            tier2.append((label, hit_rate, count))
        else:
            noise.append((label, hit_rate, count))

    md_lines.append("### Tier 1 Signals (≥70% Hit Rate)")
    if tier1:
        for label, hr, count in sorted(tier1, key=lambda x: -x[1]):
            md_lines.append(f"1. {label}: {hr:.2f}% hit rate ({count} signals).")
    else:
        md_lines.append("None identified in this backtest period.")
    md_lines.append("")

    md_lines.append("### Tier 2 Signals (60-69% Hit Rate)")
    if tier2:
        for label, hr, count in sorted(tier2, key=lambda x: -x[1]):
            md_lines.append(f"1. {label}: {hr:.2f}% hit rate ({count} signals).")
    else:
        md_lines.append("None identified in this backtest period.")
    md_lines.append("")

    md_lines.append("### Noise / Discard (<60% Hit Rate)")
    if noise:
        for label, hr, count in sorted(noise, key=lambda x: x[1]):
            md_lines.append(f"1. {label}: {hr:.2f}% hit rate ({count} signals).")
    else:
        md_lines.append("None identified in this backtest period.")
    md_lines.append("")

    md_lines.append("## Recommended Classification Thresholds (Direct ES measurement)")
    md_lines.append("")
    md_lines.append("### Tier 1: High Conviction (High conviction direction)")
    md_lines.append("- **FirstHour** with total ES volume ≥ 500")
    md_lines.append("- **PM** with total ES volume > 1000")
    md_lines.append("")
    md_lines.append("### Tier 2: Elevated Conviction (Supplementary signal)")
    md_lines.append("- **RTH** with ES volume < 1000")
    md_lines.append("- **AH** with ES volume < 1000")
    md_lines.append("- **PM** with total ES volume ≤ 1000")
    md_lines.append("- **FirstHour** with total ES volume < 500")
    md_lines.append("")
    md_lines.append("### Discard / Noise (Low statistical edge)")
    md_lines.append("- **RTH** with ES volume ≥ 1000")
    md_lines.append("- **AH** with ES volume ≥ 1000")
    md_lines.append("- Any signal failing the **Weak Signal Filter** (Counter-trade ratio ≥ 25%)")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append(f"*Generated: {end_date.strftime('%Y-%m-%d')}. ES-only backtest using direct measurement. Window: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.*")

    with open(os.path.join(ref_dir, "big_trade_stats.md"), 'w') as f:
        f.write('\n'.join(md_lines))
    print(f"Saved report to {os.path.join(ref_dir, 'big_trade_stats.md')}")

    # ========== 2. Individual bucket_analysis_*.md files ==========
    bucket_order = ["<500", "500-1000", "1000-2000", ">2000"]
    period_order = ["PM", "FirstHour", "RTH", "AH"]

    all_bucket_toc = []

    for period in period_order:
        for bucket in bucket_order:
            bucket_df = df_signals[(df_signals['period'] == period) & (df_signals['vol_bucket'] == bucket)].copy()
            if bucket_df.empty:
                continue

            bucket_name_safe = bucket.replace('<', 'lt').replace('>', 'gt')
            fname = f"bucket_analysis_{period}_{bucket_name_safe}.md"
            fpath = os.path.join(ref_dir, fname)

            normal_df = bucket_df[bucket_df['is_extreme_chase'] == False]
            chase_df = bucket_df[bucket_df['is_extreme_chase'] == True]
            
            total_signals = len(bucket_df)
            overall_hit_rate = bucket_df['hit'].mean() * 100 if total_signals > 0 else 0
            overall_max_win = bucket_df['max_win_pct'].mean() if total_signals > 0 else 0

            normal_count = len(normal_df)
            normal_hit_rate = normal_df['hit'].mean() * 100 if normal_count > 0 else 0
            normal_max_win = normal_df['max_win_pct'].mean() if normal_count > 0 else 0

            chase_count = len(chase_df)
            chase_hit_rate = chase_df['hit'].mean() * 100 if chase_count > 0 else 0
            chase_max_win = chase_df['max_win_pct'].mean() if chase_count > 0 else 0
            
            lines = []
            lines.append(f"# Historical Detailed Analysis: {period} ({bucket})")
            lines.append("")
            lines.append(f"### Overall Snapshot")
            lines.append(f"- **Total Signals**: {total_signals}")
            lines.append(f"- **Overall Hit Rate**: {overall_hit_rate:.2f}%")
            lines.append(f"- **Overall Avg Max Favorable Move**: {overall_max_win:.2f}%")
            lines.append("")
            lines.append("---")
            lines.append("")
            
            lines.append("### Normal Signals")
            lines.append(f"- **Count**: {normal_count}")
            lines.append(f"- **Hit Rate**: {normal_hit_rate:.2f}%")
            lines.append(f"- **Avg Max Favorable Move**: {normal_max_win:.2f}%")
            lines.append("")
            
            md_lines_main = []
            md_lines_chase = []
            
            header_table = "| Date | Time | Side | ES Vol | Trades | Big≥500 | ES From | ES To | Hit? | Max Pct | Hours to hit | Hours to Max Profit |"
            header_chase = "| Date | Time | Side | ES Vol | Trades | Big≥500 | ES From | Rolling 12H H/L | ES To | Hit? | Max Pct | Hours to hit | Hours to Max Profit |"
            sep_table = "|---|---|---|---|---|---|---|---|---|---|---|---|"
            sep_chase = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"

            for _, row in bucket_df.sort_values('date', ascending=False).iterrows():
                # Format hrs columns
                hrs_hit_str = format_hrs_days(row['hrs_to_hit'])
                hrs_max_str = format_hrs_days(row['hrs_to_max'])
                date_str = str(row['date'])
                time_str = str(row['time']).split('.')[0]
                side = row['side']
                vol = int(row['net_vol'])
                trades = int(row['total_count']) if pd.notna(row.get('total_count')) else 1
                big = int(row['big_count']) if pd.notna(row.get('big_count')) else 0
                es_from = f"${row['es_start']:.2f}" if pd.notna(row.get('es_start')) else "-"
                
                target_val = f"${row['es_target']:.2f}" if pd.notna(row.get('es_target')) else "-"
                is_eval_pending = row.get('eval_status') == 1.0
                es_to = f"{target_val}*" if is_eval_pending else target_val
                
                hit_mark = "✅" if row['hit'] == 1.0 else "❌"
                if is_eval_pending and row['hit'] == 0.0:
                    hit_mark = "⏳" # Pending
                
                max_pct = f"{row['max_win_pct']:.2f}%" if pd.notna(row.get('max_win_pct')) else "-"
                
                if row['is_extreme_chase']:
                    ext_price = f"${row['extreme_price']:.2f}" if pd.notna(row.get('extreme_price')) else "-"
                    row_str = f"| {date_str} | {time_str} | {side} | {vol} | {trades} | {big} | {es_from} | {ext_price} | {es_to} | {hit_mark} | {max_pct} | {hrs_hit_str} | {hrs_max_str} |"
                    md_lines_chase.append(row_str)
                else:
                    row_str = f"| {date_str} | {time_str} | {side} | {vol} | {trades} | {big} | {es_from} | {es_to} | {hit_mark} | {max_pct} | {hrs_hit_str} | {hrs_max_str} |"
                    md_lines_main.append(row_str)

            lines.append("### Normal Signals")
            lines.append("")
            lines.append(header_table)
            lines.append(sep_table)
            lines.extend(md_lines_main)
            lines.append("")
            
            if md_lines_chase:
                lines.append("### Extreme Chase Signals (Excluded from Global Stats)")
                lines.append(f"- **Count**: {chase_count}")
                lines.append(f"- **Hit Rate**: {chase_hit_rate:.2f}%")
                lines.append(f"- **Avg Max Favorable Move**: {chase_max_win:.2f}%")
                lines.append("")
                lines.append("> [!NOTE]")
                lines.append("> These signals were buying within 10pts of the 12h high or selling within 10pts of the 12h low.")
                lines.append("")
                lines.append(header_chase)
                lines.append(sep_chase)
                lines.extend(md_lines_chase)
                lines.append("")

            with open(fpath, 'w') as f:
                f.write('\n'.join(lines))

            # Add TOC entry for all_bucket_details
            anchor = period.lower().replace('firsthour', 'firsthour').replace(' ', '-')
            bucket_label_display = bucket.replace('<', '&lt;').replace('>', '&gt;')
            anchor_bucket = bucket.replace('<', 'lt').replace('>', 'gt')
            all_bucket_toc.append(f"- [{period} ({bucket_label_display})](#{period.lower()}-{anchor_bucket.lower()})")
            print(f"  Saved {fname}")

    # ========== 3. all_bucket_details.md ==========
    all_lines = []
    all_lines.append("# ES Big Trade Signal — All Bucket Details (Direct ES Measurement)")
    all_lines.append("")
    all_lines.append(f"*Generated: {end_date.strftime('%Y-%m-%d')}. 12-month backtest using direct ES execution price baseline.*")
    all_lines.append("")
    all_lines.append("---")
    all_lines.append("")
    all_lines.append("## Table of Contents")
    all_lines.append("")
    for toc_entry in all_bucket_toc:
        all_lines.append(toc_entry)
    all_lines.append("")
    all_lines.append("---")

    for period in period_order:
        for bucket in bucket_order:
            bucket_df = df_signals[(df_signals['period'] == period) & (df_signals['vol_bucket'] == bucket)].copy()
            if bucket_df.empty:
                continue

            bucket_name_safe = bucket.replace('<', 'lt').replace('>', 'gt')
            normal_df = bucket_df[bucket_df['is_extreme_chase'] == False]
            chase_df = bucket_df[bucket_df['is_extreme_chase'] == True]
            
            total_signals = len(bucket_df)
            overall_hit_rate = bucket_df['hit'].mean() * 100 if total_signals > 0 else 0
            overall_max_win = bucket_df['max_win_pct'].mean() if total_signals > 0 else 0

            normal_count = len(normal_df)
            normal_hit_rate = normal_df['hit'].mean() * 100 if normal_count > 0 else 0
            normal_max_win = normal_df['max_win_pct'].mean() if normal_count > 0 else 0

            chase_count = len(chase_df)
            chase_hit_rate = chase_df['hit'].mean() * 100 if chase_count > 0 else 0
            chase_max_win = chase_df['max_win_pct'].mean() if chase_count > 0 else 0

            all_lines.append("")
            all_lines.append(f"## {period} ({bucket})")
            all_lines.append("")
            all_lines.append(f"### Overall Snapshot")
            all_lines.append(f"- **Total Signals**: {total_signals}")
            all_lines.append(f"- **Overall Hit Rate**: {overall_hit_rate:.2f}%")
            all_lines.append(f"- **Overall Avg Max Favorable Move**: {overall_max_win:.2f}%")
            all_lines.append("")
            
            all_lines.append("### Normal Signals")
            all_lines.append(f"- **Count**: {normal_count}")
            all_lines.append(f"- **Hit Rate**: {normal_hit_rate:.2f}%")
            all_lines.append(f"- **Avg Max Favorable Move**: {normal_max_win:.2f}%")
            all_lines.append("")
            
            main_rows = []
            chase_rows = []
            
            main_rows = []
            chase_rows = []
            
            header_table = "| Date | Time | Side | ES Vol | Trades | Big≥500 | ES From | ES To | Hit? | Max Pct | Hours to hit | Hours to Max Profit |"
            header_chase = "| Date | Time | Side | ES Vol | Trades | Big≥500 | ES From | Rolling 12H H/L | ES To | Hit? | Max Pct | Hours to hit | Hours to Max Profit |"
            sep_table = "|---|---|---|---|---|---|---|---|---|---|---|---|"
            sep_chase = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"

            for _, row in bucket_df.sort_values('date', ascending=False).iterrows():
                hrs_hit_str = format_hrs_days(row['hrs_to_hit'])
                hrs_max_str = format_hrs_days(row['hrs_to_max'])
                date_str = str(row['date'])
                time_str = str(row['time']).split('.')[0]
                side = row['side']
                vol = int(row['net_vol'])
                trades = int(row['total_count']) if pd.notna(row.get('total_count')) else 1
                big = int(row['big_count']) if pd.notna(row.get('big_count')) else 0
                es_from = f"${row['es_start']:.2f}" if pd.notna(row.get('es_start')) else "-"
                
                target_val = f"${row['es_target']:.2f}" if pd.notna(row.get('es_target')) else "-"
                is_eval_pending = row.get('eval_status') == 1.0
                es_to = f"{target_val}*" if is_eval_pending else target_val
                
                hit_mark = "✅" if row['hit'] == 1.0 else "❌"
                if is_eval_pending and row['hit'] == 0.0:
                    hit_mark = "⏳" # Pending

                max_pct = f"{row['max_win_pct']:.2f}%" if pd.notna(row.get('max_win_pct')) else "-"
                
                if row['is_extreme_chase']:
                    ext_price = f"${row['extreme_price']:.2f}" if pd.notna(row.get('extreme_price')) else "-"
                    row_str = f"| {date_str} | {time_str} | {side} | {vol} | {trades} | {big} | {es_from} | {ext_price} | {es_to} | {hit_mark} | {max_pct} | {hrs_hit_str} | {hrs_max_str} |"
                    chase_rows.append(row_str)
                else:
                    row_str = f"| {date_str} | {time_str} | {side} | {vol} | {trades} | {big} | {es_from} | {es_to} | {hit_mark} | {max_pct} | {hrs_hit_str} | {hrs_max_str} |"
                    main_rows.append(row_str)

            all_lines.append("### Normal Signals")
            all_lines.append("")
            all_lines.append(header_table)
            all_lines.append(sep_table)
            all_lines.extend(main_rows)
            all_lines.append("")
            
            if chase_rows:
                all_lines.append("### Extreme Chase Signals (Excluded from Global Stats)")
                all_lines.append(f"- **Count**: {chase_count}")
                all_lines.append(f"- **Hit Rate**: {chase_hit_rate:.2f}%")
                all_lines.append(f"- **Avg Max Favorable Move**: {chase_max_win:.2f}%")
                all_lines.append("")
                all_lines.append(header_chase)
                all_lines.append(sep_chase)
                all_lines.extend(chase_rows)
                all_lines.append("")

            all_lines.append("")
            all_lines.append("---")

    with open(os.path.join(ref_dir, "all_bucket_details.md"), 'w') as f:
        f.write('\n'.join(all_lines))
    print(f"Saved {os.path.join(ref_dir, 'all_bucket_details.md')}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    run_backtest(days)
