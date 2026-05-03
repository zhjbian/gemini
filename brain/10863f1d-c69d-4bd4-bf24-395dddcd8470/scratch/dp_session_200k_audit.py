import sys
import os
import pandas as pd
import yfinance as yf
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine

# Path Setup
BASE_DIR = '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading'
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'bbt_data_web'))

from bbt_data_app import bbt_data_app
from db_connection_legacy import db
from models import DarkPoolTradeAgg

def evaluate_session_200k(ticker='TSLA'):
    print(f"Auditing Session Quality for {ticker} (>= 200k Shares)...")
    
    start_date = date.today() - timedelta(days=365)
    
    with bbt_data_app.app_context():
        # Query aggregated trades >= 200,000 shares
        query = db.session.query(DarkPoolTradeAgg).filter(
            DarkPoolTradeAgg.ticker == ticker,
            DarkPoolTradeAgg.trade_date >= start_date,
            DarkPoolTradeAgg.size >= 200000
        ).order_by(DarkPoolTradeAgg.trade_date.asc())
        
        trades = query.all()
        if not trades:
            print("No trades found.")
            return
            
        # Market Data Fetch
        df_price = yf.download(ticker, start=start_date - timedelta(days=10), end=date.today() + timedelta(days=2), auto_adjust=True)
        if isinstance(df_price.columns, pd.MultiIndex): df_price.columns = df_price.columns.get_level_values(0)
        df_price.index = df_price.index.normalize()

        results = []
        target_pct = 5.0

        for row in trades:
            price_start = float(row.price)
            side = row.side
            eval_start = pd.Timestamp(row.trade_date)
            # Eval from Day 1 to Day 20
            eval_window = df_price[df_price.index > eval_start].head(40)
            
            hit_20d = 0
            days_to_hit = None
            mae = 0
            
            if not eval_window.empty and side:
                if side == "Buy":
                    target = price_start * (1 + target_pct/100)
                    hb = eval_window[eval_window['High'] >= target]
                    if not hb.empty:
                        # Count trading bars in window
                        days_to_hit = len(df_price[(df_price.index > eval_start) & (df_price.index <= hb.index[0])])
                        if days_to_hit <= 20: hit_20d = 1
                        pre_hit = eval_window.loc[:hb.index[0]]
                        mae = min(0, (pre_hit['Low'].min() - price_start) / price_start * 100)
                    else:
                        mae = min(0, (eval_window['Low'].min() - price_start) / price_start * 100)
                else: # Sell
                    target = price_start * (1 - target_pct/100)
                    hb = eval_window[eval_window['Low'] <= target]
                    if not hb.empty:
                        days_to_hit = len(df_price[(df_price.index > eval_start) & (df_price.index <= hb.index[0])])
                        if days_to_hit <= 20: hit_20d = 1
                        pre_hit = eval_window.loc[:hb.index[0]]
                        mae = min(0, (price_start - pre_hit['High'].max()) / price_start * 100)
                    else:
                        mae = min(0, (price_start - eval_window['High'].max()) / price_start * 100)
            
            results.append({
                'session': row.trading_hour,
                'hit': hit_20d,
                'days': days_to_hit,
                'mae': mae
            })

        df = pd.DataFrame(results)
        
        summary = df.groupby('session').agg({
            'hit': ['count', 'mean'],
            'days': 'mean',
            'mae': 'mean'
        })
        summary.columns = ['Count', 'Hit Rate', 'Avg Days', 'MAE DD']
        summary['Hit Rate'] = (summary['Hit Rate'] * 100).round(1).astype(str) + '%'
        summary['Avg Days'] = summary['Avg Days'].round(1)
        summary['MAE DD'] = summary['MAE DD'].round(2).astype(str) + '%'
        
        print("\n=== SESSION PERFORMANCE (200K FLOOR) ===")
        print(summary)
        
        report = "# TSLA Dark Pool Session Audit: 200k Share Floor\n\n"
        report += "Loosening the institutional floor to 200,000 shares to explore tactical conviction.\n\n"
        report += summary.to_markdown() + "\n\n"
        
        out_path = '/Users/zhijiebian/.gemini/skills/dark-pool-analysis/references/backtest/TSLA_DP_session_audit_200k.md'
        with open(out_path, 'w') as f:
            f.write(report)
        print(f"\nAudit saved to {out_path}")

if __name__ == '__main__':
    evaluate_session_200k('TSLA')
