import sys
import yfinance as yf
import pandas as pd
import numpy as np

def calculate_rsi(data, periods=14):
    close_delta = data['Close'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.rolling(window=periods).mean()
    ma_down = down.rolling(window=periods).mean()
    rs = ma_up / ma_down
    rsi = 100 - (100/(1 + rs))
    return rsi

if len(sys.argv) < 3:
    print("Usage: python get_tech_data.py <ticker> <date YYYY-MM-DD>")
    sys.exit(1)

ticker_str = sys.argv[1]
target_date = sys.argv[2]

ticker = yf.Ticker(ticker_str)
hist = ticker.history(period="1y")

if hist.empty:
    print(f"No data found for {ticker_str}")
    exit()

hist['SMA20'] = hist['Close'].rolling(window=20).mean()
hist['SMA50'] = hist['Close'].rolling(window=50).mean()
hist['SMA200'] = hist['Close'].rolling(window=200).mean()
hist['RSI'] = calculate_rsi(hist)

try:
    # yfinance indices are tz-aware; convert to naive for easy string matching
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)
        
    target_data = hist.loc[target_date]
    print(f"Date: {target_date}")
    print(f"Close: {target_data['Close']:.2f}")
    print(f"High: {target_data['High']:.2f}")
    print(f"Low: {target_data['Low']:.2f}")
    print(f"Volume: {target_data['Volume']}")
    print(f"SMA20: {target_data['SMA20']:.2f}")
    print(f"SMA50: {target_data['SMA50']:.2f}")
    print(f"SMA200: {target_data['SMA200']:.2f}")
    print(f"RSI: {target_data['RSI']:.2f}")
    
    # Calculate % change from previous day
    prev_date = hist.index[hist.index < target_date][-1]
    prev_close = hist.loc[prev_date]['Close']
    pct_change = ((target_data['Close'] - prev_close) / prev_close) * 100
    print(f"Pct Change: {pct_change:.2f}%")
    
    # 3 mo avg volume (approx 63 trading days)
    avg_vol_3mo = hist['Volume'].tail(63).mean()
    print(f"3mo Avg Vol: {avg_vol_3mo:.0f}")
    print(f"Vol % of 3mo Avg: {(target_data['Volume']/avg_vol_3mo)*100:.2f}%")
except KeyError:
    print(f"Data for {target_date} not found. Here is the last available date:")
    print(hist.tail(1))
