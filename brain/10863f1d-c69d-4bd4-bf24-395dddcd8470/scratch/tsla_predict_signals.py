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

def evaluate_sentiment(legs):
    bullish_prem = 0
    bearish_prem = 0
    for leg in legs:
        prem = leg.get("premium", 0)
        sent = leg.get("sentiment", "Neutral")
        if sent == "Bullish": bullish_prem += prem
        elif sent == "Bearish": bearish_prem += prem
    
    total = bullish_prem + bearish_prem
    if total == 0: return "Neutral"
    
    # If one side is significantly dominant (>60% of total premium), use that direction.
    # Otherwise, it's a balanced 'Churn' trade.
    if bullish_prem > bearish_prem * 1.5: return "Bullish"
    if bearish_prem > bullish_prem * 1.5: return "Bearish"
    return "Neutral/Churn"

def get_tsla_prediction_data(lookback_days=7, mode="predict"):
    # Today is 2026-04-15 based on metadata
    today = datetime.date(2026, 4, 15)
    start_date = today - datetime.timedelta(days=lookback_days)
    
    ticker = "TSLA"
    signals = []
    
    # 1. Fetch current price to check if targets were hit
    tech_cmd = f"python3 /Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts/get_tech_data.py {ticker} {today.strftime('%Y-%m-%d')}"
    latest_price_out = run_command(tech_cmd)
    
    current_price = 0
    if latest_price_out:
        for line in latest_price_out.split("\n"):
            if "Close:" in line:
                current_price = float(line.split("Close:")[1].strip())
    
    print(f"Current Price: {current_price} | Mode: {mode.upper()}")
    
    current_date = start_date
    while current_date <= today:
        d_str = current_date.strftime("%Y-%m-%d")
        
        # A. Spikes
        spike_cmd = f"python3 /Users/zhijiebian/.gemini/skills/spike-analysis/scripts/fetch_spikes.py {ticker} {d_str}"
        spike_out = run_command(spike_cmd)
        if spike_out and not spike_out.startswith("Error"):
            try:
                data = json.loads(spike_out)
                for s in data.get("verified_spikes", []):
                    vol = s.get("volume_agg", 0)
                    hour = s.get("trading_hour", "")
                    target = s.get("target_price", 0)
                    direction = s.get("direction", "")
                    
                    if (hour == "PM" and vol >= 10) or (hour == "RTH" and vol >= 50):
                        is_hit = False
                        if direction == "UP" and current_price >= target: is_hit = True
                        if direction == "DN" and current_price <= target: is_hit = True
                        
                        # In Predict mode, only keep active. In Backtest, keep all.
                        if mode == "backtest" or not is_hit:
                            signals.append({
                                "date": d_str, "time": s.get("time"), "type": f"Spike ({hour})",
                                "dir": direction, "vol": vol, "target": target, "status": "HIT" if is_hit else "Active"
                            })
            except: pass

        # B. Options
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
                    
                    is_high_importance = False
                    if legs_count == 1 and has_d_auto and total_prem >= 5: is_high_importance = True
                    if legs_count > 1 and max_leg_prem >= 25: is_high_importance = True
                    
                    if is_high_importance:
                        # Holistic Sentiment Evaluation
                        final_dir = evaluate_sentiment(legs)
                        
                        # Find the max expiry across all legs to see if the trade is still 'active'
                        max_expiry_date = None
                        for leg in legs:
                            ex_str = leg.get("expiration")
                            if ex_str:
                                try:
                                    try:
                                        edate = datetime.datetime.strptime(ex_str, "%Y-%m-%d").date()
                                    except:
                                        edate = datetime.datetime.strptime(ex_str, "%b %d, %Y").date()
                                    if not max_expiry_date or edate > max_expiry_date:
                                        max_expiry_date = edate
                                except: pass
                        
                        is_expired = max_expiry_date and max_expiry_date < today
                        
                        # In Predict mode, only keep active. In Backtest, keep all.
                        if mode == "backtest" or not is_expired:
                            signals.append({
                                "date": d_str, "time": legs[0].get("transac_time"), "type": "Options Flow",
                                "dir": final_dir, "vol": total_prem, "status": "EXPIRED" if is_expired else "Active"
                            })
            except: pass
        current_date += datetime.timedelta(days=1)
    return signals

