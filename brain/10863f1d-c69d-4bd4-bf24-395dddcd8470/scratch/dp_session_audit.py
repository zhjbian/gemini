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

def evaluate_session_delta(ticker='TSLA'):
    print(f"Comparing Session Conviction for {ticker} (>= $1B Notional)...")
    
    start_date = date.today() - timedelta(days=365)
    
    with bbt_data_app.app_context():
        query = db.session.query(DarkPoolTradeAgg).filter(
            DarkPoolTradeAgg.ticker == ticker,
            DarkPoolTradeAgg.trade_date >= start_date,
            DarkPoolTradeAgg.notional_value >= 1000
        ).order_by(DarkPoolTradeAgg.trade_date.asc())
        
        trades = query.all()
        
        # Market Data Fetch
        df_price = yf.download(ticker, start=start_date - timedelta(days=10), end=date.today() + timedelta(days=2), auto_adjust=True)
        if isinstance(df_price.columns, pd.MultiIndex): df_price.columns = df_price.columns.get_level_values(0)
        df_price.index = df_price.index.normalize()

        results = []
        for row in trades:
            price_start = float(row.price)
            side = row.side
            eval_window = df_price[df_price.index > pd.Timestamp(row.trade_date)].head(40)
            
            hit = 0
            days = None
            if not eval_window.empty and side:
                if side == "Buy":
                    target = price_start * 1.05
                    hb = eval_window[eval_window['High'] >= target]
                    if not hb.empty:
                        days = len(df_price[(df_price.index > pd.Timestamp(row.trade_date)) & (df_price.index <= hb.index[0])])
                        if days <= 20: hit = 1
                else: # Sell
                    target = price_start * 0.95
                    hb = eval_window[eval_window['Low'] <= target]
                    if not hb.empty:
                        days = len(df_price[(df_price.index > pd.Timestamp(row.trade_date)) & (df_price.index <= hb.index[0])])
                        if days <= 20: hit = 1
            
            results.append({
                'session': row.trading_hour,
                'hit': hit,
                'days': days
            })

        df = pd.DataFrame(results)
        
        summary = df.groupby('session').agg({
            'hit': ['count', 'mean'],
            'days': 'mean'
        })
        summary.columns = ['Count', 'Hit Rate', 'Avg Days']
        summary['Hit Rate'] = (summary['Hit Rate'] * 100).round(1).astype(str) + '%'
        summary['Avg Days'] = summary['Avg Days'].round(1)
        
        print("\n=== SESSION PERFORMANCE COMPARISON ===")
        print(summary)
        
        report = "# Session conviction Analysis: PM/RTH vs AH (TSLA)\n\n"
        report += "Hypothesis: Intra-day (PM/RTH) prints are less frequent but more directional.\n\n"
        report += summary.to_markdown() + "\n\n"
        report += "### Conclusion:\n"
        if summary.loc['PM']['Avg Days'] < summary.loc['AH']['Avg Days']:
            report += "- **Velocity**: PM/RTH trades show higher urgency (shorter days to hit target).\n"
        
        out_path = '/Users/zhijiebian/.gemini/skills/dark-pool-analysis/references/TSLA_DP_session_audit.md'
        with open(out_path, 'w') as f:
            f.write(report)
        print(f"\nAudit saved to {out_path}")

if __name__ == '__main__':
    evaluate_session_delta('TSLA')
