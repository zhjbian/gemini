import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

start_date = "2026-04-01"
print(f"Downloading ES=F daily data since {start_date}...")
es_d = yf.download("ES=F", start=start_date, progress=False)

if isinstance(es_d.columns, pd.MultiIndex):
    es_d.columns = es_d.columns.get_level_values(0)

print(es_d[['High', 'Low']].tail(10))

# Check for 2026-04-13
try:
    print("\nData for 2026-04-13:")
    print(es_d.loc['2026-04-13'])
except Exception as e:
    print(f"Error accessing 2026-04-13: {e}")

# Check the window logic
sig_date = pd.to_datetime("2026-04-13")
window = es_d.loc[sig_date:].head(4)
print("\nWindow for 2026-04-13 (head 4):")
print(window[['High', 'Low']])
