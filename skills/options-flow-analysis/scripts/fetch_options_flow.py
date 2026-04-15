import sys
import json
import datetime
from decimal import Decimal

if len(sys.argv) < 3:
    print("Usage: python fetch_options_flow.py <ticker> <date YYYY-MM-DD>")
    sys.exit(1)

ticker = sys.argv[1].upper()
target_date_str = sys.argv[2]
try:
    target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
except ValueError:
    print("Invalid date format. Use YYYY-MM-DD")
    sys.exit(1)

sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")

from db_query import DbQuery
from PyTools.tos_api.bb_tos import BBTOS

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime.date, datetime.time)):
        return str(obj)
    raise TypeError

def main():
    # 1. Fetch OHLC string context using bb_tos
    daily_context = {}
    try:
        bb_tos_result = BBTOS.get_ohlc_daily(ticker, target_date_str)
        if bb_tos_result and "error" not in bb_tos_result:
            daily_context = bb_tos_result
            daily_context["date"] = target_date_str
    except Exception as e:
        print(f"Error fetching OHLC from TOS: {e}", file=sys.stderr)
        
    # 2. Fetch Options Flow using the new DbQuery method
    flows_dict_list = DbQuery.option_flow_query_for_analysis(ticker, target_date)

    # 3. Group by sprd_id
    grouped_trades = {}
    standalone_id_counter = 0

    for flow in flows_dict_list:
        sprd_id = flow.get("sprd_id")
        if not sprd_id:
            sprd_id = f"STANDALONE_{standalone_id_counter}"
            standalone_id_counter += 1
            
        if sprd_id not in grouped_trades:
            grouped_trades[sprd_id] = []
            
        code_str = flow.get("code") or ""
        # Normalize code (remove N. or D.)
        normalized_code = code_str
        if normalized_code.startswith("N.") or normalized_code.startswith("D."):
            normalized_code = normalized_code[2:]
            
        leg_desc = {
            "id": flow.get("id"),
            "transac_time": str(flow.get("transac_time")) if flow.get("transac_time") else None,
            "expiration": flow.get("expiration"),
            "strike": float(flow.get("strike")) if flow.get("strike") else None,
            "call_put": flow.get("call_put"),
            "price": float(flow.get("price")) if flow.get("price") else None,
            "qty": flow.get("qty"),
            "premium": float(flow.get("premium")) if flow.get("premium") else 0.0,
            "side": flow.get("side"),
            "sentiment": flow.get("sentiment"),
            "spot_price": float(flow.get("spot_price")) if flow.get("spot_price") else None,
            "dte": flow.get("dte"),
            "code": code_str,
            "normalized_code": normalized_code,
            "dir": flow.get("dir"),
            "action": flow.get("action")
        }
        grouped_trades[sprd_id].append(leg_desc)

    # Output structure
    output_data = {
        "ticker": ticker,
        "date": target_date_str,
        "daily_price_context": daily_context,
        "option_trades": []
    }
    
    for sprd_id, legs in grouped_trades.items():
        total_premium = sum(leg["premium"] for leg in legs)
        min_dte = min([leg["dte"] for leg in legs if leg["dte"] is not None], default=None)
        spot_price = legs[0]["spot_price"] if legs else None
        exec_time = legs[0]["transac_time"] if legs else None
        
        output_data["option_trades"].append({
            "sprd_id": sprd_id,
            "execution_time": exec_time,
            "spot_price_at_execution": spot_price,
            "total_premium_in_trade": total_premium,
            "min_dte": min_dte,
            "legs_count": len(legs),
            "legs": legs
        })

    print(json.dumps(output_data, default=decimal_default, indent=2))

if __name__ == "__main__":
    main()
