import pandas as pd
from sqlalchemy import create_engine
import sys

# Add paths for models
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
from models import SpikeMWAgg, StockDaily

DATABASE_URL = 'mysql+pymysql://root:fmer244755@127.0.0.1:3306/bb_trade'
engine = create_engine(DATABASE_URL)

def analyze_nvda_rally():
    # 1. Fetch Price History from March 20
    query_price = "SELECT t_date, open, high, low, close FROM stock_daily WHERE ticker = 'NVDA' AND t_date >= '2026-03-20' ORDER BY t_date ASC"
    df_price = pd.read_sql(query_price, engine)
    
    # 2. Fetch Spikes from March 20
    query_spikes = "SELECT t_date, time, trading_hour, direction, target_price, spot_price, volume_agg, hit, hit_date FROM spike_mw_agg WHERE ticker = 'NVDA' AND t_date >= '2026-03-20' ORDER BY t_date ASC, time ASC"
    df_spikes = pd.read_sql(query_spikes, engine)
    
    print("### NVDA Price Action (Mar 20 - Apr 18)")
    print(df_price.to_string(index=False))
    
    print("\n### NVDA Institutional Spikes (Mar 20 - Apr 18)")
    if df_spikes.empty:
        print("No spikes found in this period.")
    else:
        print(df_spikes.to_string(index=False))

if __name__ == "__main__":
    analyze_nvda_rally()
