"""
REDUNDANT SPIKE CONSOLIDATION UTILITY
=====================================

PURPOSE:
--------
This script merges multiple institutional spikes that occur near each other into a single 
high-fidelity "Master Signal." It solves the issue of inflated signal counts and skewed 
backtest results caused by rapid-fire institutional filling activity.

MERGE CONDITIONS:
-----------------
The script consolidates signals based on the following rules:
1.  Grouping: Signals must share the same [Date], [Ticker], [Spot Price], and [Session].
2.  Proximity: Target Prices must be within a specific dollar range of each other (default: $1.00).
3.  Aggregation: 
    - The record with the largest volume in the cluster becomes the "Anchor."
    - Total Volume, Total Premium, and Total Trade Count are summed across all cluster records.
    - The Anchor is updated with these totals and marked with ",merged(N)" in the note field.

CLEANUP SCOPE:
--------------
- Only the `spike_mw_agg` table is sanitized (redundant rows deleted).
- The raw `spike_mw` table is NOT modified to preserve the transaction-level audit trail.

USAGE:
------
- Preview: python3 merge_redundant_spikes.py --ticker TSLA --session RTH
- Execute: python3 merge_redundant_spikes.py --ticker TSLA --session RTH --execute
- Adjust Range: python3 merge_redundant_spikes.py --range 5.0 --execute
"""
import sys
import argparse
from datetime import datetime
from collections import defaultdict

# Add paths for project models and DB connection
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
try:
    from db_connection import DBConn
    from sqlalchemy import text
except ImportError:
    print("Error: Could not import DBConn. Ensure you are running this from the correct environment.")
    sys.exit(1)

def merge_spikes(ticker=None, date_str=None, threshold_price=1.0, dry_run=True, session_type='PM'):
    """
    Merges redundant institutional spikes occurring at the same spot price
    and within a physical price range ($1.00) into a single high-conviction signal.
    Sums up volumes, premiums, and trade counts.
    """
    with DBConn().session() as session:
        # 1. Fetch relevant spikes
        where_clauses = []
        params = {}
        
        if session_type and session_type != 'all':
            where_clauses.append("trading_hour = :sess")
            params['sess'] = session_type
        
        if ticker:
            where_clauses.append("ticker = :ticker")
            params['ticker'] = ticker.upper()
        if date_str:
            where_clauses.append("t_date = :t_date")
            params['t_date'] = date_str

        query = f"""
            SELECT id, t_date, ticker, spot_price, target_price, volume_agg, premium_agg, note, time, trade_count
            FROM spike_mw_agg
            WHERE {' AND '.join(where_clauses) if where_clauses else '1=1'}
            ORDER BY t_date, ticker, spot_price, target_price
        """
        
        records = session.execute(text(query), params).fetchall()
        
        if not records:
            print(f"No {session_type} spikes found matching the criteria.")
            return

        print(f"=== {'[DRY RUN] ' if dry_run else ''}Processing {len(records)} records for merging ===")

        # 2. Group by (Date, Ticker, SpotPrice)
        groups = defaultdict(list)
        for r in records:
            key = (r[1], r[2], float(r[3]))
            groups[key].append(r)

        merges_performed = 0
        total_rows_cleaned = 0

        for key, group_records in groups.items():
            t_date, tkr, spot = key
            
            # Sort by target_price to cluster correctly
            sorted_records = sorted(group_records, key=lambda x: float(x[4]))
            
            i = 0
            while i < len(sorted_records):
                cluster = [sorted_records[i]]
                base_target = float(sorted_records[i][4])
                
                j = i + 1
                while j < len(sorted_records):
                    next_target = float(sorted_records[j][4])
                    if abs(next_target - base_target) <= threshold_price:
                        cluster.append(sorted_records[j])
                        j += 1
                    else:
                        break
                
                # Advance i to the start of the next potential cluster
                i = j
                
                if len(cluster) > 1:
                    # MERGE CLUSTER
                    # Find Master (Anchor) - record with max volume
                    master = max(cluster, key=lambda x: int(x[5]))
                    others = [r for r in cluster if r[0] != master[0]]
                    
                    total_vol = sum(int(r[5]) for r in cluster)
                    total_prem = sum(float(r[6]) for r in cluster if r[6] is not None)
                    total_count = sum(int(r[9]) for r in cluster if r[9] is not None)
                    merge_count = len(cluster)
                    
                    old_note = str(master[7]) if master[7] else ""
                    # append ,merged(N)
                    new_note = (old_note + f",merged({merge_count})").strip(",")
                    
                    print(f"Merging {merge_count} spikes for {tkr} at {t_date} (Spot: {spot:.2f}, Target ~{float(master[4]):.2f})")
                    print(f"  - New Total Volume: {total_vol}")
                    print(f"  - New Total Count: {total_count}")
                    
                    if not dry_run:
                        # Update Master
                        session.execute(text("""
                            UPDATE spike_mw_agg 
                            SET volume_agg = :vol, premium_agg = :prem, trade_count = :count, note = :note
                            WHERE id = :id
                        """), {'vol': total_vol, 'prem': total_prem, 'count': total_count, 'note': new_note, 'id': master[0]})
                        
                        # Delete Others
                        other_ids = [r[0] for r in others]
                        session.execute(text("DELETE FROM spike_mw_agg WHERE id IN :ids"), {'ids': other_ids})
                        
                        merges_performed += 1
                        total_rows_cleaned += len(others)

        if not dry_run:
            session.commit()
            print(f"\nSuccess: Performed {merges_performed} merges, cleaned {total_rows_cleaned} redundant rows.")
        else:
            print(f"\nDry run complete. Use --execute to perform the merge.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge redundant spikes within price proximity.")
    parser.add_argument("--ticker", help="Target ticker")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD)")
    parser.add_argument("--session", default='PM', choices=['PM', 'RTH', 'AH', 'all'], help="Session type (default: PM)")
    parser.add_argument("--range", type=float, default=1.0, help="Price range for merging (default: $1.00)")
    parser.add_argument("--execute", action="store_true", help="Actually perform the merge")
    
    args = parser.parse_args()
    
    merge_spikes(
        ticker=args.ticker, 
        date_str=args.date, 
        threshold_price=args.range, 
        dry_run=not args.execute,
        session_type=args.session
    )
