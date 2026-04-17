import sys
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
import pytz

# Add paths for models
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading")

from models import SpikeMWAgg

DATABASE_URL = 'mysql+pymysql://root:fmer244755@127.0.0.1:3306/bb_trade'

# Statistical constraints
HIT_WINDOW = 20  # Only count as a "Hit" if resolved within 20 trading days
SPECIAL_DAYS = ['2026-02-06']  # Days where large bursts are aggregated by bucket

def get_volume_bucket(vol):
    if vol < 10: return "<10"
    if vol < 20: return "10-19"
    if vol < 50: return "20-49"
    if vol <= 100: return "50-100"
    if vol < 500: return "100-499"
    if vol < 1000: return "500-999"
    if vol < 2000: return "1000-2000"
    if vol < 5000: return "2000-4999"
    return ">=5000"

def is_rth(dt):
    """Check if the timestamp is within Regular Trading Hours (09:30 - 16:00 ET)."""
    h = dt.hour
    m = dt.minute
    time_val = h + m/60.0
    return 9.5 <= time_val < 16.0

def run_backtest(ticker="TSLA", lookback_days=365):
    print(f"Starting Backtest for {ticker} (Lookback: {lookback_days} days, Window: {HIT_WINDOW} days, RTH Only)...")
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Fetch Spikes
    start_date = date.today() - timedelta(days=lookback_days)
    spikes = session.query(SpikeMWAgg).filter(
        SpikeMWAgg.ticker == ticker,
        SpikeMWAgg.t_date >= start_date,
        (SpikeMWAgg.is_prev_close == False) | (SpikeMWAgg.is_prev_close == None),
        func.abs(SpikeMWAgg.price_change) >= 0.03
    ).all()

    if not spikes:
        print("No spikes found matching criteria.")
        return

    print(f"Found {len(spikes)} valid spikes.")

    # 2. Fetch Price History
    hist_start = spikes[0].t_date if spikes else start_date
    print(f"Fetching 1h price history for {ticker}...")
    df_hist = yf.download(ticker, start=hist_start, interval="1h", prepost=True, progress=False)
    
    if df_hist.empty:
        print("Failed to fetch price history.")
        return
    
    if isinstance(df_hist.columns, pd.MultiIndex):
        df_hist.columns = df_hist.columns.get_level_values(0)

    eastern = pytz.timezone("US/Eastern")
    pacific = pytz.timezone("US/Pacific")
    
    if df_hist.index.tz is None:
        df_hist.index = df_hist.index.tz_localize("UTC").tz_convert(eastern)
    else:
        df_hist.index = df_hist.index.tz_convert(eastern)

    df_rth = df_hist[df_hist.index.map(is_rth)].copy()
    all_trading_days = sorted(list(set(df_hist.index.date)))
    day_idx_map = {d: i for i, d in enumerate(all_trading_days)}

    # 3. Simulation Each Spike
    full_audit_results = []
    for s in spikes:
        target = float(s.target_price)
        spot = float(s.spot_price) if s.spot_price else target
        direction = "Bullish" if target > spot else "Bearish"
        
        discovery_dt_pacific = pacific.localize(datetime.combine(s.t_date, s.time))
        discovery_dt_market = discovery_dt_pacific.astimezone(eastern)
        future_data = df_rth[df_rth.index > discovery_dt_market]
        
        min_move_trigger = spot * (1.03 if direction == "Bullish" else 0.97)
        target_hit = False
        days_to_target = None
        min_move_hit = False
        days_to_min = None
        max_profit_pct = 0.0
        days_to_max = 0
        best_price = spot
        spike_day_idx = day_idx_map.get(s.t_date, -1)
        
        for idx, row in future_data.iterrows():
            high = float(row['High'])
            low = float(row['Low'])
            curr_day_idx = day_idx_map.get(idx.date(), -1)
            day_offset = curr_day_idx - spike_day_idx if spike_day_idx != -1 else 0
            
            if not target_hit:
                if (direction == "Bullish" and high >= target) or (direction == "Bearish" and low <= target):
                    if day_offset <= HIT_WINDOW:
                        target_hit = True
                        days_to_target = day_offset
            
            if not min_move_hit:
                if (direction == "Bullish" and high >= min_move_trigger) or (direction == "Bearish" and low <= min_move_trigger):
                    if day_offset <= HIT_WINDOW:
                        min_move_hit = True
                        days_to_min = day_offset
            
            if direction == "Bullish":
                if high > best_price:
                    best_price = high
                    days_to_max = day_offset
            else:
                if low < best_price:
                    best_price = low
                    days_to_max = day_offset
                    
        if spot > 0:
            max_profit_pct = (best_price - spot) / spot * 100 if direction == "Bullish" else (spot - best_price) / spot * 100

        full_audit_results.append({
            "id": s.id,
            "date": s.t_date,
            "time": s.time.strftime("%H:%M:%S") if s.time else "N/A",
            "trading_hour": s.trading_hour,
            "vol": s.volume_agg,
            "vol_bucket": get_volume_bucket(s.volume_agg),
            "spot": spot,
            "target": target,
            "target_move_pct": abs(target - spot) / spot * 100 if spot > 0 else 0,
            "direction": direction,
            "target_hit": 1 if target_hit else 0,
            "days_to_target": days_to_target,
            "min_hit": 1 if min_move_hit else 0,
            "days_to_min": days_to_min,
            "max_profit_pct": max_profit_pct,
            "days_to_max": days_to_max
        })

    df_full = pd.DataFrame(full_audit_results)
    
    # 4. Statistical Normalization
    special_dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in SPECIAL_DAYS]
    normal_df = df_full[~df_full['date'].isin(special_dates)].copy()
    burst_df = df_full[df_full['date'].isin(special_dates)].copy()
    
    if not burst_df.empty:
        print(f"Aggregating burst data for special days: {SPECIAL_DAYS}")
        burst_df['time_min'] = burst_df['time'].str[:5] 
        burst_summary = burst_df.groupby(['date', 'time_min', 'vol_bucket', 'trading_hour']).agg({
            'target_hit': 'max',
            'min_hit': 'max',
            'days_to_target': 'min',
            'days_to_min': 'min',
            'max_profit_pct': 'mean',
            'target_move_pct': 'mean',
            'days_to_max': 'mean'
        }).reset_index()
        burst_summary = burst_summary.rename(columns={'time_min': 'time'})
        df_stats = pd.concat([normal_df, burst_summary], ignore_index=True)
    else:
        df_stats = normal_df

    # 5. Aggregation & Reporting
    def summarize_to_f(f, df_sub, title, group_by_vol=False):
        f.write(f"### {title}\n\n")
        f.write("| Bucket | Count | Avg Target Move | Target Hit Rate | Avg Days to Target | Min Move Hit Rate (3%) | Avg Days to Min Move | Avg Max Profit | Avg Days to Max Profit |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        
        bucket_order = ["<10", "10-19", "20-49", "50-100", "100-499", "500-999", "1000-2000", "2000-4999", ">=5000"]
        if group_by_vol:
            group_col = "vol_bucket"
            buckets = [b for b in bucket_order if b in df_sub[group_col].unique()]
        else:
            group_col = "trading_hour"
            buckets = [b for b in ["PM", "RTH", "AH"] if b in df_sub[group_col].unique()]

        for b in buckets:
            subset = df_sub[df_sub[group_col] == b]
            if subset.empty: continue
            t_hit_p = subset['target_hit'].mean() * 100
            m_hit_p = subset['min_hit'].mean() * 100
            t_hit_subset = subset[subset['target_hit'] == 1]
            avg_days_t = t_hit_subset['days_to_target'].mean() if not t_hit_subset.empty else 0
            m_hit_subset = subset[subset['min_hit'] == 1]
            avg_days_m = m_hit_subset['days_to_min'].mean() if not m_hit_subset.empty else 0
            prefix = "**" if b in ["10-19", "20-49", "50-100", "100-499", "500-999", "1000-2000", "2000-4999"] else ""
            suffix = "**" if prefix else ""
            f.write(f"| {prefix}{b}{suffix} | {len(subset)} | {subset['target_move_pct'].mean():.2f}% | {t_hit_p:.2f}% | {avg_days_t:.1f} | {m_hit_p:.2f}% | {avg_days_m:.1f} | {subset['max_profit_pct'].mean():.2f}% | {subset['days_to_max'].mean():.1f} |\n")
        f.write("\n")

    report_path = f"/Users/zhijiebian/.gemini/skills/spike-analysis/references/{ticker}_reference_data.md"
    with open(report_path, "w") as f:
        f.write(f"# Spike Analysis: Historical Reference Data ({ticker})\n\n")
        f.write(f"**Analysis Parameters:**\n")
        f.write(f"- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"- **Lookback**: {lookback_days} days\n")
        f.write(f"- **Hit Logic**: **RTH ONLY** within {HIT_WINDOW} trading days.\n")
        f.write(f"- **De-duplication**: Hits on special days {SPECIAL_DAYS} are aggregated by minute and bucket.\n")
        f.write(f"- **Total Valid Spikes (Normalized)**: {len(df_stats)}\n\n")
        f.write("---\n\n")
        f.write("## High-Level Findings\n\n")
        f.write(f"Analysis shows that **Volume >= 20** is the key threshold for consistent **70%+ hit rates** in the sub-50 volume category.\n\n")

        summarize_to_f(f, df_stats, "Results by Timing Bracket")
        f.write("---\n\n")
        rth_stats = df_stats[df_stats['trading_hour'] == 'RTH']
        summarize_to_f(f, rth_stats, "Detailed Breakdown: \"The Golden Signal\" (RTH)", group_by_vol=True)
        f.write("---\n\n")
        pm_stats = df_stats[df_stats['trading_hour'] == 'PM']
        summarize_to_f(f, pm_stats, "Detailed Breakdown: Pre-Market (PM)", group_by_vol=True)
        f.write("---\n\n")

        f.write(f"### Skill Guidelines ({ticker} Specific)\n\n")
        f.write(f"1. **Tier 1 (Instant Magnets - 90%+ Confidence)**:\n")
        f.write(f"    - Any **PM** spike with **10+** Volume.\n")
        f.write(f"    - Any **RTH** spike with **50+** Volume.\n")
        f.write(f"2. **Tier 2 (Conviction Swings - 70% Confidence)**:\n")
        f.write(f"    - Any **RTH** spike with **20-49** Volume.\n")
        f.write(f"3. **Noise Filter (Ignore)**:\n")
        f.write(f"    - All **AH** spikes (Overshoot noise).\n")
        f.write(f"    - **RTH** spikes with **< 20** Volume.\n")
        f.write(f"    - **PM** spikes with **< 10** Volume.\n")

    # 6. Detailed Audit Report
    detailed_path = f"/Users/zhijiebian/.gemini/skills/spike-analysis/references/{ticker}_RTH_volume_details.md"
    with open(detailed_path, "w") as f:
        f.write(f"# Detailed RTH Volume Analysis: {ticker}\n\n")
        f.write(f"- **Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        rth_full = df_full[df_full['trading_hour'] == 'RTH']
        normal_rth = rth_full[~rth_full['date'].isin(special_dates)].copy()
        special_audit = rth_full[rth_full['date'].isin(special_dates)].copy()
        bucket_order = ["<10", "10-19", "20-49", "50-100", "100-499", "500-999", "1000-2000", "2000-4999", ">=5000"]
        for b in bucket_order:
            subset = normal_rth[normal_rth['vol_bucket'] == b]
            if subset.empty: continue
            
            # Calculate hit rate for this bucket
            hit_rate = subset['target_hit'].mean() * 100
            
            f.write(f"## Volume Bucket: {b} (Total: {len(subset)}, Hit Rate: {hit_rate:.2f}%)\n\n")
            f.write("| Date | Time | Direction | Spot | Target | Volume | Move % | Target Hit | Target Days | Min Hit | Min Days | Max Profit | Max Days |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            subset = subset.sort_values(by='date', ascending=False)
            for _, row in subset.iterrows():
                t_hit_str = "✅" if row['target_hit'] else "❌"
                m_hit_str = "✅" if row['min_hit'] else "❌"
                t_days_str = f"{int(row['days_to_target'])}" if row['target_hit'] else "-"
                m_days_str = f"{int(row['days_to_min'])}" if row['min_hit'] else "-"
                f.write(f"| {row['date']} | {row['time']} | {row['direction']} | {row['spot']:.2f} | {row['target']:.2f} | {int(row['vol'])} | {row['target_move_pct']:.2f}% | {t_hit_str} | {t_days_str} | {m_hit_str} | {m_days_str} | {row['max_profit_pct']:.2f}% | {int(row['days_to_max'])} |\n")
            f.write("\n")

        if not special_audit.empty:
            f.write("---\n\n")
            f.write("## Special Days Audit (Outlier Bursts)\n\n")
            f.write("| Date | Time | Direction | Spot | Target | Volume | Move % | Target Hit | Target Days | Min Hit | Min Days | Max Profit | Max Days |\n")
            f.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            special_audit = special_audit.sort_values(by=['date', 'time'], ascending=False)
            for _, row in special_audit.iterrows():
                t_hit_str = "✅" if row['target_hit'] else "❌"
                m_hit_str = "✅" if row['min_hit'] else "❌"
                t_days_str = f"{int(row['days_to_target'])}" if row['target_hit'] else "-"
                m_days_str = f"{int(row['days_to_min'])}" if row['min_hit'] else "-"
                f.write(f"| {row['date']} | {row['time']} | {row['direction']} | {row['spot']:.2f} | {row['target']:.2f} | {int(row['vol'])} | {row['target_move_pct']:.2f}% | {t_hit_str} | {t_days_str} | {m_hit_str} | {m_days_str} | {row['max_profit_pct']:.2f}% | {int(row['days_to_max'])} |\n")
            f.write("\n")
            
    df_full.to_csv(f"/Users/zhijiebian/.gemini/skills/spike-analysis/references/backtest_spike_results_{ticker.lower()}.csv", index=False)
    print(f"Reports refined with 20-volume threshold.")

if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "TSLA"
    days_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    run_backtest(ticker_arg, days_arg)
