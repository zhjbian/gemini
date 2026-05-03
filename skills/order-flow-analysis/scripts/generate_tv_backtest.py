import os
import sys
import pandas as pd
import subprocess
import argparse
from datetime import datetime, timedelta

"""
TRADINGVIEW INSTITUTIONAL BACKTEST VISUALIZATION BRIDGE

COLOR CONVICTION MODEL:
-----------------------
1. SIGNAL EXECUTION (VOLUME BOXES):
   - DARK POOL (DP): 
     * CYAN (#00FFFF): Institutional BUY conviction (Net Vol >= 1M).
     * MAGENTA (#FF00FF): Institutional SELL conviction (Net Vol >= 1M).
   - REGULAR (NON-DP):
     * GREEN: Institutional BUY conviction (Net Vol >= 1M).
     * RED: Institutional SELL conviction (Net Vol >= 1M).
   * Height maps to Volume (Scaled by 0.5 for TSLA).

2. PERFORMANCE MATURATION (LABELS & TARGET LINES):
   - GREEN: 5% Target Hit within 20 trading days.
   - ORANGE: Late Hit maturation (21–60 trading days).
   - RED: Failed maturation within the 60-day audit window.

USAGE:
/usr/local/bin/python3 /Users/zhijiebian/.gemini/skills/order-flow-analysis/scripts/generate_tv_backtest.py --ticker TSLA
/usr/local/bin/python3 /Users/zhijiebian/.gemini/skills/order-flow-analysis/scripts/generate_tv_backtest.py --ticker TSLA,NVDA

Run this script to generate Pine Script code for high-fidelity backtest results.
The code is automatically copied to the clipboard for deployment in TradingView Pine Editor.
"""

def convert_to_tradingview_time(trade_date_str, t_time_str, ticker, offset_index=0):
    """Aligns backtest timestamps with TradingView chart time."""
    trade_date = datetime.strptime(str(trade_date_str), "%Y-%m-%d").date()
    # Handle both HH:MM:SS and HH:MM:SS.mmmmmm
    t_time_str = str(t_time_str).split('.')[0]
    t_time = datetime.strptime(t_time_str, "%H:%M:%S").time()
    
    dt_local = datetime.combine(trade_date, t_time)
    # Removing +3h offset to align with user's chart (PT -> PT alignment)
    # Adding horizontal staggering for concurrent signals (15 min steps)
    dt_tradingview = dt_local + timedelta(minutes=15 * offset_index)
    
    return dt_tradingview

