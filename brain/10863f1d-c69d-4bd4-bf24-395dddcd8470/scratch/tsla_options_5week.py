import sys
import subprocess
import datetime
import json

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def get_tsla_options_backtest(lookback_days=35):
    # Today is 2026-04-15 based on metadata
    today = datetime.date(2026, 4, 15)
    start_date = today - datetime.timedelta(days=lookback_days)
    
    ticker = "TSLA"
    signals = []
    
    current_date = start_date
    while current_date <= today:
        d_str = current_date.strftime("%Y-%m-%d")
        
        # Options
        opts_cmd = f"python3 /Users/zhijiebian/.gemini/skills/options-flow-analysis/scripts/fetch_options_flow.py {ticker} {d_str}"
        opts_out = run_command(opts_cmd)
        if opts_out and not opts_out.startswith("Error"):
            try:
                data = json.loads(opts_out)
                for t in data.get("option_trades", []):
                    legs = t.get("legs", [])
                    total_prem = t.get("total_premium_in_trade", 0)
                    legs_count = t.get("legs_count", 1)
                    has_d_auto = any(leg.get("normalized_code") == "D.AUTO" for leg in legs)
                    max_leg_prem = max(leg.get("premium", 0) for leg in legs) if legs else 0
                    
                    is_high_conf = False
                    # Rule 1: D.AUTO single leg >= 5M
                    if legs_count == 1 and has_d_auto and total_prem >= 5: is_high_conf = True
                    # Rule 2: Multi-leg Medium+ (Biggest leg >= 25M)
                    if legs_count > 1 and max_leg_prem >= 25: is_high_conf = True
                    
                    if is_high_conf:
                         signals.append({
                             "date": d_str, "time": legs[0].get("trade_time"), "type": "Options Flow",
                             "dir": legs[0].get("sentiment_type"), "vol": total_prem, 
                             "details": f"{legs_count} legs, max_leg: ${max_leg_prem}M",
                             "code": legs[0].get("normalized_code")
                         })
            except: pass
        current_date += datetime.timedelta(days=1)
    return signals

if __name__ == "__main__":
    days = 35
    signals = get_tsla_options_backtest(days)
    print(f"\n--- TSLA HISTORICAL OPTIONS (LOOKBACK: {days}d, MODE: BACKTEST) ---")
    if signals:
        for s in signals:
            print(json.dumps(s))
    else:
        print("No high-confidence options signals found.")
