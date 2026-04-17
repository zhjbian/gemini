import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, time as dt_time
import pytz
import os

def check():
    sig_date_str = "2025-08-05"
    sig_time_str = "01:03:36"
    sig_side = "Buy"
    price_start = 6364.00
    
    start_date = datetime.strptime(sig_date_str, "%Y-%m-%d") - timedelta(days=2)
    end_date = datetime.strptime(sig_date_str, "%Y-%m-%d") + timedelta(days=2)
    
    print(f"Downloading ES data for {sig_date_str}...")
    es_data = yf.download("ES=F", start=start_date, end=end_date, interval="1h")
    
    if es_data.empty:
        print("Failed to download ES data.")
        return

    # Reproduce logic from backtest_big_trades.py
    es_h = es_data.copy()
    es_h.index = es_h.index.tz_convert(pytz.UTC) # Ensure UTC like in script (yf returns localized often)
    
    sig_date_obj = datetime.strptime(sig_date_str, "%Y-%m-%d")
    t_time = datetime.strptime(sig_time_str, "%H:%M:%S").time()
    sig_dt_naive = datetime.combine(sig_date_obj, t_time)
    
    tz_pacific = pytz.timezone('US/Pacific')
    sig_dt = tz_pacific.localize(sig_dt_naive).astimezone(pytz.UTC)
    
    print(f"Signal Timestamp (UTC): {sig_dt}")
    print(f"Last few index values in ES data (UTC):")
    print(es_h.index[-5:])
    
    lookback_start = sig_dt - pd.Timedelta(hours=12)
    print(f"Lookback Start (UTC): {lookback_start}")
    
    # Selection logic from script
    lookback_window = es_h.loc[lookback_start : sig_dt]
    
    print(f"Lookback Window Size: {len(lookback_window)}")
    if not lookback_window.empty:
        range_high = lookback_window['High'].max()
        range_low = lookback_window['Low'].min()
        print(f"12H Range High: {range_high}")
        print(f"12H Range Low: {range_low}")
        
        if sig_side == "Buy":
            is_chase = price_start >= (range_high - 10)
            print(f"Buy Chase Check: {price_start} >= {range_high} - 10 ({range_high - 10})? -> {is_chase}")
            
    else:
        print("Lookback window is EMPTY!")

if __name__ == "__main__":
    check()
