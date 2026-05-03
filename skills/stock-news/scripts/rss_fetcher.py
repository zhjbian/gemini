import json
import sys
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# Add PyTools to sys.path for BBDateTime (optional enhancement later)
py_tools_path = '/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools'
if py_tools_path not in sys.path:
    sys.path.append(py_tools_path)

FEEDS = {
    "ForexLive": "https://www.forexlive.com/feed",
    "Reuters World": "https://www.reuters.com/arc/outboundfeeds/v1/rss/world/"
}

def parse_rss_date(date_str):
    """
    Common RSS date formats: 
    - Wed, 22 Apr 2026 05:23:10 GMT
    - 2026-04-22T05:23:10Z
    """
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ"
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            continue
    return date_str

def fetch_and_parse(name, url):
    news_items = []
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            print(f"Warning: Failed to fetch {name} (Status: {response.status_code})")
            return []

        root = ET.fromstring(response.content)
        for item in root.findall('.//item'):
            title = item.find('title').text if item.find('title') is not None else ""
            desc = item.find('description').text if item.find('description') is not None else ""
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
            
            # Combine title and desc for full context
            full_text = f"{title}\n{desc}" if desc else title
            
            news_items.append({
                "text": full_text.strip(),
                "user": f"RSS: {name}",
                "timestamp": parse_rss_date(pub_date)
            })
    except Exception as e:
        print(f"Error processing {name}: {e}")
    
    return news_items

def main():
    all_news = []
    for name, url in FEEDS.items():
        print(f"Fetching {name}...")
        all_news.extend(fetch_and_parse(name, url))
    
    # Sort by timestamp descending
    all_news.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Print the top 10 for immediate review
    print(f"\n--- Successfully Loaded {len(all_news)} RSS Items ---")
    for item in all_news[:10]:
        print(f"[{item['timestamp']}] {item['user']}: {item['text'][:140]}...")

    # Return for internal use if called as module
    return all_news

if __name__ == "__main__":
    main()
