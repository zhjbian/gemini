import sys
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, date, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytz

# Add paths for models
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
from models import SpikeMWAgg, StockDaily

DATABASE_URL = 'mysql+pymysql://root:fmer244755@127.0.0.1:3306/bb_trade'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def is_rth(dt):
    """Check if the timestamp is within Regular Trading Hours (09:30 - 16:00 ET)."""
    h = dt.hour
    m = dt.minute
    time_val = h + m/60.0
    return 9.5 <= time_val < 16.0

def backfill_nvda_precision():
    session = Session()
    ticker = 'NVDA'
    lookback_days = 365
    start_date = date.today() - timedelta(days=lookback_days)
    
    print(f"Starting NVDA Precision Backfill (Lookback: {lookback_days} days)")
    
    # 1. Fetch NVDA Spikes
    spikes = session.query(SpikeMWAgg).filter(
        SpikeMWAgg.ticker == ticker,
        SpikeMWAgg.t_date >= start_date
    ).order_by(SpikeMWAgg.t_date.asc()).all()
    
    if not spikes:
        print("No spikes found.")
        return

    print(f"Found {len(spikes)} spikes to audit.")

    # 2. Fetch Intraday Data for precise same-day hit check
    # Fetching 1h data for the entire year is faster than per-day
    print("Fetching 1h price history for RTH alignment...")
    df_1h = yf.download(ticker, start=start_date - timedelta(days=5), interval="1h", prepost=False, progress=False)
    if isinstance(df_1h.columns, pd.MultiIndex): df_1h.columns = df_1h.columns.get_level_values(0)
    
    eastern = pytz.timezone("US/Eastern")
    pacific = pytz.timezone("US/Pacific")
    
    if df_1h.index.tz is None:
        df_1h.index = df_1h.index.tz_localize("UTC").tz_convert(eastern)
    else:
        df_1h.index = df_1h.index.tz_convert(eastern)
    
    # Filter for RTH Bars only
    df_rth = df_1h[df_1h.index.map(is_rth)].copy()

    # 3. Fetch Daily Data for future-day hits
    print("Fetching Daily price history for future resolution tracking...")
    daily_bars = session.query(StockDaily).filter(
        StockDaily.ticker == ticker,
        StockDaily.t_date >= start_date - timedelta(days=5)
    ).order_by(StockDaily.t_date.asc()).all()
    
    price_history_daily = []
    for b in daily_bars:
        price_history_daily.append({
            'date': b.t_date,
            'high': float(b.high),
            'low': float(b.low)
        })

    updated_count = 0
    buffer = 1.00

    for spike in spikes:
        target = float(spike.target_price)
        spike_date = spike.t_date
        
        # MotiveWave signals are in Pacific Time usually.
        # Let's assume the 'time' column is PST/PDT.
        # We need to compare it against RTH which is ET.
        
        # Convert spike time to ET for comparison
        discovery_dt_pacific = pacific.localize(datetime.combine(spike_date, spike.time))
        discovery_dt_market = discovery_dt_pacific.astimezone(eastern)
        
        found_hit = False
        
        # A. Check SAME DAY Intraday (Strictly After Signal)
        same_day_future = df_rth[(df_rth.index.date == spike_date) & (df_rth.index > discovery_dt_market)]
        
        for idx, row in same_day_future.iterrows():
            hit = False
            if spike.direction == 'UP' or spike.direction == 'Bullish':
                if row['High'] >= (target - buffer): hit = True
            else:
                if row['Low'] <= (target + buffer): hit = True
            
            if hit:
                spike.hit = True
                spike.hit_date = spike_date
                spike.hit_age = 0
                found_hit = True
                break
        
        # B. Check FUTURE DAYS Daily
        if not found_hit:
            for bar in price_history_daily:
                if bar['date'] <= spike_date: continue # Must be strictly after current day since we already checked RTH post-signal
                
                hit = False
                if spike.direction == 'UP' or spike.direction == 'Bullish':
                    if bar['high'] >= (target - buffer): hit = True
                else:
                    if bar['low'] <= (target + buffer): hit = True
                
                if hit:
                    spike.hit = True
                    spike.hit_date = bar['date']
                    spike.hit_age = (bar['date'] - spike_date).days
                    found_hit = True
                    break
        
        if not found_hit:
            spike.hit = False
            spike.hit_date = None
            spike.hit_age = None
            
        updated_count += 1
        if updated_count % 100 == 0:
            print(f"Audited {updated_count} spikes...")

    try:
        session.commit()
        print(f"Successfully completed precision backfill for NVDA ({len(spikes)} records).")
    except Exception as e:
        session.rollback()
        print(f"Error during commit: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    backfill_nvda_precision()
