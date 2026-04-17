import sys
import datetime
import pandas as pd
from decimal import Decimal

if len(sys.argv) < 3:
    print("Usage: python get_bbt_data.py <ticker> <date YYYY-MM-DD>")
    sys.exit(1)

ticker = sys.argv[1]
target_date_str = sys.argv[2]

sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")
from db_query import DbQuery



print("\n--- DARK POOL ---")
try:
    dps = DbQuery.dp_query_by_tickers(look_back_days=5, tickers=[ticker])
    if isinstance(dps, pd.DataFrame) and not dps.empty:
        dps['trade_date'] = dps['trade_date'].astype(str)
        df = dps[dps['trade_date'].str.contains(target_date_str)]
        for _, row in df.iterrows():
            print(f"Time: {row['trade_time']} | Type: {row['dp_type']} | Price: {row['price']} | Size: {row['size']} | Notional: {row['notional_value']}")
except Exception as e:
    print(f"Error querying Dark Pool: {e}")
