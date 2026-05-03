import json
from collections import Counter
from datetime import datetime
import os

input_file = '/Users/zhijiebian/Documents/Workplace/Data/TwitterNews/stock_news_week_04-19-26.json'
output_file = '/Users/zhijiebian/Documents/Workplace/Data/TwitterNews/stock_news_week_04-19-26_stats.md'

with open(input_file, 'r') as f:
    data = json.load(f)

stats_by_day = {}

for entry in data:
    ts_str = entry.get('timestamp')
    if not ts_str:
        continue
    
    # Extract date YYYY-MM-DD
    date_str = ts_str.split(' ')[0]
    
    user_raw = entry.get('user', 'Unknown')
    # Extract clean username - usually everything before the first '@'
    user_clean = user_raw.split('@')[0].strip()
    if user_clean.startswith('*'):
        user_clean = user_clean[1:]
    
    if date_str not in stats_by_day:
        stats_by_day[date_str] = {
            'count': 0,
            'sources': Counter()
        }
    
    stats_by_day[date_str]['count'] += 1
    stats_by_day[date_str]['sources'][user_clean] += 1

# Sort days
sorted_days = sorted(stats_by_day.keys())

with open(output_file, 'w') as f:
    f.write(f"# Statistics for {os.path.basename(input_file)}\n\n")
    
    total_captured = len(data)
    f.write(f"**Total News Captured:** {total_captured}\n\n")
    
    for day in sorted_days:
        f.write(f"## {day}\n")
        day_data = stats_by_day[day]
        f.write(f"- **Total Captured:** {day_data['count']}\n")
        f.write("- **By Source:**\n")
        for source, count in day_data['sources'].most_common():
            f.write(f"  - {source}: {count}\n")
        f.write("\n")

print(f"Stats generated in {output_file}")
