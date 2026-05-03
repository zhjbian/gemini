import sys
import os
import pandas as pd

def format_hrs_days(total_hours):
    if total_hours is None or pd.isna(total_hours):
        return "-"
    hrs = int(round(total_hours))
    days = int(hrs // 24)
    return f"{hrs}({days})"

def analyze_bucket(period, vol_bucket):
    csv_path = os.path.expanduser("~/.gemini/skills/order-flow-analysis/references/backtest_results.csv")
    if not os.path.exists(csv_path):
        print(f"Error: Backtest results not found at {csv_path}. Please run backtest_big_trades.py first.")
        return

    df = pd.read_csv(csv_path)

    # Auto-detect column names
    from_col = 'es_start' if 'es_start' in df.columns else 'spy_start'
    to_col = 'es_target' if 'es_target' in df.columns else 'spy_target'
    label = 'ES' if 'es_start' in df.columns else 'SPY'
    
    # Filter for the specific bucket
    mask = (df['period'] == period) & (df['vol_bucket'] == vol_bucket)
    subset = df[mask].sort_values(by='date', ascending=False)

    if subset.empty:
        print(f"No historical data found for Bucket: {period} ({vol_bucket})")
        return

    # Helper for formatting rows
    def format_row(row):
        is_eval_pending = row.get('eval_status') == 1.0
        hit_emoji = "✅" if row['hit'] == 1.0 else "❌"
        if is_eval_pending and row['hit'] == 0.0:
            hit_emoji = "⏳"

        total_ct = int(row['total_count']) if not pd.isna(row.get('total_count')) else "-"
        big_ct = int(row['big_count']) if not pd.isna(row.get('big_count')) else "-"
        price_from = f"${row[from_col]:.2f}" if not pd.isna(row.get(from_col)) else "-"
        target_val = f"${row[to_col]:.2f}" if not pd.isna(row.get(to_col)) else "-"
        price_to = f"{target_val}*" if is_eval_pending else target_val
        
        hrs_hit = format_hrs_days(row.get('hrs_to_hit'))
        hrs_max = format_hrs_days(row.get('hrs_to_max'))
        time_str = str(row['time']).split('.')[0]
        
        return f"| {row['date']} | {time_str} | {row['side']} | {int(row['net_vol'])} | {total_ct} | {big_ct} | {price_from} | {price_to} | {hit_emoji} | {row['max_win_pct']:.2f}% | {hrs_hit} | {hrs_max} |"

    # Calculate statistics
    normal_subset = subset[subset['is_extreme_chase'] == False]
    chase_subset = subset[subset['is_extreme_chase'] == True]
    
    total_count = len(subset)
    total_hit_rate = subset['hit'].mean() * 100 if total_count > 0 else 0
    total_max_win = subset['max_win_pct'].mean() if total_count > 0 else 0

    normal_count = len(normal_subset)
    normal_hit_rate = normal_subset['hit'].mean() * 100 if normal_count > 0 else 0
    normal_max_win = normal_subset['max_win_pct'].mean() if normal_count > 0 else 0
    
    chase_count = len(chase_subset)
    chase_hit_rate = chase_subset['hit'].mean() * 100 if chase_count > 0 else 0
    chase_max_win = chase_subset['max_win_pct'].mean() if chase_count > 0 else 0
    
    header_str = f"| Date | Time | Side | ES Vol | Trades | Big≥500 | {label} From | {label} To | Hit? | Max Pct | Hours to hit | Hours to Max Profit |"
    header_chase = f"| Date | Time | Side | ES Vol | Trades | Big≥500 | {label} From | Rolling 12H H/L | {label} To | Hit? | Max Pct | Hours to hit | Hours to Max Profit |"
    sep_str = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    sep_chase = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"

    # Console Output
    print(f"# Historical Detailed Analysis: {period} ({vol_bucket})")
    print(f"\n### Overall Snapshot")
    print(f"- **Total Signals**: {total_count}")
    print(f"- **Overall Hit Rate**: {total_hit_rate:.2f}%")
    print(f"- **Overall Avg Max Favorable Move**: {total_max_win:.2f}%")
    
    print("\n### Normal Signals")
    print(f"- **Count**: {normal_count}")
    print(f"- **Hit Rate**: {normal_hit_rate:.2f}%")
    print(f"- **Avg Max Favorable Move**: {normal_max_win:.2f}%")
    print(header_str)
    print(sep_str)
    for _, row in normal_subset.iterrows():
        print(format_row(row))

    if not chase_subset.empty:
        print("\n### Extreme Chase Signals (Excluded from Stats)")
        print(f"- **Count**: {chase_count}")
        print(f"- **Hit Rate**: {chase_hit_rate:.2f}%")
        print(f"- **Avg Max Favorable Move**: {chase_max_win:.2f}%")
        print(header_chase)
        print(sep_chase)
        for _, row in chase_subset.iterrows():
            ext_price = f"${row['extreme_price']:.2f}" if not pd.isna(row.get('extreme_price')) else "-"
            r_str = format_row(row)
            parts = r_str.split(" | ")
            parts.insert(7, ext_price)
            print(" | ".join(parts))

    # Save to Markdown
    out_md = os.path.expanduser(f"~/.gemini/skills/order-flow-analysis/references/bucket_analysis_{period}_{vol_bucket}.md")
    with open(out_md, "w") as f:
        f.write(f"# Historical Detailed Analysis: {period} ({vol_bucket})\n\n")
        f.write(f"### Overall Snapshot\n")
        f.write(f"- **Total Signals**: {total_count}\n")
        f.write(f"- **Overall Hit Rate**: {total_hit_rate:.2f}%\n")
        f.write(f"- **Overall Avg Max Favorable Move**: {total_max_win:.2f}%\n\n")
        f.write("---\n\n")
        
        f.write("### Normal Signals\n")
        f.write(f"- **Count**: {normal_count}\n")
        f.write(f"- **Hit Rate**: {normal_hit_rate:.2f}%\n")
        f.write(f"- **Avg Max Favorable Move**: {normal_max_win:.2f}%\n\n")
        f.write(f"{header_str}\n{sep_str}\n")
        for _, row in normal_subset.iterrows():
            f.write(f"{format_row(row)}\n")
            
        if not chase_subset.empty:
            f.write("\n### Extreme Chase Signals (Excluded from Global Stats)\n")
            f.write(f"- **Count**: {chase_count}\n")
            f.write(f"- **Hit Rate**: {chase_hit_rate:.2f}%\n")
            f.write(f"- **Avg Max Favorable Move**: {chase_max_win:.2f}%\n\n")
            f.write(f"{header_chase}\n{sep_chase}\n")
            for _, row in chase_subset.iterrows():
                ext_price = f"${row['extreme_price']:.2f}" if not pd.isna(row.get('extreme_price')) else "-"
                r_str = format_row(row)
                parts = r_str.split(" | ")
                parts.insert(7, ext_price)
                f.write(" | ".join(parts) + "\n")
    print(f"\nSaved to {out_md}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python analyze_bucket_details.py <period> <vol_bucket>")
        print("Example: python analyze_bucket_details.py PM 500-1000")
        sys.exit(1)
        
    period_arg = sys.argv[1]
    bucket_arg = sys.argv[2]
    analyze_bucket(period_arg, bucket_arg)
