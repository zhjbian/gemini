import sys
import os
import pandas as pd
from datetime import datetime, date, timedelta, time
import subprocess
import argparse
import yfinance as yf

# Path Setup
BASE_DIR = '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading'
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'bbt_data_web'))

from db_connection_legacy import db
from models import DarkPoolTradeAgg
from bbt_data_app import bbt_data_app

def generate_pine_code(trades, ticker, target_pct=5.0):
    pine_prefix = f"""//@version=5
indicator('BB_DarkPool_Visual_{ticker}_V2', overlay=true, max_labels_count=500, max_boxes_count=500)

type DarkPoolSignal
    string date_str
    int hour
    int minute
    float price
    float volume
    string side
    string session
    string hit_status
    int days

array<DarkPoolSignal> signals = array.new<DarkPoolSignal>()

fill_data() =>
"""
    
    signals_code = ""
    for t in trades:
        vol_m = round(t['size'] / 1000000, 2)
        t_date_str = t['trade_date'].strftime("%Y-%m-%d")
        t_hour = t['trade_time'].hour
        t_minute = t['trade_time'].minute
        
        hit_status = t['perf_status']
        hit_days = t['perf_days'] if t['perf_days'] else 0
        
        signals_code += f"    array.push(signals, DarkPoolSignal.new(\"{t_date_str}\", {t_hour}, {t_minute}, {t['price']}, {vol_m}, \"{t['side']}\", \"{t['trading_hour']}\", \"{hit_status}\", {hit_days}))\n"

    pine_suffix = """
if barstate.islast
    fill_data()
    for i = 0 to (array.size(signals) - 1)
        sig = array.get(signals, i)
        
        // 1. Time Setup
        string[] d_parts = str.split(sig.date_str, "-")
        y = int(str.tonumber(array.get(d_parts, 0)))
        m = int(str.tonumber(array.get(d_parts, 1)))
        d = int(str.tonumber(array.get(d_parts, 2)))
        t_sig = timestamp(y, m, d, sig.hour, sig.minute, 0)
        t_right = t_sig + 14400000 // 4 hour visual width
        
        // 2. Styling (Buy=Green, Sell=Red)
        color col = sig.side == "Buy" ? color.new(color.green, 20) : color.new(color.red, 20)
        
        // 3. Draw Volume Box (Factor 0.2 for TSLA)
        factor = 1
        top = sig.price + (sig.volume * factor)
        bottom = sig.price
        
        box.new(t_sig, top, t_right, bottom, xloc=xloc.bar_time, bgcolor=col, border_color=color.gray)
        
        // 4. Volume Label (Top of Box, No Overlap)
        label.new(t_sig, top, str.tostring(sig.volume) + "M", xloc=xloc.bar_time, yloc=yloc.price, color=color.new(color.white, 100), textcolor=color.white, style=label.style_none, size=size.small)
        
        // 5. Performance Label (Bottom)
        label_bg = sig.hit_status == "HIT" ? color.new(color.green, 10) : color.new(color.red, 10)
        status_text = sig.hit_status == "HIT" ? "HIT (" + str.tostring(sig.days) + "d)" : "FAIL"
        txt = sig.session + " " + sig.side + "\\n" + status_text
        
        label.new(t_sig, bottom, txt, xloc=xloc.bar_time, yloc=yloc.belowbar, color=label_bg, textcolor=color.white, style=label.style_label_up, size=size.small)
"""

    return pine_prefix + signals_code + pine_suffix