def generate_pine_script(df, ticker):
    # 1. DEDUPLICATION: Process signals to remove redundant entries
    df['time_clean'] = df['time'].apply(lambda x: str(x).split('.')[0])
    # Sort by volume descending so we keep the largest volume in case of duplicates
    df = df.sort_values('net_vol', ascending=False)
    df_deduped = df.drop_duplicates(subset=['date', 'time_clean', 'side']).copy()
    # Sort back by time for the indicator fill
    df_deduped = df_deduped.sort_values(['date', 'time_clean'])
    
    pine_prefix = f"""//@version=5
indicator('BB_Backtest_Audit_{ticker}', overlay=true, max_labels_count=500)

type OfBacktestSignal
    string date_str
    string time_str
    int hour
    int minute
    string side
    string mw_side
    float volume
    string hit_status
    int days_to_hit
    float target_price
    float drawdown
    float max_profit
    float price
    bool is_dp

array<OfBacktestSignal> signals = array.new<OfBacktestSignal>()

fill_data() =>
"""
    
    # Track seen timestamps for horizontal staggering
    seen_ts = {}
    signals_code = ""
    for _, row in df_deduped.iterrows():
        ts_key = (row['date'], row['time_clean'])
        offset_idx = seen_ts.get(ts_key, 0)
        seen_ts[ts_key] = offset_idx + 1
        
        dt_tv = convert_to_tradingview_time(row['date'], row['time'], ticker, offset_idx)
        date_str = dt_tv.strftime("%Y-%m-%d")
        time_str = row['time_clean']
        side = row['side']
        mw_side = row['mw_side']
        vol = round(row['net_vol'] / 1000000, 2)
        is_dp = 'true' if row['is_dp'] == 1 else 'false'
        
        # Determine Hit Status
        status = "FAIL"
        days = 0
        if row['hit'] == 1.0:
            status = "TARGET"
            days = int(row['days_to_hit'])
        elif row['late_hit'] == 1.0:
            status = "LATE"
            days = int(row['days_to_late'])
            
        target = row['es_target']
        price = row['es_start']
        mue = row['mue_pre_hit'] if row['hit'] == 1.0 else (row['mue_pre_late'] if row['late_hit'] == 1.0 else 0)
        mfe = row['max_win_pct']
        
        # Clean data for Pine
        mue_val = round(mue * 100, 2) if pd.notna(mue) else 0.0
        mfe_val = round(mfe * 100, 2) if pd.notna(mfe) else 0.0
        
        signals_code += f"    array.push(signals, OfBacktestSignal.new(\"{date_str}\", \"{time_str}\", {dt_tv.hour}, {dt_tv.minute}, \"{side}\", \"{mw_side}\", {vol}, \"{status}\", {days}, {target}, {mue_val}, {mfe_val}, {price}, {is_dp}))\n"

    pine_suffix = """
var float factor = na
if barstate.islast
    switch syminfo.ticker
        "TSLA" => factor := 0.5
        "NVDA" => factor := 0.015
        "ES1!" => factor := 7.5
        "NQ1!" => factor := 10
        => factor := 0.01

    fill_data()
    for i = 0 to (array.size(signals) - 1)
        sig = array.get(signals, i)
        
        string[] d_parts = str.split(sig.date_str, "-")
        y = int(str.tonumber(array.get(d_parts, 0)))
        m = int(str.tonumber(array.get(d_parts, 1)))
        d = int(str.tonumber(array.get(d_parts, 2)))
        t_sig = timestamp(y, m, d, sig.hour, sig.minute, 0)
        t_right = t_sig + 14400000 // 4 hour width
        
        // 1. Maturation Status Color (Result Audit)
        color status_color = color.new(color.red, 20)
        if sig.hit_status == "TARGET"
            status_color := color.new(color.green, 20)
        else if sig.hit_status == "LATE"
            status_color := color.new(color.orange, 20)
        
        // 2. Pivot Entry Box (Signal Itself)
        color box_color = na
        if sig.is_dp
            box_color := sig.side == "Buy" ? color.new(#00FFFF, 20) : color.new(#FF00FF, 20)
        else
            box_color := sig.side == "Buy" ? color.new(color.green, 20) : color.new(color.red, 20)
            
        bottom = sig.price
        top = bottom + sig.volume * 10 * factor 
        box.new(t_sig, top, t_right, bottom, xloc=xloc.bar_time, bgcolor=box_color, border_color=color.gray)

        // 3. Maturation Result Label
        string status_text = sig.hit_status == "TARGET" ? "HIT (" + str.tostring(sig.days_to_hit) + "d)" : 
                             sig.hit_status == "LATE" ? "LATE (" + str.tostring(sig.days_to_hit) + "d)" : "FAIL"
                             
        string side_text = sig.side != sig.mw_side ? sig.side + " (Override)" : sig.side
        txt = str.tostring(sig.volume) + "M " + side_text + "\\n" + status_text + "\\nDD: " + str.tostring(sig.drawdown) + "%"
        
        // Use status_color for the label itself for clear identification
        label.new(t_sig, bottom, txt, xloc=xloc.bar_time, yloc=yloc.belowbar, color=status_color, textcolor=color.white, style=label.style_label_up, size=size.small, textalign=text.align_center)
        
        // 4. Institutional Target Projection
        line.new(t_sig, sig.target_price, t_sig + (86400000 * 5), sig.target_price, xloc=xloc.bar_time, color=status_color, style=line.style_dashed)
"""
    
    return pine_prefix + signals_code + pine_suffix

def main():
    parser = argparse.ArgumentParser(description="Generate TradingView Pine Script for backtest results.")
    parser.add_argument("--ticker", type=str, default="TSLA", help="Ticker(s) to process, comma-separated (e.g., TSLA or TSLA,NVDA)")
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.ticker.split(',')]
    
    # Locate latest backtest CSV
    ref_dir = os.path.expanduser("~/.gemini/skills/order-flow-analysis/references/backtest")
    dates = sorted([d for d in os.listdir(ref_dir) if os.path.isdir(os.path.join(ref_dir, d))], reverse=True)
    if not dates:
        print("No backtest results found.")
        return
        
    latest_date_dir = dates[0]

    for ticker in tickers:
        print(f"\n--- Processing {ticker} ---")
        csv_path = os.path.join(ref_dir, latest_date_dir, f"{ticker}_backtest_results.csv")
        if not os.path.exists(csv_path):
            print(f"CSV not found: {csv_path}")
            continue
            
        print(f"Loading results from {csv_path}...")
        df = pd.read_csv(csv_path)
        
        # Apply Filtering: RTH/RTH_FH and >= 1M
        print("Filtering for PM/RTH/FirstHour sessions and >= 1,000,000 shares...")
        df_filtered = df[
            (df['period'].isin(['RTH', 'FirstHour', 'PM'])) &
            (df['net_vol'] >= 1000000)
        ].copy()
        
        if df_filtered.empty:
            print(f"No signals match the filters for {ticker}.")
            continue
            
        print(f"Generating TradingView script for {len(df_filtered)} signals...")
        pine_code = generate_pine_script(df_filtered, ticker)
        
        out_file = os.path.join(ref_dir, f"{ticker}_tv_indicator_script.txt")
        with open(out_file, 'w') as f:
            f.write(pine_code)
        print(f"SUCCESS: TradingView Pine Script saved to {out_file}")
        
        try:
            subprocess.run("pbcopy", universal_newlines=True, input=pine_code)
            print(f"Copied {ticker} script to clipboard!")
        except Exception as e:
            print(f"Failed to copy to clipboard: {e}")

if __name__ == "__main__":
    main()
