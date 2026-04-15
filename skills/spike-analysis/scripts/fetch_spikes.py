import sys
import json
import datetime
from decimal import Decimal

sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")

from sqlalchemy import func
from db_connection_legacy import get_global_session
from models import SpikeMWAgg
from tos_api.bb_tos import BBTOS

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, datetime.time):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

if len(sys.argv) < 3:
    print("Usage: python3 fetch_spikes.py <ticker> <date YYYY-MM-DD>")
    sys.exit(1)

ticker = sys.argv[1].upper()
target_date_str = sys.argv[2]
try:
    target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
except ValueError:
    print("Invalid date format. Use YYYY-MM-DD")
    sys.exit(1)

session = get_global_session()
bbtos = BBTOS()

output_data = {
    "ticker": ticker,
    "date": target_date_str,
    "daily_price_context": None,
    "verified_spikes": []
}

# Fetch daily price context
try:
    ohlc = bbtos.get_ohlc_daily(ticker, target_date_str)
    if ohlc:
        output_data["daily_price_context"] = ohlc
except Exception as e:
    output_data["daily_price_context"] = f"Error fetching OHLC: {e}"

# Determine gap threshold based on ticker type
etfs = ['SPY', 'QQQ', 'IWM', 'DIA']
price_gap = 0.01 if ticker in etfs else 0.02

# Query the high-fidelity SpikeMWAgg table
try:
    spikes = session.query(SpikeMWAgg).filter(
        SpikeMWAgg.ticker == ticker,
        SpikeMWAgg.t_date == target_date,
        (SpikeMWAgg.is_prev_close == False) | (SpikeMWAgg.is_prev_close == None),
        func.abs(SpikeMWAgg.price_change) >= price_gap
    ).order_by(SpikeMWAgg.time.asc()).all()

    for s in spikes:
        record = {
            "id": s.id,
            "time": s.time.strftime("%H:%M:%S") if isinstance(s.time, datetime.time) else str(s.time),
            "trading_hour": s.trading_hour,
            "direction": s.direction,
            "spot_price": float(s.spot_price) if s.spot_price else 0,
            "target_price": float(s.target_price) if s.target_price else 0,
            "price_change_pct": float(s.price_change) * 100 if s.price_change else 0,
            "volume_agg": int(s.volume_agg) if s.volume_agg else 0
        }
        output_data["verified_spikes"].append(record)
except Exception as e:
    output_data["error"] = str(e)

print(json.dumps(output_data, default=decimal_default, indent=2))
