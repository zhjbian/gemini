import sys
import os
import json
from datetime import datetime, timedelta, date
from sqlalchemy import and_, or_

PROJECT_ROOT = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading"
sys.path.append(os.path.join(PROJECT_ROOT, "PyTools"))
sys.path.append(os.path.join(PROJECT_ROOT, "bbt_data_web"))

from db_connection import DBConn
from models import SpikeMWAgg
def main():
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "TSLA"
    
    etfs = ['SPY', 'QQQ', 'IWM', 'DIA']
    volatile_techs = ['TSLA', 'NVDA', 'META', 'GOOGL']
    
    with DBConn().session() as session:
        cutoff_date = date.today() - timedelta(days=30)
        
        # Query all open spikes for the ticker in last 30 days
        spikes = session.query(SpikeMWAgg).filter(
            and_(
                SpikeMWAgg.ticker == ticker,
                SpikeMWAgg.hit == False,
                SpikeMWAgg.t_date >= cutoff_date,
                or_(SpikeMWAgg.is_prev_close == False, SpikeMWAgg.is_prev_close == None)
            )
        ).order_by(SpikeMWAgg.t_date.desc()).all()
        
        results = []
        for s in spikes:
            trading_hour = s.trading_hour
            volume = int(s.volume_agg) if s.volume_agg else 0
            is_dp = bool(s.is_dp) if s.is_dp else False
            
            # Check validity based on updated SKILL.md rules
            is_valid = False
            
            if ticker in etfs:
                # Path B: Macro ETFs
                if trading_hour == 'RTH' and volume >= 20:
                    is_valid = True
                elif trading_hour == 'PM':
                    min_pm_vol = 2 if ticker == 'QQQ' else 20
                    if volume >= min_pm_vol:
                        is_valid = True
                elif trading_hour == 'AH':
                    if is_dp or volume >= 5000:
                        is_valid = True
            else:
                # Path A: Individual Stocks (High-Beta/General)
                if trading_hour == 'RTH':
                    min_rth_vol = 50 if (ticker in volatile_techs or ticker == 'TSM') else 50
                    if volume >= min_rth_vol:
                        is_valid = True
                elif trading_hour == 'PM':
                    min_pm_vol = 2 if ticker == 'TSM' else 10
                    if volume >= min_pm_vol:
                        is_valid = True
                elif trading_hour == 'AH':
                    if volume >= 500 or is_dp:
                        is_valid = True
            
            if is_valid:
                results.append({
                    "date": str(s.t_date),
                    "hour": s.trading_hour,
                    "target": float(s.target_price),
                    "spot": float(s.spot_price) if s.spot_price else 0.0,
                    "change": float(s.price_change) if s.price_change else 0.0,
                    "vol": volume
                })
                
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
