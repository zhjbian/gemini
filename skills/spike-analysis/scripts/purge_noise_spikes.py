"""
PURGE NOISE SPIKES UTILITY
==========================

PURPOSE:
--------
This script identifies and purges "Machine Gun" noise clusters from the Institutional Spike database 
(ONLY from the spike_mw_agg table). These clusters are false positives typically generated 
during rapid Pre-Market or After-Hours trend moves where the detection baseline lags behind the price, 
resulting in hundreds of redundant signals at a single spot price.

NOISE IDENTIFICATION CONDITIONS:
--------------------------------
The script scans for clusters meeting the following criteria:
1.  Grouping: Signals must share the same [Date], [Ticker], [Spot Price], and occur within the same 
    [1-minute window] (e.g., 05:58:00 to 05:58:59).
2.  Threshold: The cluster must contain at least N records (default: 20) within that single minute.
3.  Session: Default targeting is the Pre-Market (PM) session, but AH and RTH can be specified.

CLEANUP SCOPE:
--------------
- Only the `spike_mw_agg` table is sanitized (redundant rows deleted).
- The raw `spike_mw` table is NOT modified to preserve the transaction-level audit trail.

USAGE:
------
- Preview: python3 purge_noise_spikes.py --ticker TSLA
- Execute: python3 purge_noise_spikes.py --ticker TSLA --execute
- Adjust Threshold: python3 purge_noise_spikes.py --threshold 50 --execute
"""
import sys
import argparse
from datetime import datetime

# Add paths for project models and DB connection
sys.path.append("/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web")
try:
    from db_connection import DBConn
    from sqlalchemy import text
except ImportError:
    print("Error: Could not import DBConn. Ensure you are running this from the correct environment.")
    sys.exit(1)

def purge_noise_spikes(ticker=None, threshold=20, dry_run=True, session_type='PM'):
    """
    Identifies and purges 'Machine Gun' noise clusters where baseline lag 
    causes excessive redundant signals during rapid price moves.
    """
    with DBConn().session() as session:
        # 1. Identify identifying groups safely
        where_clause = f"WHERE trading_hour = '{session_type}'"
        if ticker:
            where_clause += f" AND ticker = '{ticker.upper()}'"

        keys_query = f"""
            SELECT t_date, ticker, spot_price, DATE_FORMAT(time, '%%H:%%i') as min_key, COUNT(*) as cluster_size
            FROM spike_mw_agg
            {where_clause}
            GROUP BY t_date, ticker, spot_price, DATE_FORMAT(time, '%%H:%%i')
            HAVING cluster_size >= :threshold
            ORDER BY t_date DESC
        """
        
        clusters = session.execute(text(keys_query), {'threshold': threshold}).fetchall()
        
        if not clusters:
            print(f"No {session_type} noise clusters found meeting the threshold (>= {threshold}).")
            return

        print(f"=== {'[DRY RUN] ' if dry_run else ''}Identified Noise Clusters ===")
        print(f"{'Date':<12} | {'Ticker':<8} | {'Size':<6} | {'Spot':<8} | {'Minute'}")
        print("-" * 50)

        total_agg_deleted = 0
        
        for row in clusters:
            t_date, tkr, spot, min_key, size = row
            print(f"{str(t_date):<12} | {tkr:<8} | {size:<6} | {spot:<8.2f} | {min_key}")
            
            if not dry_run:
                # Delete from aggregated table
                agg_del = session.execute(text("""
                    DELETE FROM spike_mw_agg 
                    WHERE ticker = :tkr AND trading_hour = :sess 
                      AND t_date = :t_date AND spot_price = :spot 
                      AND DATE_FORMAT(time, '%%H:%%i') = :min_key
                """), {'tkr': tkr, 'sess': session_type, 't_date': t_date, 'spot': spot, 'min_key': min_key})
                total_agg_deleted += agg_del.rowcount
        
        if not dry_run:
            session.commit()
            print(f"\nSuccessfully purged noise stats:")
            print(f"  - Aggregated records: {total_agg_deleted}")
        else:
            print(f"\nDry run complete. Use --execute to perform the deletion.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Purge high-frequency noise clusters from Spike DB.")
    parser.add_argument("--ticker", help="Target specific ticker (e.g. TSLA)")
    parser.add_argument("--threshold", type=int, default=20, help="Min records/min to define a noise burst (default: 20)")
    parser.add_argument("--session", default='PM', choices=['PM', 'AH', 'RTH'], help="Session type (default: PM)")
    parser.add_argument("--execute", action="store_true", help="Actually perform the deletion (default: dry-run)")
    
    args = parser.parse_args()
    
    purge_noise_spikes(
        ticker=args.ticker, 
        threshold=args.threshold, 
        dry_run=not args.execute, 
        session_type=args.session
    )
