#!/usr/local/bin/python3
"""
OPEN OPTIONS FLOW ANALYSIS - DATA PROVIDER (MIRROR ORIGINAL)
"""
import sys
import os
import argparse
from datetime import datetime, date, timedelta

PROJECT_ROOT = "/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading"
sys.path.append(os.path.join(PROJECT_ROOT, "PyTools"))
from db_connection import DBConn
from models import OptionFlow
from py_lib.bb_date_time import BBDateTime

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    args = parser.parse_args()
    
    ticker = args.ticker.upper()
    # 40 Trading Days Lookback (Original Logic)
    cutoff_date = date.today()
    days_found = 0
    while days_found < 40:
        cutoff_date -= timedelta(days=1)
        if BBDateTime.is_market_open_by_date(cutoff_date.strftime("%Y-%m-%d")):
            days_found += 1
    
    with DBConn().session() as session:
        # EXACT ORIGINAL QUERY
        flows = session.query(OptionFlow).filter(
            OptionFlow.ticker == ticker,
            OptionFlow.premium >= 25, # User adjusted to 25
            OptionFlow.is_summary == False,
            OptionFlow.transac_date >= cutoff_date
        ).order_by(OptionFlow.transac_date.desc(), OptionFlow.transac_time.desc()).all()
        
        if not flows: return
        
        md = "| 日期/时间 | 合约 | 价格 | 数量 | 权利金 | DTE | 情绪 | 类型 |\n"
        md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        for f in flows:
            # DTE calculation like original
            exp_date = BBDateTime.get_date_obj_from_diff_formats(f.expiration)
            dte = (exp_date - date.today()).days if exp_date else -1
            if dte < 0: continue
            
            # Using CORRECT FIELD NAMES from original script:
            # contract, price, qty, premium, sentiment, exec_type
            # Data from DB is already in Millions
            md += f"| {f.transac_date} {f.transac_time.strftime('%H:%M')} | {f.contract} | ${f.price:.2f} | {f.qty} | ${f.premium:.2f}M | {dte}d | {f.sentiment} | {f.exec_type or ''} |\n"
        print(md)

if __name__ == "__main__":
    main()
