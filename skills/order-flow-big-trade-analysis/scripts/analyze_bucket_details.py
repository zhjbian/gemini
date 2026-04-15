import sys
import os
import pandas as pd

def analyze_bucket(period, vol_bucket):
    csv_path = os.path.expanduser("~/.gemini/skills/order-flow-big-trade-analysis/references/backtest_results.csv")
    if not os.path.exists(csv_path):
        print(f"Error: Backtest results not found at {csv_path}. Please run backtest_big_trades.py first.")
        return

    df = pd.read_csv(csv_path)

    # Auto-detect column names (support both old spy_* and new es_* columns)
    from_col = 'es_start' if 'es_start' in df.columns else 'spy_start'
    to_col = 'es_target' if 'es_target' in df.columns else 'spy_target'
    label = 'ES' if 'es_start' in df.columns else 'SPY'
    
    # Filter for the specific bucket
    mask = (df['period'] == period) & (df['vol_bucket'] == vol_bucket)
    subset = df[mask].sort_values(by='date', ascending=False)

    if subset.empty:
        print(f"No historical data found for Bucket: {period} ({vol_bucket})")
        return

    # Calculate statistics
    total = len(subset)
    hits = subset['hit'].sum()
    win_rate = (hits / total) * 100
    avg_max_win = subset['max_win_pct'].mean()
    
    # Generate Markdown Output
    print(f"# Historical Detailed Analysis: {period} ({vol_bucket})")
    print(f"\n- **Total Signals**: {total}")
    print(f"- **Hit Rate (>=0.75% {label} move)**: {win_rate:.2f}% ({int(hits)}/{total})")
    print(f"- **Avg Max Favorable Move**: {avg_max_win:.2f}%")
    print("\n---")
    
    header = f"\n| Date | Time | Side | ES Vol | Trades | Big≥500 | {label} From | {label} To | Hit? | Max Pct | Days to Hit |"
    separator = "|---|---|---|---|---|---|---|---|---|---|---|"
    
    print(header)
    print(separator)

    def format_row(row):
        hit_emoji = "✅" if row['hit'] == 1.0 else "❌"
        days = int(row['days_to_hit']) if not pd.isna(row['days_to_hit']) else "-"
        total_ct = int(row['total_count']) if not pd.isna(row.get('total_count', float('nan'))) else "-"
        big_ct = int(row['big_count']) if not pd.isna(row.get('big_count', float('nan'))) else "-"
        price_from = f"${row[from_col]:.2f}" if not pd.isna(row.get(from_col, float('nan'))) else "-"
        price_to = f"${row[to_col]:.2f}" if not pd.isna(row.get(to_col, float('nan'))) else "-"
        return f"| {row['date']} | {row['time']} | {row['side']} | {int(row['net_vol'])} | {total_ct} | {big_ct} | {price_from} | {price_to} | {hit_emoji} | {row['max_win_pct']:.2f}% | {days} |"

    for _, row in subset.iterrows():
        print(format_row(row))

    # Save to a markdown file
    out_md = os.path.expanduser(f"~/.gemini/skills/order-flow-big-trade-analysis/references/bucket_analysis_{period}_{vol_bucket}.md")
    with open(out_md, "w") as f:
        f.write(f"# Historical Detailed Analysis: {period} ({vol_bucket})\n")
        f.write(f"\n- **Total Signals**: {total}\n")
        f.write(f"- **Hit Rate**: {win_rate:.2f}%\n")
        f.write(f"- **Avg Max Favorable Move**: {avg_max_win:.2f}%\n")
        f.write(f"\n{header.strip()}\n")
        f.write(f"{separator}\n")
        for _, row in subset.iterrows():
            f.write(f"{format_row(row)}\n")
    
    print(f"\nDetailed markdown saved to: {out_md}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python analyze_bucket_details.py <period> <vol_bucket>")
        print("Example: python analyze_bucket_details.py PM 500-1000")
        sys.exit(1)
        
    period_arg = sys.argv[1]
    bucket_arg = sys.argv[2]
    analyze_bucket(period_arg, bucket_arg)
