import sys
import pandas as pd
from datetime import datetime, timedelta, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add paths for models
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
from models import SpikeMWAgg, StockDaily

DATABASE_URL = 'mysql+pymysql://root:fmer244755@127.0.0.1:3306/bb_trade'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

def backfill_nvda_hits():
    session = Session()
    ticker = 'NVDA'
    lookback_days = 365
    start_date = date.today() - timedelta(days=lookback_days)
    
    print(f"Starting NVDA Hit Backfill (Lookback: {lookback_days} days)")
    
    # 1. Fetch all NVDA Spikes for the period
    spikes = session.query(SpikeMWAgg).filter(
        SpikeMWAgg.ticker == ticker,
        SpikeMWAgg.t_date >= start_date
    ).order_by(SpikeMWAgg.t_date.asc()).all()
    
    if not spikes:
        print("No spikes found for NVDA.")
        return

    print(f"Found {len(spikes)} spikes to check.")

    # 2. Fetch all NVDA daily bars for the period to avoid per-spike queries
    # Fetch price history starting from the earliest spike date
    earliest_date = spikes[0].t_date
    daily_bars = session.query(StockDaily).filter(
        StockDaily.ticker == ticker,
        StockDaily.t_date >= earliest_date
    ).order_by(StockDaily.t_date.asc()).all()
    
    # Organize bars into a list of dicts for faster iteration
    price_history = []
    for b in daily_bars:
        price_history.append({
            'date': b.t_date,
            'high': float(b.high),
            'low': float(b.low)
        })

    updated_count = 0
    buffer = 1.00 # Standard buffer for individual stocks

    for spike in spikes:
        target = float(spike.target_price)
        spike_date = spike.t_date
        
        # Reset hit status if needed (optional, depends on if we want to refresh everything)
        # spike.hit = False
        # spike.hit_date = None
        # spike.hit_age = None
        
        found_hit = False
        # Check all price bars on or after spike date
        for bar in price_history:
            if bar['date'] < spike_date:
                continue
            
            hit = False
            if spike.direction == 'Bullish' or spike.direction == 'UP':
                if bar['high'] >= (target - buffer):
                    hit = True
            elif spike.direction == 'Bearish' or spike.direction == 'DN':
                if bar['low'] <= (target + buffer):
                    hit = True
            
            if hit:
                spike.hit = True
                spike.hit_date = bar['date']
                spike.hit_age = (bar['date'] - spike_date).days
                found_hit = True
                updated_count += 1
                break
        
        if not found_hit:
            spike.hit = False
            spike.hit_date = None
            spike.hit_age = None

    try:
        session.commit()
        print(f"Successfully backfilled {updated_count} hits for NVDA.")
    except Exception as e:
        session.rollback()
        print(f"Error during commit: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    backfill_nvda_hits()
