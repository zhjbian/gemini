import sys
import os

def get_latest_news_summary(query):
    """
    Demonstration logic for the stock-news skill.
    In a real agentic flow, this would trigger the search_web tool and process results.
    """
    print(f"--- Fetching News for: {query} ---")
    # This is a placeholder for the agent's logic.
    # In practice, the agent uses its search_web tool directly.
    return f"News regarding '{query}' is currently being tracked via global search engines."

if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(get_latest_news_summary(q))
    else:
        print("Please provide a search query.")
