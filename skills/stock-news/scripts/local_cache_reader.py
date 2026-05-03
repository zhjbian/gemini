import json
import os
import sys
import glob

def read_local_news_cache(directory_path):
    """
    Reads all weekly JSON news cache files and aggregates them.
    """
    if not os.path.isdir(directory_path):
        return f"Error: Directory not found at {directory_path}."

    file_pattern = os.path.join(directory_path, "stock_news_*.json")
    files = glob.glob(file_pattern)
    
    if not files:
        return f"No news segments found in {directory_path} (Pattern: stock_news_*.json)"

    all_data = []
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_data.extend(data)
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")

    # Deduplicate in case overlapping tweets were sent across weeks
    news_map = {t.get('text', ''): t for t in all_data}
    
    # Sort by timestamp descending
    sorted_news = sorted(news_map.values(), key=lambda x: x.get('timestamp', ''), reverse=True)
    return sorted_news

if __name__ == "__main__":
    DATA_DIR = "/Users/zhijiebian/Documents/Workplace/Data/TwitterNews/"
    news = read_local_news_cache(DATA_DIR)
    
    if isinstance(news, list):
        print(f"--- Successfully Aggregated {len(news)} Tweets from Weekly Segments ---")
        for item in news[:5]: # Show latest 5
            print(f"[{item['timestamp']}] {item['user'][:30]}: {item['text'][:100]}...")
    else:
        print(news)
