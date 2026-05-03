import sys
import os
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime, time
import pytz
import yfinance as yf

sys.path.append('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading')
sys.path.append('/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web')

from db_connection_legacy import db
from models import DarkPoolTradeAgg
from bbt_data_app import bbt_data_app

def get_es_daily_for_ticker(ticker, n_days=365):
    start_date = date.today() - timedelta(days=n_days + 60)
    es_d = yf.download(ticker, start=start_date, interval='1d', progress=False)
    if isinstance(es_d.columns, pd.MultiIndex):
        es_d.columns = es_d.columns.droplevel(1)
    return es_d

def get_es_hourly_for_window(ticker, sig_date_obj, n_days=60):
    start_date = sig_date_obj - timedelta(days=30)
    end_date = sig_date_obj + timedelta(days=n_days + 30)
    if end_date > date.today() + timedelta(days=1):
        end_date = date.today() + timedelta(days=1)
        
    es_h = yf.download(ticker, start=start_date, end=end_date, interval='1h', progress=False)
    if isinstance(es_h.columns, pd.MultiIndex):
        es_h.columns = es_h.columns.droplevel(1)
    if not es_h.empty:
        es_h.index = es_h.index.tz_convert('UTC')
    return es_h

def run_backtest():
    ticker = 'TSLA'
    days_back = 365
    start_date = date.today() - timedelta(days=days_back)
    
    print(f"Fetching DarkPoolTradeAgg data for {ticker} since {start_date}...")
    with bbt_data_app.app_context():
        query = db.session.query(DarkPoolTradeAgg).filter(
            DarkPoolTradeAgg.ticker == ticker,
            DarkPoolTradeAgg.trade_date >= start_date
        )
        trades = query.all()
        
        if not trades:
            print("No aggregated trades found.")
            return
            
        data = []
        for t in trades:
            data.append({
                'trade_date': t.trade_date,
                'ticker': t.ticker,
                'price': t.price,
                'size': t.size,
                'side': t.side,
                'trading_hour': t.trading_hour,
                'trade_time': t.trade_time,
                'is_opex': t.is_opex
            })
        
    df = pd.DataFrame(data)
    print(f"Loaded {len(df)} aggregated Dark Pool trades.")
    
    # Sort chronologically
    df = df.sort_values(['trade_date', 'trade_time']).reset_index(drop=True)
    
    # Evaluate Engine
    es_d = get_es_daily_for_ticker(ticker, n_days=days_back)
    
    results = []
    
    for idx, row in df.iterrows():
        sig_date_obj = row['trade_date']
        t_time = row['trade_time']
        price_start = float(row['price'])
        contextual_side = row['side']
        
        if contextual_side not in ["Buy", "Sell"]:
            continue
            
        # Localize time
        sig_dt_naive = datetime.combine(sig_date_obj, t_time)
        tz_pacific = pytz.timezone('US/Pacific')
        sig_dt = tz_pacific.localize(sig_dt_naive).astimezone(pytz.UTC)
        
        eval_days = 60
        es_window = get_es_hourly_for_window(ticker, sig_date_obj, n_days=eval_days)
        if es_window.empty:
            continue
            
        sig_dt_floor = sig_dt.replace(minute=0, second=0, microsecond=0)
        eval_window = es_window.loc[sig_dt_floor:]
        if eval_window.empty:
            eval_window = es_window.loc[sig_dt:]
            if eval_window.empty:
                 continue
                 
        target_pct = 5.0
        
        # Evaluate Performance
        hit_20d = 0
        late_hit_40d = 0
        days_to_hit = None
        max_profit_40d = 0
        mae_drawdown = 0
        
        eval_window = eval_window.copy()
        eval_window['t_date_only'] = eval_window.index.normalize()
        unique_dates = sorted(eval_window['t_date_only'].unique())
        date_to_day_idx = {d: i + 1 for i, d in enumerate(unique_dates)}
        eval_window['trading_day'] = eval_window['t_date_only'].map(date_to_day_idx)
        
        # Limit to 40 trading days
        eval_40d = eval_window[eval_window['trading_day'] <= 40]
        if eval_40d.empty:
            continue
            
        if contextual_side == "Buy":
            target_price = price_start * (1 + target_pct/100)
            hit_bars = eval_40d[eval_40d['High'] >= target_price]
            
            if not hit_bars.empty:
                first_hit = hit_bars.iloc[0]
                days_to_hit = int(first_hit['trading_day'])
                if days_to_hit <= 20: 
                    hit_20d = 1
                else: 
                    late_hit_40d = 1
                
                # MAE: Max Adverse Excursion BEFORE target hit
                pre_hit_window = eval_40d.loc[:first_hit.name]
                low_point = pre_hit_window['Low'].min()
                mae_drawdown = min(0, (low_point - price_start) / price_start * 100)
            else:
                # Still unsuccessful: Max drawdown over entire 40d
                mae_drawdown = min(0, (eval_40d['Low'].min() - price_start) / price_start * 100)
            
            # Max Gain (Full window)
            max_profit_40d = (eval_40d['High'].max() - price_start) / price_start * 100
        else:
            target_price = price_start * (1 - target_pct/100)
            hit_bars = eval_40d[eval_40d['Low'] <= target_price]
            
            if not hit_bars.empty:
                first_hit = hit_bars.iloc[0]
                days_to_hit = int(first_hit['trading_day'])
                if days_to_hit <= 20: 
                    hit_20d = 1
                else: 
                    late_hit_40d = 1
                
                # MAE: Max Adverse Excursion BEFORE target hit (Price goes UP against Sell)
                pre_hit_window = eval_40d.loc[:first_hit.name]
                high_point = pre_hit_window['High'].max()
                mae_drawdown = min(0, (price_start - high_point) / price_start * 100)
            else:
                mae_drawdown = min(0, (price_start - eval_40d['High'].max()) / price_start * 100)
                    
            # Max Gain (Sell side: price goes down = profit)
            max_profit_40d = (price_start - eval_40d['Low'].min()) / price_start * 100
        
        results.append({
            'trade_date': row['trade_date'],
            'trading_hour': row['trading_hour'],
            'price': row['price'],
            'size': row['size'],
            'side': contextual_side,
            'hit_20d': hit_20d,
            'late_hit_40d': late_hit_40d,
            'days_to_hit': days_to_hit,
            'max_profit': max_profit_40d,
            'mae_drawdown': mae_drawdown,
            'is_opex': row['is_opex']
        })
        
    res_df = pd.DataFrame(results)
    
    if not res_df.empty:
        markdown = f"# TSLA Aggregated Dark Pool Backtest (Last 365 Days)\n\n"
        markdown += f"Source: `DarkPoolTradeAgg` (Side derived from True Intention Engine)\n\n"
        markdown += f"**Metric Notice**: Drawdown is calculated as **MAE (Maximum Adverse Excursion)**—the risk encountered only BEFORE the target is hit.\n\n"
        
        def get_vol_bucket(size):
            if size < 1000000: return "500k-1M"
            if size < 4000000: return "1M-4M"
            if size < 7000000: return "4M-7M"
            if size < 12000000: return "7M-12M"
            return ">12M"
            
        res_df['vol_bucket'] = res_df['size'].apply(get_vol_bucket)
        vol_order = ["500k-1M", "1M-4M", "4M-7M", "7M-12M", ">12M"]
        
        for hour_bucket in ['PM', 'RTH', 'AH']:
            markdown += f"## Trading Hour: {hour_bucket}\n"
            h_df = res_df[res_df['trading_hour'] == hour_bucket]
            
            if h_df.empty:
                markdown += "*No trades found.*\n\n"
                continue
            
            # Table Header
            markdown += "| Volume Tier | Signals | Hit Rate | Avg Days | Avg Profit | MAE Drawdown |\n"
            markdown += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
            
            found_any = False
            for vol_bucket in vol_order:
                g = h_df[h_df['vol_bucket'] == vol_bucket]
                if g.empty:
                    continue
                
                found_any = True
                total = len(g)
                hits = g['hit_20d'].sum()
                rate = hits / total * 100
                avg_profit = g['max_profit'].mean()
                avg_drawdown = g['mae_drawdown'].mean()
                avg_days = g[g['days_to_hit'].notnull()]['days_to_hit'].mean()
                
                markdown += f"| {vol_bucket} | {total} | {rate:.1f}% | {avg_days:.1f} | {avg_profit:.2f}% | {avg_drawdown:.2f}% |\n"
            
            if not found_any:
                markdown += "| N/A | 0 | 0.0% | - | 0.00% | 0.00% |\n"
            
            markdown += "\n"
                
        out_path = '/Users/zhijiebian/.gemini/skills/dark-pool-analysis/references/TSLA_DP_agg_backtest.md'
        with open(out_path, 'w') as f:
            f.write(markdown)
        print(f"Report saved to {out_path}")
        
        # 5. Export Detailed Bucket Reports (>=1M)
        export_dir = '/Users/zhijiebian/.gemini/skills/dark-pool-analysis/references/backtest/'
        os.makedirs(export_dir, exist_ok=True)
        
        for vol_bucket in ["1M-4M", "4M-7M", "7M-12M", ">12M"]:
            b_df = res_df[res_df['vol_bucket'] == vol_bucket].copy()
            if b_df.empty:
                continue
                
            b_df = b_df.sort_values('trade_date', ascending=False)
            
            b_md = f"# Detailed Backtest Report: {vol_bucket} Tier\n\n"
            b_md += f"| Date | Session | Side | Price | Result | Days | Profit | MAE DD |\n"
            b_md += f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            
            for _, row in b_df.iterrows():
                status = "✅ HIT" if row['hit_20d'] == 1 else "❌ FAIL"
                days = int(row['days_to_hit']) if pd.notnull(row['days_to_hit']) else "-"
                b_md += f"| {row['trade_date']} | {row['trading_hour']} | {row['side']} | {row['price']:.2f} | {status} | {days} | {row['max_profit']:.2f}% | {row['mae_drawdown']:.2f}% |\n"
                
            b_filename = f"TSLA_DP_details_{vol_bucket.replace('>', 'GT')}.md"
            with open(os.path.join(export_dir, b_filename), 'w') as f:
                f.write(b_md)
            print(f"Detailed bucket report saved: {b_filename}")
        print(markdown)
    else:
        print("No results to report.")

if __name__ == '__main__':
    run_backtest()
