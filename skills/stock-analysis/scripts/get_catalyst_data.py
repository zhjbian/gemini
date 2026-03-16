import sys
import datetime
import requests
import urllib.parse
from dateutil import tz  # Requires python-dateutil

def get_market_catalysts(date_str):
    start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    end_date = start_date + datetime.timedelta(days=14)
    
    start_str_basic = start_date.strftime("%Y-%m-%d")
    end_str_basic = end_date.strftime("%Y-%m-%d")
    
    start_time_enc = urllib.parse.quote("T00:00:00.000-04:00")
    end_time_enc = urllib.parse.quote("T23:59:59.999-04:00")
    
    start_param = f"{start_str_basic}{start_time_enc}"
    end_param = f"{end_str_basic}{end_time_enc}"

    url = f"https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/occurrences?domain_id=1&limit=200&start_date={start_param}&end_date={end_param}&country_ids=5&importance=high"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0'
    }

    print(f"--- MARKET CATALYSTS ({start_str_basic} to {end_str_basic}) ---")
    print("\n[Economic Calendar - US High Impact]")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        event_dict = {}
        for ev in data.get('data', []):
            event_id = str(ev.get('event_id', ''))
            if event_id and event_id != '':
                event_dict[event_id] = ev
                
        occurrences = data.get('occurrences', [])
        
        if not occurrences:
             print("No major US economic events found in the given timeframe.")
        else:
             # Sort occurrences by time
             occurrences = sorted(occurrences, key=lambda x: x.get('occurrence_time', ''))
             
             from_zone = tz.tzutc()
             to_zone = tz.tzlocal()
             
             for occ in occurrences:
                 # Both 'data' array and 'occurrences' array should have 'event_id'.
                 # Convert to string to ensure safe matching
                 event_id = str(occ.get('event_id', ''))
                 ev_info = event_dict.get(event_id, {})
                 
                 # Look in different fields based on the API response structure
                 event_name = ev_info.get('event_translated')
                 if not event_name:
                     event_name = ev_info.get('short_name')
                 if not event_name:
                     event_name = ev_info.get('event_meta_title')
                 if not event_name:
                     event_name = ev_info.get('long_name')
                 if not event_name:
                     event_name = 'Unknown Event'
                 
                 occ_time_str = occ.get('occurrence_time', '')
                 
                 formatted_time = occ_time_str
                 if occ_time_str.endswith('Z'):
                     try:
                         dt_utc = datetime.datetime.strptime(occ_time_str, "%Y-%m-%dT%H:%M:%SZ")
                         dt_utc = dt_utc.replace(tzinfo=from_zone)
                         dt_local = dt_utc.astimezone(to_zone)
                         formatted_time = dt_local.strftime("%Y-%m-%d %H:%M")
                     except Exception:
                         formatted_time = occ_time_str[:10] + " " + occ_time_str[11:16] + " UTC"
                 
                 print(f"Date & Time: {formatted_time} | Event: {event_name} | Impact: High")
                 
    except Exception as e:
        print(f"Error fetching economic calendar from investing.com API: {e}")

def get_stock_catalysts(ticker, date_str):
    start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    end_date = start_date + datetime.timedelta(days=14)
    start_str_basic = start_date.strftime("%Y-%m-%d")
    end_str_basic = end_date.strftime("%Y-%m-%d")

    # Use Alpha Vantage Earnings Calendar free endpoint for stocks
    av_key = "NK2UFLEP5AJ3NODA"
    url = f"https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&symbol={ticker}&horizon=3month&apikey={av_key}"

    print(f"\n--- STOCK CATALYSTS: {ticker} ({start_str_basic} to {end_str_basic}) ---")
    print("\n[Earnings Calendar]")

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        # Alpha Vantage returns CSV
        lines = response.text.strip().split('\n')
        if len(lines) <= 1:
            print(f"No earnings scheduled for {ticker} in the fetched window.")
        else:
            headers = lines[0].split(',')
            found = False
            for line in lines[1:]:
                # symbol,name,reportDate,fiscalDateEnding,estimate,currency
                parts = line.split(',')
                if len(parts) >= 3:
                     # e.g., parts[2] = 2026-04-15
                     report_date_str = parts[2]
                     if start_str_basic <= report_date_str <= end_str_basic:
                         estimate = parts[4] if len(parts) > 4 else 'N/A'
                         print(f"Date: {report_date_str} | Expected EPS: {estimate}")
                         found = True
            
            if not found:
                 print(f"No earnings scheduled for {ticker} in the next 14 days.")

    except Exception as e:
         print(f"Error fetching earnings calendar from Alpha Vantage: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        target_date = datetime.datetime.now().strftime("%Y-%m-%d")
        print("Usage:")
        print("  python get_catalyst_data.py market <date YYYY-MM-DD>")
        print("  python get_catalyst_data.py stock <ticker> <date YYYY-MM-DD>")
    else:
        mode = sys.argv[1].lower()
        if mode == 'market':
             get_market_catalysts(sys.argv[2])
        elif mode == 'stock':
             if len(sys.argv) < 4:
                  print("Missing ticker and/or date")
                  sys.exit(1)
             get_stock_catalysts(sys.argv[2].upper(), sys.argv[3])
