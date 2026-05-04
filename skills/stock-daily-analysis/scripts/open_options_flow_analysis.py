import sys
import os
import json
from datetime import datetime, timedelta, date

PROJECT_ROOT = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading"
sys.path.append(os.path.join(PROJECT_ROOT, "PyTools"))
sys.path.append(os.path.join(PROJECT_ROOT, "bbt_data_web"))

from db_connection import DBConn
from models import OptionFlow
from py_lib.bb_date_time import BBDateTime

def main():
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "TSLA"
    min_premium = 25.0
    
    with DBConn().session() as session:
        cutoff_date = date.today() - timedelta(days=40)
        sig_flows = session.query(OptionFlow).filter(
            OptionFlow.ticker == ticker,
            OptionFlow.premium >= min_premium,
            OptionFlow.is_summary == False,
            OptionFlow.transac_date >= cutoff_date
        ).all()
        
        if not sig_flows:
            print("[]")
            return

        sprd_ids = [f.sprd_id for f in sig_flows if f.sprd_id]
        all_flows = []
        if sprd_ids:
            spread_legs = session.query(OptionFlow).filter(
                OptionFlow.sprd_id.in_(sprd_ids)
            ).all()
            single_flows = [f for f in sig_flows if not f.sprd_id]
            all_flows = spread_legs + single_flows
        else:
            all_flows = sig_flows

        all_flows.sort(key=lambda x: (x.transac_date, x.transac_time), reverse=True)
        
        results = []
        for f in all_flows:
            exp_date = BBDateTime.get_date_obj_from_diff_formats(f.expiration)
            dte = (exp_date - date.today()).days if exp_date else -1
            if dte < 0: continue
            
            results.append({
                "date": str(f.transac_date),
                "time": f.transac_time.strftime("%H:%M"),
                "contract": f.contract,
                "price": float(f.price),
                "qty": int(f.qty),
                "premium": float(f.premium),
                "dte": dte,
                "spot": float(f.spot_price) if f.spot_price else 0.0,
                "sentiment": f.sentiment,
                "type": f.exec_type or "",
                "sprd_id": f.sprd_id
            })
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
