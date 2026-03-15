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
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/PyTools")
from db_query import DbQuery

print("--- OPTIONS ---")
try:
    options = DbQuery.option_flow_query_onchart_ticker(ticker)
    if isinstance(options, pd.DataFrame) and not options.empty:
        options['transac_date'] = options['transac_date'].astype(str)
        df = options[options['transac_date'].str.contains(target_date_str)]
        for _, row in df.iterrows():
            print(f"Time: {row['transac_time']} | Contract: {row['contract']} | Side: {row['side']} | Sentiment: {row['sentiment']} | Premium: {row['premium']} | Dir: {row['dir']}")
except Exception as e:
    print(f"Error querying Options: {e}")

print("\n--- ORDERS ---")
try:
    orders = DbQuery.order_flow_big_trade_single_tick_query_by_tickers([ticker])
    if isinstance(orders, pd.DataFrame) and not orders.empty:
        orders['t_date'] = orders['t_date'].astype(str)
        df = orders[orders['t_date'].str.contains(target_date_str)]
        for _, row in df.iterrows():
            print(f"Time: {row['trade_time']} | Side: {row['side']} | Type: {row['type']} | Vol: {row['volume']} | Price: {row['price']} | Prem: {row['premium']}")
except Exception as e:
    print(f"Error querying Orders: {e}")

print("\n--- SPIKES ---")
try:
    spikes = DbQuery.spike_mw_query_by_ticker_date(target_date_str, ticker)
    if isinstance(spikes, pd.DataFrame) and not spikes.empty:
        for _, row in spikes.iterrows():
            print(f"Time: {row['time']} | Dir: {row['direction']} | Target: {row['target_price']} | Spot: {row['spot_price']} | Vol: {row['volume']}")
except Exception as e:
    print(f"Error querying Spikes: {e}")

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
