# Stock-News Skill

A skill for real-time aggregation and synthesis of financial and geopolitical news to identify market catalysts.

## Purpose
- Provide high-speed answers to geopolitical and macro-economic questions.
- Identify "Breaking News" catalysts for specific stock tickers.
- Bridge the gap when social media feeds (like Twitter Lists) are inaccessible by using targeted web search.

## Usage
1. **Automated Bridge**: News is automatically ingested from your Twitter Lists via Port 5008 and segmented into weekly local files (e.g. `stock_news_week_04-19-26.json`).
2. **Institutional Wires**: Use `rss_fetcher.py` to pull live geopolitical and financial confirmation from **ForexLive** and **Reuters**.
3. **Catalyst Engine**: Use `catalyst_reader.py` and `catalyst_calendar.json` to monitor scheduled earnings (**TSLA**) and macro events (**FOMC/GDP**).

## Core Sources
- **Pillar 1: Social Bridge**: Weekly segmented local news cache (Seattle Time).
- **Pillar 2: Institutional Wires**: ForexLive and Reuters RSS feeds (Non-authenticated).
- **Pillar 3: Catalyst Calendar**: Unified corporate earnings and global macro events database.

---
*Updated on April 21, 2026*

---
*Created on April 21, 2026*
