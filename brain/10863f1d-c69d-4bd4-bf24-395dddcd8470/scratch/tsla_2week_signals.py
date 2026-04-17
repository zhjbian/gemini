import sys
import subprocess
import datetime
import json
import pandas as pd

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def get_tsla_signals(lookback_days=14):
    end_date = datetime.date(2026, 4, 15)
    start_date = end_date - datetime.timedelta(days=lookback_days)
    
    ticker = "TSLA"
    all_signals = []
    
    print(f"Gathering signals for {ticker} from {start_date} to {end_date}...")
    
    current_date = start_date
    while current_date <= end_date:
        d_str = current_date.strftime("%Y-%m-%d")
        print(f"Processing {d_str}...")
        
        # 1. Spikes
        spike_cmd = f"python3 /Users/zhijiebian/.gemini/skills/spike-analysis/scripts/fetch_spikes.py {ticker} {d_str}"
        spike_out = run_command(spike_cmd)
        if spike_out and not spike_out.startswith("Error"):
            try:
                data = json.loads(spike_out)
                for s in data.get("verified_spikes", []):
                    # Filter: PM 10+, RTH 50+
                    vol = s.get("volume_agg", 0)
                    hour = s.get("trading_hour", "")
                    if (hour == "PM" and vol >= 10) or (hour == "RTH" and vol >= 50):
                        all_signals.append({
                            "date": d_str,
                            "time": s.get("time"),
                            "type": f"Spike ({hour})",
                            "dir": s.get("direction"),
                            "vol": vol,
                            "spot": s.get("spot_price"),
                            "target": s.get("target_price"),
                            "confidence": "High (Tier 1)" if (hour == "PM" and vol >= 10) or (hour == "RTH" and vol >= 50) else "Medium"
                        })
            except: pass

        # 2. Options
        opts_cmd = f"python3 /Users/zhijiebian/.gemini/skills/options-flow-analysis/scripts/fetch_options_flow.py {ticker} {d_str}"
        opts_out = run_command(opts_cmd)
        if opts_out and not opts_out.startswith("Error"):
            try:
                data = json.loads(opts_out)
                for t in data.get("option_trades", []):
                    legs = t.get("legs", [])
                    total_prem = t.get("total_premium_in_trade", 0)
                    has_d_auto = any(leg.get("normalized_code") == "D.AUTO" for leg in legs)
                    
                    if has_d_auto and total_prem >= 5:
                        all_signals.append({
                            "date": d_str,
                            "time": legs[0].get("trade_time"),
                            "type": "Options Flow (D.AUTO)",
                            "dir": legs[0].get("sentiment_type"),
                            "vol": total_prem,
                            "premium": f"${total_prem}M",
                            "confidence": "High (D.AUTO >= 5M)"
                        })
                    elif total_prem >= 10:
                         all_signals.append({
                            "date": d_str,
                            "time": legs[0].get("trade_time"),
                            "type": "Options Flow (Big)",
                            "dir": legs[0].get("sentiment_type"),
                            "vol": total_prem,
                            "premium": f"${total_prem}M",
                            "confidence": "Medium (>= 10M)"
                        })
            except: pass

        # 3. Dark Pool / Big Trades (via stock-daily-analysis fetcher)
        bbt_cmd = f"python3 /Users/zhijiebian/.gemini/skills/stock-daily-analysis/scripts/get_bbt_data.py {ticker} {d_str}"
        bbt_out = run_command(bbt_cmd)
        if bbt_out and "DARK POOL" in bbt_out:
            lines = bbt_out.split("\n")
            for line in lines:
                if "Time:" in line:
                    # Time: 12:47 | Type: Signature | Price: 775.22 | Size: 1.2M | Notional: 930.26
                    try:
                        pts = line.split("|")
                        ts = pts[0].split(":")[1].strip() + ":" + pts[0].split(":")[2].strip()
                        notional = float(line.split("Notional:")[1].strip())
                        if notional >= 100: # High confidence floor for DP
                            all_signals.append({
                                "date": d_str,
                                "time": ts,
                                "type": "Dark Pool",
                                "vol": notional,
                                "premium": f"${notional}M",
                                "confidence": "High (>= 100M)"
                            })
                    except: pass
        
        current_date += datetime.timedelta(days=1)
    
    return all_signals

if __name__ == "__main__":
    signals = get_tsla_signals(14)
    print("\n--- CONSOLIDATED TSLA SIGNALS (LAST 2 WEEKS) ---")
    if signals:
        # Sort signals descending by date and time (handling None time)
        signals.sort(key=lambda x: (x['date'], x['time'] or "00:00:00"), reverse=True)
        for s in signals:
            t = s.get('time') or "??:??:??"
            print(f"{s['date']} {t} | {s['type']:<18} | {str(s.get('dir')):<14} | Vol/Prem: {str(s.get('vol', '-')):<6} | {s['confidence']}")
    else:
        print("No high confidence signals found.")