def audit_trades(trades, ticker, target_pct=5.0):
    """Perform quick backtest audit for each trade to determine HIT/FAIL."""
    if not trades: return []
    
    # Fetch historical data
    start_date = min(t.trade_date for t in trades) - timedelta(days=5)
    end_date = date.today() + timedelta(days=1)
    df_price = yf.download(ticker, start=start_date, end=end_date, interval='1d', auto_adjust=True)
    
    if df_price.empty:
        for t in trades:
            t.perf_status = "UNKNOWN"
            t.perf_days = 0
        return trades

    # Flatten yfinance MultiIndex if present
    if isinstance(df_price.columns, pd.MultiIndex):
        df_price.columns = df_price.columns.get_level_values(0)

    # Format Date Index
    df_price.index = df_price.index.normalize()
    
    trade_results = []
    for t_obj in trades:
        t = {
            'trade_date': t_obj.trade_date,
            'trade_time': t_obj.trade_time,
            'price': float(t_obj.price),
            'side': t_obj.side,
            'trading_hour': t_obj.trading_hour,
            'size': t_obj.size
        }
        
        price_start = t['price']
        eval_start = pd.Timestamp(t['trade_date'])
        
        # Look at the next 40 trading days (Start from NEXT day)
        eval_window = df_price[df_price.index > eval_start].head(40)
        
        perf_status = "FAIL"
        perf_days = 0
        
        if not eval_window.empty:
            if t['side'] == "Buy":
                target = price_start * (1 + target_pct/100)
                hit_bars = eval_window[eval_window['High'] >= target]
                if not hit_bars.empty:
                    hit_date = hit_bars.index[0]
                    # Count trading days starting from the next day
                    perf_days = len(df_price[(df_price.index > eval_start) & (df_price.index <= hit_date)])
                    if perf_days <= 20: 
                         perf_status = "HIT"
            else:
                target = price_start * (1 - target_pct/100)
                hit_bars = eval_window[eval_window['Low'] <= target]
                if not hit_bars.empty:
                    hit_date = hit_bars.index[0]
                    perf_days = len(df_price[(df_price.index > eval_start) & (df_price.index <= hit_date)])
                    if perf_days <= 20: 
                        perf_status = "HIT"
        
        t['perf_status'] = perf_status
        t['perf_days'] = perf_days
        trade_results.append(t)
        
    return trade_results

def main():
    parser = argparse.ArgumentParser(description='Generate Enhanced tradingView Pine Script for Dark Pool Trades')
    parser.add_argument('--ticker', type=str, default='TSLA', help='Stock ticker')
    parser.add_argument('--session', type=str, choices=['PM', 'RTH', 'AH', 'ALL'], default='ALL', help='Trading session')
    parser.add_argument('--min_vol', type=float, default=1.0, help='Minimum volume in Millions')
    parser.add_argument('--days', type=int, default=30, help='Lookback days')
    
    args = parser.parse_args()
    start_date = date.today() - timedelta(days=args.days)
    
    print(f"Querying DarkPoolTradeAgg for {args.ticker} >= {args.min_vol}M ({args.session}) since {start_date}...")
    
    with bbt_data_app.app_context():
        query = db.session.query(DarkPoolTradeAgg).filter(
            DarkPoolTradeAgg.ticker == args.ticker,
            DarkPoolTradeAgg.trade_date >= start_date,
            DarkPoolTradeAgg.size >= args.min_vol * 1000000
        )
        if args.session != 'ALL':
            query = query.filter(DarkPoolTradeAgg.trading_hour == args.session)
            
        trades_raw = query.order_by(DarkPoolTradeAgg.trade_date.desc(), DarkPoolTradeAgg.trade_time.desc()).limit(100).all()
        
        if not trades_raw:
            print("No matching trades found.")
            return

        print(f"Auditing Performance for {len(trades_raw)} signals...")
        trades_audited = audit_trades(trades_raw, args.ticker)

        print(f"Generating Pine Script V2...")
        pine_code = generate_pine_code(trades_audited, args.ticker)
        
        # Save to file
        ref_dir = os.path.dirname(os.path.abspath(__file__))
        out_file = os.path.join(ref_dir, f"{args.ticker}_tv_source.txt")
        with open(out_file, 'w') as f:
            f.write(pine_code)
            
        # Copy to clipboard
        try:
            subprocess.run("pbcopy", universal_newlines=True, input=pine_code)
            print(f"SUCCESS: Pine Script V2 copied to clipboard and saved to {out_file}")
        except:
            print(f"SUCCESS: Pine Script saved to {out_file} (Clipboard copy failed)")

if __name__ == '__main__':
    main()