if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    mode = sys.argv[2] if len(sys.argv) > 2 else "predict"
    
    # Use system date or allow override
    today_override = sys.argv[3] if len(sys.argv) > 3 else "2026-04-16"
    today_dt = datetime.datetime.strptime(today_override, "%Y-%m-%d").date()
    
    # Re-passing today into the function logic
    def get_data_with_date(lookback, mode, custom_today):
        today = custom_today
        start_date = today - datetime.timedelta(days=lookback)
        ticker = "TSLA"
        signals = []
        
        # 1. Fetch current price
        tech_cmd = f"python3 /Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts/get_tech_data.py {ticker} {today.strftime('%Y-%m-%d')}"
        latest_price_out = run_command(tech_cmd)
        current_price = 0
        if latest_price_out:
            for line in latest_price_out.split("\n"):
                if "Close:" in line:
                    current_price = float(line.split("Close:")[1].strip())
        
        print(f"Current Price: {current_price} | Mode: {mode.upper()} | As of: {today}")
        
        current_date = start_date
        while current_date <= today:
            d_str = current_date.strftime("%Y-%m-%d")
            
            # A. Spikes
            spike_cmd = f"python3 /Users/zhijiebian/.gemini/skills/spike-analysis/scripts/fetch_spikes.py {ticker} {d_str}"
            spike_out = run_command(spike_cmd)
            if spike_out and not spike_out.startswith("Error"):
                try:
                    data = json.loads(spike_out)
                    for s in data.get("verified_spikes", []):
                        vol = s.get("volume_agg", 0)
                        hour = s.get("trading_hour", "")
                        target = s.get("target_price", 0)
                        direction = s.get("direction", "")
                        if (hour == "PM" and vol >= 10) or (hour == "RTH" and vol >= 50):
                            is_hit = False
                            if direction == "UP" and current_price >= target: is_hit = True
                            if direction == "DN" and current_price <= target: is_hit = True
                            if mode == "backtest" or not is_hit:
                                signals.append({
                                    "date": d_str, "time": s.get("time"), "type": f"Spike ({hour})",
                                    "dir": direction, "vol": vol, "target": target, "status": "HIT" if is_hit else "Active"
                                })
                except: pass

            # B. Options
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
                        if (legs_count == 1 and has_d_auto and total_prem >= 5) or (legs_count > 1 and max_leg_prem >= 25):
                            final_dir = evaluate_sentiment(legs)
                            max_expiry_date = None
                            for leg in legs:
                                ex_str = leg.get("expiration")
                                if ex_str:
                                    try:
                                        try: edate = datetime.datetime.strptime(ex_str, "%Y-%m-%d").date()
                                        except: edate = datetime.datetime.strptime(ex_str, "%b %d, %Y").date()
                                        if not max_expiry_date or edate > max_expiry_date: max_expiry_date = edate
                                    except: pass
                            is_expired = max_expiry_date and max_expiry_date < today
                            if mode == "backtest" or not is_expired:
                                signals.append({
                                    "date": d_str, "time": legs[0].get("transac_time"), "type": "Options Flow",
                                    "dir": final_dir, "vol": total_prem, "status": "EXPIRED" if is_expired else "Active"
                                })
                except: pass
            current_date += datetime.timedelta(days=1)
        return signals

    signals = get_data_with_date(days, mode, today_dt)
    print(f"\n--- TSLA SIGNALS (LOOKBACK: {days}d, MODE: {mode.upper()}) ---")
    if signals:
        for s in signals:
            print(json.dumps(s))
    else:
        print("No qualified institutional signals found.")
