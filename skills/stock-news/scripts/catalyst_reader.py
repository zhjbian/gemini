import json
import os
from datetime import datetime, timedelta

CALENDAR_PATH = "/Users/zhijiebian/Documents/Workplace/Data/TwitterNews/catalyst_calendar.json"

def get_upcoming_catalysts(window_days=10):
    if not os.path.exists(CALENDAR_PATH):
        return {"EARNINGS": [], "MACRO": []}

    try:
        with open(CALENDAR_PATH, 'r') as f:
            calendar = json.load(f)
        
        upcoming = {"EARNINGS": [], "MACRO": []}
        now = datetime.now()
        threshold = now + timedelta(days=window_days)

        # Process Earnings
        earnings_dict = calendar.get("EARNINGS", {})
        for ticker, info in earnings_dict.items():
            try:
                date_val = datetime.strptime(info['date'], '%Y-%m-%d')
                if now.date() <= date_val.date() <= threshold.date():
                    upcoming["EARNINGS"].append({
                        "ticker": ticker,
                        "date": info['date'],
                        "time": info.get('time', 'Unknown'),
                        "status": info.get('status', 'confirmed')
                    })
            except Exception as e:
                print(f"Error parsing earnings date for {ticker}: {e}")

        # Process Macro
        macro_list = calendar.get("MACRO", [])
        for event in macro_list:
            try:
                date_val = datetime.strptime(event['date'], '%Y-%m-%d')
                if now.date() <= date_val.date() <= threshold.date():
                    upcoming["MACRO"].append(event)
            except Exception as e:
                print(f"Error parsing macro date for {event.get('name')}: {e}")
        
        return upcoming
    except Exception as e:
        print(f"Error reading calendar: {e}")
        return {"EARNINGS": [], "MACRO": []}

if __name__ == "__main__":
    catalysts = get_upcoming_catalysts()
    print(f"--- UNIFIED CATALYST SWEEP (Next 10 Days) ---")
    
    if catalysts["MACRO"]:
        print(f"\n[MACRO GRAVITY]")
        for m in catalysts["MACRO"]:
            print(f"  - [{m['date']}] {m['name']}: {m['time']}")

    if catalysts["EARNINGS"]:
        print(f"\n[STOCK EARNINGS]")
        for e in catalysts["EARNINGS"]:
            print(f"  - [{e['date']}] {e['ticker']}: {e['time']} ({e['status']})")
    
    if not catalysts["MACRO"] and not catalysts["EARNINGS"]:
        print("No high-priority catalysts in the next 10 days.")
