import sys
import os
import json
from datetime import datetime, timedelta, date

PROJECT_ROOT = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading"
sys.path.append(os.path.join(PROJECT_ROOT, "PyTools"))
sys.path.append(os.path.join(PROJECT_ROOT, "bbt_data_web"))

from db_connection import DBConn
from models import OrderFlowBigTrade

def main():
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "TSLA"
    with DBConn().session() as session:
        cutoff_date = date.today() - timedelta(days=30)
        trades = session.query(OrderFlowBigTrade).filter(
            OrderFlowBigTrade.ticker == ticker,
            OrderFlowBigTrade.volume >= 1000000,
            OrderFlowBigTrade.trading_hour.in_(['RTH', 'RTH_FH']),
            OrderFlowBigTrade.t_date >= cutoff_date
        ).order_by(OrderFlowBigTrade.t_date.desc(), OrderFlowBigTrade.trade_time.desc()).all()
        
        results = []
        for t in trades:
            results.append({
                "date": str(t.t_date),
                "time": t.trade_time.strftime("%H:%M"),
                "price": float(t.price),
                "side": t.side.value if hasattr(t.side, 'value') else t.side,
                "true_side": t.true_side,
                "size": int(t.volume),
                "total_val": float(t.premium),
                "tied": bool(t.tied_options)
            })
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
