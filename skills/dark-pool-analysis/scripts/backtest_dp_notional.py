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

def run_backtest_notional(ticker='TSLA', min_notional_b=1.0, lookback_days=365):
    print(f"Starting Notional-based Backtest for {ticker} (Min: ${min_notional_b}B)...")
    
    start_date = date.today() - timedelta(days=lookback_days)
    
    with bbt_data_app.app_context():
        # Query trades >= $1B (notional_value is in Millions)
        min_notional_m = min_notional_b * 1000
        query = db.session.query(DarkPoolTradeAgg).filter(
            DarkPoolTradeAgg.ticker == ticker,
            DarkPoolTradeAgg.trade_date >= start_date,
            DarkPoolTradeAgg.notional_value >= min_notional_m
        ).order_by(DarkPoolTradeAgg.trade_date.asc())
        
        trades = query.all()
        if not trades:
            print("No trades found matching criteria.")
            return

        print(f"Found {len(trades)} signals. Fetching market data...")
        
        # Market Data Fetch
        yf_ticker = ticker if ticker not in ['ES', 'NQ'] else (ticker + '=F')
        df_price = yf.download(yf_ticker, start=start_date - timedelta(days=10), end=date.today() + timedelta(days=2), auto_adjust=True)
        if df_price.empty:
            print("Failed to fetch market data.")
            return
            
        # Flatten MultiIndex if present (yfinance update compat)
        if isinstance(df_price.columns, pd.MultiIndex):
            df_price.columns = df_price.columns.get_level_values(0)
        df_price.index = df_price.index.normalize()

        results = []
        target_pct = 5.0

        for row in trades:
            price_start = float(row.price)
            trade_date = row.trade_date
            side = row.side # True Intention
            
            if not side: continue
            
            eval_start = pd.Timestamp(trade_date)
            # Evaluate from Day 1 to Day 40
            eval_window = df_price[df_price.index > eval_start].head(40)
            
            hit_20d = 0
            days_to_hit = None
            max_profit = 0
            mae_drawdown = 0
            
            if not eval_window.empty:
                if side == "Buy":
                    target = price_start * (1 + target_pct/100)
                    hit_bars = eval_window[eval_window['High'] >= target]
                    
                    if not hit_bars.empty:
                        first_hit = hit_bars.iloc[0]
                        # Count trading days
                        days_to_hit = len(df_price[(df_price.index > eval_start) & (df_price.index <= hit_bars.index[0])])
                        if days_to_hit <= 20: hit_20d = 1
                        
                        # MAE before hit
                        pre_hit = eval_window.loc[:hit_bars.index[0]]
                        mae_drawdown = min(0, (pre_hit['Low'].min() - price_start) / price_start * 100)
                    else:
                        mae_drawdown = min(0, (eval_window['Low'].min() - price_start) / price_start * 100)
                    
                    max_profit = (eval_window['High'].max() - price_start) / price_start * 100
                else:
                    target = price_start * (1 - target_pct/100)
                    hit_bars = eval_window[eval_window['Low'] <= target]
                    
                    if not hit_bars.empty:
                        first_hit = hit_bars.iloc[0]
                        days_to_hit = len(df_price[(df_price.index > eval_start) & (df_price.index <= hit_bars.index[0])])
                        if days_to_hit <= 20: hit_20d = 1
                        
                        # MAE before hit (Adverse is price going UP)
                        pre_hit = eval_window.loc[:hit_bars.index[0]]
                        mae_drawdown = min(0, (price_start - pre_hit['High'].max()) / price_start * 100)
                    else:
                        mae_drawdown = min(0, (price_start - eval_window['High'].max()) / price_start * 100)
                    
                    max_profit = (price_start - eval_window['Low'].min()) / price_start * 100
            
            results.append({
                'trade_date': trade_date,
                'trading_hour': row.trading_hour,
                'notional_b': row.notional_value / 1000,
                'side': side,
                'hit_20d': hit_20d,
                'days_to_hit': days_to_hit,
                'max_profit': max_profit,
                'mae_drawdown': mae_drawdown
            })

        res_df = pd.DataFrame(results)
        
        # Group by Notional Buckets
        def get_notional_bucket(val_b):
            if val_b < 1.5: return "$1.0B - $1.5B"
            if val_b < 2.0: return "$1.5B - $2.0B"
            if val_b < 5.0: return "$2.0B - $5.0B"
            if val_b < 8.0: return "$5.0B - $8.0B"
            return ">$8.0B"
            
        res_df['notional_bucket'] = res_df['notional_b'].apply(get_notional_bucket)
        bucket_order = ["$1.0B - $1.5B", "$1.5B - $2.0B", "$2.0B - $5.0B", "$5.0B - $8.0B", ">$8.0B"]
        
        report = f"# {ticker} Dark Pool Notional Backtest (Last 365 Days)\n\n"
        report += f"Focus: Signals >= ${min_notional_b}B Notional Value\n\n"
        report += f"| Notional Bucket | Signals | Hit Rate | Avg Days | Avg Profit | MAE Drawdown |\n"
        report += f"| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        
        for bucket in bucket_order:
            g = res_df[res_df['notional_bucket'] == bucket]
            if g.empty: continue
            
            total = len(g)
            hits = g['hit_20d'].sum()
            rate = hits / total * 100
            avg_days = g[g['days_to_hit'].notnull()]['days_to_hit'].mean()
            avg_profit = g['max_profit'].mean()
            avg_dd = g['mae_drawdown'].mean()
            
            report += f"| {bucket} | {total} | {rate:.1f}% | {avg_days:.1f} | {avg_profit:.2f}% | {avg_dd:.2f}% |\n"
            
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../references/TSLA_notional_backtest.md')
        with open(out_path, 'w') as f:
            f.write(report)
        print(f"Backtest complete. Report saved to {out_path}")
        
        # Detailed Reports by Bucket
        detail_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../references/backtest/')
        os.makedirs(detail_dir, exist_ok=True)
        
        for bucket in bucket_order:
            b_df = res_df[res_df['notional_bucket'] == bucket].copy()
            if b_df.empty: continue
            
            b_df = b_df.sort_values('trade_date', ascending=False)
            
            b_md = f"# Detailed Backtest Report: {bucket} Notional Tier\n\n"
            b_md += f"| Date | Session | Side | $B | Result | Days | Profit | MAE DD |\n"
            b_md += f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            
            for _, row in b_df.iterrows():
                status = "✅ HIT" if row['hit_20d'] == 1 else "❌ FAIL"
                days = int(row['days_to_hit']) if pd.notnull(row['days_to_hit']) else "-"
                b_md += f"| {row['trade_date']} | {row['trading_hour']} | {row['side']} | {row['notional_b']:.2f} | {status} | {days} | {row['max_profit']:.2f}% | {row['mae_drawdown']:.2f}% |\n"
                
            b_filename = f"TSLA_DP_notional_details_{bucket.replace('$', '').replace(' ', '_').replace('-', 'to').replace('>', 'GT')}.md"
            with open(os.path.join(detail_dir, b_filename), 'w') as f:
                f.write(b_md)
            print(f"Detailed bucket report saved: {b_filename}")

        print("\n" + report)

if __name__ == '__main__':
    run_backtest_notional('TSLA')
