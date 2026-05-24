import sys
import pandas as pd
import yfinance as yf
import json
from datetime import datetime, timedelta

def get_indicators(ticker, target_date_str=None):
    try:
        if not target_date_str:
            target_date_str = datetime.now().strftime('%Y-%m-%d')
        
        target_date = pd.to_datetime(target_date_str)
        # Download 1 year data for SMA200/RSI
        start_date = (target_date - timedelta(days=365)).strftime('%Y-%m-%d')
        end_date = (target_date + timedelta(days=2)).strftime('%Y-%m-%d')
        
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if df.empty: return {"error": "No data"}

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Calculations
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['SMA200'] = df['Close'].rolling(window=200).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Find closest date <= target_date
        available_dates = df.index[df.index <= target_date]
        if available_dates.empty: return {"error": "Date too early"}
        
        idx = available_dates[-1]
        row = df.loc[idx]
        
        # Scalar helpers to avoid Series ambiguity
        def to_val(val):
            if hasattr(val, 'item'): return float(val.item())
            return float(val)

        # Pct Change from prev trading day
        prev_idx_list = df.index[df.index < idx]
        pct_change = 0
        if not prev_idx_list.empty:
            prev_close = to_val(df.loc[prev_idx_list[-1]]['Close'])
            pct_change = float((to_val(row['Close']) - prev_close) / prev_close * 100)
            
        avg_vol = float(df['Volume'].tail(63).mean())

        data = {
            "ticker": ticker,
            "date": idx.strftime('%Y-%m-%d'),
            "close": to_val(row['Close']),
            "rsi": to_val(row['RSI']) if not pd.isna(row.get('RSI', float('nan'))) else 50.0,
            "sma20": to_val(row['SMA20']) if not pd.isna(row.get('SMA20', float('nan'))) else to_val(row['Close']),
            "sma50": to_val(row['SMA50']) if not pd.isna(row.get('SMA50', float('nan'))) else to_val(row['Close']),
            "sma200": to_val(row['SMA200']) if not pd.isna(row.get('SMA200', float('nan'))) else to_val(row['Close']),
            "pct_change": pct_change,
            "volume": to_val(row['Volume']),
            "vol_ratio": float(to_val(row['Volume']) / avg_vol * 100) if avg_vol > 0 else 100.0
        }
        return data
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Ticker required"}))
        sys.exit(1)
        
    ticker = sys.argv[1]
    date_str = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    
    result = get_indicators(ticker, date_str)
    
    if "--json" in sys.argv:
        print(json.dumps(result))
    else:
        for k, v in result.items():
            print(f"{k}: {v}")
