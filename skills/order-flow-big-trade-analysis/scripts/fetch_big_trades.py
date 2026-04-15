#!/usr/local/bin/python3
"""
fetch_big_trades.py - Fetch and pre-aggregate ES/NQ big trade signals for a given date.

Usage:
  python3 fetch_big_trades.py <date YYYY-MM-DD>

Output: JSON with aggregated signals ready for AI classification.
"""
import sys
import json
import datetime
from datetime import time as dt_time
from decimal import Decimal

sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading")
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools")

from sqlalchemy import func
from db_connection_legacy import get_global_session
from models import OrderFlowBigTrade, OfBigTradeType, TradeSide


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, datetime.time):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def classify_period(trade_time):
    """Classify a trade_time into PM, FirstHour, RTH, or AH (Pacific Time)."""
    pm_end = dt_time(6, 30, 0)
    open_hour_end = dt_time(7, 30, 0)
    rth_end = dt_time(13, 0, 0)

    if trade_time < pm_end:
        return "PM"
    elif trade_time < open_hour_end:
        return "FirstHour"
    elif trade_time < rth_end:
        return "RTH"
    else:
        return "AH"


def normalize_volume(ticker, volume):
    """Normalize volume to ES-equivalent. NQ × 3 = ES-equiv."""
    if ticker.strip() == "NQ":
        return volume * 3
    return volume


if len(sys.argv) < 2:
    print("Usage: python3 fetch_big_trades.py <date YYYY-MM-DD>")
    sys.exit(1)

target_date_str = sys.argv[1]
try:
    target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
except ValueError:
    print("Invalid date format. Use YYYY-MM-DD")
    sys.exit(1)

session = get_global_session()

output_data = {
    "date": target_date_str,
    "tickers": ["ES", "NQ"],
    "signals": [],
    "raw_trade_count": 0,
    "discarded_low_conviction": 0
}

# Fetch all SingleTickBigTrade for ES/NQ on target date, off_price >= 0
try:
    trades = session.query(OrderFlowBigTrade).filter(
        OrderFlowBigTrade.t_date == target_date,
        OrderFlowBigTrade.type == OfBigTradeType.SingleTickBigTrade,
        OrderFlowBigTrade.ticker.in_(["ES", "NQ"]),
        OrderFlowBigTrade.off_price >= 0
    ).order_by(OrderFlowBigTrade.trade_time.asc()).all()

    output_data["raw_trade_count"] = len(trades)

    if not trades:
        print(json.dumps(output_data, default=decimal_default, indent=2))
        sys.exit(0)

    # Bucket trades by period
    buckets = {"PM": [], "FirstHour": [], "RTH": [], "AH": []}
    for t in trades:
        period = classify_period(t.trade_time)
        es_vol = normalize_volume(t.ticker, t.volume)
        side_str = "Buy" if "Buy" in str(t.side) else "Sell"
        buckets[period].append({
            "ticker": t.ticker.strip(),
            "time": t.trade_time,
            "side": side_str,
            "es_equiv_vol": es_vol,
            "price": float(t.price),
            "raw_volume": t.volume
        })

    discarded = 0

    # Process PM and FirstHour as combined signals
    for period in ["PM", "FirstHour"]:
        group = buckets[period]
        if not group:
            continue

        buy_vol = sum(t["es_equiv_vol"] for t in group if t["side"] == "Buy")
        sell_vol = sum(t["es_equiv_vol"] for t in group if t["side"] == "Sell")
        net_vol = buy_vol - sell_vol
        abs_vol = abs(net_vol)
        big_count = sum(1 for t in group if t["es_equiv_vol"] >= 500)

        if abs_vol == 0:
            continue

        direction = "Bullish" if net_vol > 0 else "Bearish"
        first_time = min(t["time"] for t in group)

        # Determine tier
        if period == "PM":
            if abs_vol > 1000:
                tier = "Tier 1"
            elif abs_vol >= 500:
                tier = "Tier 2"
            else:
                tier = "Low Conviction"
                discarded += 1
                continue
        else:  # FirstHour
            if abs_vol > 2000:
                tier = "Tier 1"
            elif abs_vol >= 1000:
                tier = "Tier 2"
            else:
                tier = "Low Conviction"
                discarded += 1
                continue

        output_data["signals"].append({
            "period": period,
            "tier": tier,
            "direction": direction,
            "es_equiv_volume": abs_vol,
            "buy_volume": buy_vol,
            "sell_volume": sell_vol,
            "big_trade_count": big_count,
            "total_trade_count": len(group),
            "first_trade_time": first_time.strftime("%H:%M:%S"),
            "tickers_involved": list(set(t["ticker"] for t in group))
        })

    # Process RTH and AH as individual signals
    for period in ["RTH", "AH"]:
        group = buckets[period]
        for t in group:
            es_vol = t["es_equiv_vol"]

            # Determine tier
            if period == "RTH":
                if es_vol >= 2000:
                    tier = "Tier 2"
                elif es_vol >= 1000:
                    tier = "Tier 2"
                elif es_vol >= 500:
                    tier = "Tier 2"
                else:
                    tier = "Low Conviction"
                    discarded += 1
                    continue
            else:  # AH
                if es_vol > 1000:
                    tier = "Tier 1"
                elif es_vol >= 500:
                    tier = "Tier 2"
                else:
                    tier = "Low Conviction"
                    discarded += 1
                    continue

            direction = "Bullish" if t["side"] == "Buy" else "Bearish"

            output_data["signals"].append({
                "period": period,
                "tier": tier,
                "direction": direction,
                "es_equiv_volume": es_vol,
                "buy_volume": es_vol if t["side"] == "Buy" else 0,
                "sell_volume": es_vol if t["side"] == "Sell" else 0,
                "big_trade_count": 1 if es_vol >= 500 else 0,
                "total_trade_count": 1,
                "first_trade_time": t["time"].strftime("%H:%M:%S"),
                "ticker": t["ticker"],
                "price": t["price"]
            })

    output_data["discarded_low_conviction"] = discarded

except Exception as e:
    output_data["error"] = str(e)

print(json.dumps(output_data, default=decimal_default, indent=2))
