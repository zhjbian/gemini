import pandas as pd
import os

csv_path = os.path.expanduser("~/.gemini/skills/order-flow-big-trade-analysis/references/backtest_results.csv")
df = pd.read_csv(csv_path)

# Filter for FirstHour 1000-2000
mask = (df['period'] == 'FirstHour') & (df['vol_bucket'] == '1000-2000') & (df['is_extreme_chase'] == False)
subset = df[mask]

print(f"FirstHour 1000-2000 (Qualified):")
print(f"Count: {len(subset)}")
print(f"Hits: {subset['hit'].sum()}")
print(f"Hit Rate: {subset['hit'].mean() * 100:.2f}%")

# Filter for FirstHour >2000
mask2 = (df['period'] == 'FirstHour') & (df['vol_bucket'] == '>2000') & (df['is_extreme_chase'] == False)
subset2 = df[mask2]

print(f"\nFirstHour >2000 (Qualified):")
print(f"Count: {len(subset2)}")
print(f"Hits: {subset2['hit'].sum()}")
print(f"Hit Rate: {subset2['hit'].mean() * 100:.2f}%")
