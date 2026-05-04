import sys
import datetime
import requests
import urllib.parse
from dateutil import tz  # Requires python-dateutil

def get_investing_cal(date_str):
    # Determine the date range: start_date to start_date + 14 days
    start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    end_date = start_date + datetime.timedelta(days=14)
    
    start_str_basic = start_date.strftime("%Y-%m-%d")
    end_str_basic = end_date.strftime("%Y-%m-%d")
    
    # Needs to be roughly T00:00:00.000-04:00 (or -05:00, investing API is forgiving if it's generally correct)
    start_time_enc = urllib.parse.quote("T00:00:00.000-04:00")
    end_time_enc = urllib.parse.quote("T23:59:59.999-04:00")
    
    start_param = f"{start_str_basic}{start_time_enc}"
    end_param = f"{end_str_basic}{end_time_enc}"

    url = f"https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/occurrences?domain_id=1&limit=200&start_date={start_param}&end_date={end_param}&country_ids=5&importance=high"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.investing.com/',
        'Origin': 'https://www.investing.com',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'Priority': 'u=0'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # 'data' contains the event definitions with names
        event_dict = {}
        for ev in data.get('data', []):
            event_id = ev.get('event_id')
            if event_id:
                event_dict[event_id] = ev
                
        # 'occurrences' contains the specific times
        occurrences = data.get('occurrences', [])
        
        print(f"--- MARKET CATALYSTS ({start_str_basic} to {end_str_basic}) ---")
        print("\n[Economic Calendar - US High Impact]")
        
        if not occurrences:
             print("No major US economic events found in the given timeframe.")
        else:
             # Sort occurrences by time
             occurrences = sorted(occurrences, key=lambda x: x.get('occurrence_time', ''))
             
             # Timezone conversion: Investing returns UTC ('Z') - Convert to EST/EDT typical structure
             from_zone = tz.tzutc()
             to_zone = tz.tzlocal() # Or specifically tz.gettz('America/New_York')
             
             for occ in occurrences:
                 event_id = occ.get('event_id')
                 ev_info = event_dict.get(event_id, {})
                 
                 event_name = ev_info.get('event_translated', ev_info.get('short_name', 'Unknown Event'))
                 occ_time_str = occ.get('occurrence_time', '')
                 
                 # Format time nicely: 2026-03-18T18:00:00Z -> Local Time
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
        
if __name__ == "__main__":
    if len(sys.argv) < 2:
         # Default to today if no arg provided
         get_investing_cal(datetime.datetime.now().strftime("%Y-%m-%d"))
    else:
         get_investing_cal(sys.argv[1])
