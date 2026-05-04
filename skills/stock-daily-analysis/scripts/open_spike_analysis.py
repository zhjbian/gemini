#!/usr/local/bin/python3
"""
OPEN SPIKE ANALYSIS - DATA PROVIDER (MIRROR ORIGINAL)
"""
import sys
import os
import argparse
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_

PROJECT_ROOT = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading"
sys.path.append(os.path.join(PROJECT_ROOT, "PyTools"))
# Important: use legacy connection for SpikeMWAgg if that's what original used
try:
    from db_connection_legacy import get_new_session
except ImportError:
    from db_connection import DBConn
    def get_new_session(): return DBConn().session()

from models import SpikeMWAgg
from py_lib.bb_date_time import BBDateTime

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    args = parser.parse_args()
    
    ticker = args.ticker.upper()
    # 30 Trading Days Lookback (Original Logic)
    cutoff_date = date.today()
    days_found = 0
    while days_found < 30:
        cutoff_date -= timedelta(days=1)
        if BBDateTime.is_market_open_by_date(cutoff_date.strftime("%Y-%m-%d")):
            days_found += 1
    
    session = get_new_session()
    # EXACT ORIGINAL QUERY
    spikes = session.query(SpikeMWAgg).filter(
        and_(
            SpikeMWAgg.ticker == ticker,
            SpikeMWAgg.hit == False,
            SpikeMWAgg.volume_agg >= 15,
            SpikeMWAgg.trading_hour.in_(['RTH']) if ticker in ['SPY', 'QQQ'] else SpikeMWAgg.trading_hour.in_(['PM', 'RTH']),
            SpikeMWAgg.t_date >= cutoff_date,
            or_(SpikeMWAgg.is_prev_close == False, SpikeMWAgg.is_prev_close == None)
        )
    ).order_by(SpikeMWAgg.t_date.desc()).all()
    
    if not spikes: return
    
    md = "| 产生日期 | 时段 | 目标价格 | 现价 | 方向 | 成交量 |\n"
    md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
    for s in spikes:
        is_bull = s.target_price > s.spot_price if s.spot_price else True
        dir_char = "▲ BULL" if is_bull else "▼ BEAR"
        md += f"| {s.t_date} | {s.trading_hour} | ${s.target_price:.2f} | ${s.spot_price if s.spot_price else 'N/A'} | {dir_char} | {s.volume_agg} |\n"
    print(md)

if __name__ == "__main__":
    main()
