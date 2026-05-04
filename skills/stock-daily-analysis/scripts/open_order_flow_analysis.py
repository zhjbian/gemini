#!/usr/local/bin/python3
"""
OPEN ORDER FLOW ANALYSIS - DATA PROVIDER (MIRROR ORIGINAL)
"""
import sys
import os
import argparse
from datetime import datetime, date, timedelta

PROJECT_ROOT = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading"
sys.path.append(os.path.join(PROJECT_ROOT, "PyTools"))
from db_connection import DBConn
from models import OrderFlowBigTrade
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
            
    with DBConn().session() as session:
        # EXACT ORIGINAL QUERY
        trades = session.query(OrderFlowBigTrade).filter(
            OrderFlowBigTrade.ticker == ticker,
            OrderFlowBigTrade.volume >= 1000000,
            OrderFlowBigTrade.trading_hour.in_(['RTH', 'RTH_FH']),
            OrderFlowBigTrade.t_date >= cutoff_date
        ).order_by(OrderFlowBigTrade.t_date.desc(), OrderFlowBigTrade.trade_time.desc()).all()
        
        if not trades: return

        md = "| 日期 | 时间 | 价格 | 方向 | 侧向 (TrueSide) | 成交量 | 期权绑定 |\n"
        md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        for t in trades:
            side_text = t.side.value if hasattr(t.side, 'value') else t.side
            tied_char = "✓" if t.tied_options else ""
            md += f"| {t.t_date} | {t.trade_time.strftime('%H:%M')} | ${t.price:.2f} | {side_text} | {t.true_side} | {t.volume/1e6:.1f}M | {tied_char} |\n"
        print(md)

if __name__ == "__main__":
    main()
