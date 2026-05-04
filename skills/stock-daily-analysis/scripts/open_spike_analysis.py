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
    with DBConn().session() as session:
        cutoff_date = date.today() - timedelta(days=30)
        hour_filter = SpikeMWAgg.trading_hour.in_(['RTH']) if ticker in ['SPY', 'QQQ'] else SpikeMWAgg.trading_hour.in_(['PM', 'RTH'])
        
        spikes = session.query(SpikeMWAgg).filter(
            and_(
                SpikeMWAgg.ticker == ticker,
                SpikeMWAgg.hit == False,
                SpikeMWAgg.volume_agg >= 15,
                hour_filter,
                SpikeMWAgg.t_date >= cutoff_date,
                or_(SpikeMWAgg.is_prev_close == False, SpikeMWAgg.is_prev_close == None)
            )
        ).order_by(SpikeMWAgg.t_date.desc()).all()
        
        results = []
        for s in spikes:
            results.append({
                "date": str(s.t_date),
                "hour": s.trading_hour,
                "target": float(s.target_price),
                "spot": float(s.spot_price) if s.spot_price else 0.0,
                "change": float(s.price_change) if s.price_change else 0.0,
                "vol": int(s.volume_agg)
            })
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
