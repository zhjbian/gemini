import requests
import json
import os

url = "http://localhost:5008/ingest_news"
payload = [
    {
        "text": "MOCK NEWS: Fed to increase rates again",
        "user": "FinancialJuice@financialjuice\u00b71m (4/22/2026 8:00:00 AM)",
        "timestamp": "2026-04-22T15:00:00Z"
    },
    {
        "text": "MOCK NEWS: Markets rallying",
        "user": "Mario Nawfal@MarioNawfal\u00b75m (4/22/2026 8:05:00 AM)",
        "timestamp": "2026-04-22T15:05:00Z"
    }
]

try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error connecting to server: {e}")
    print("Is the Flask app running at 5008?")
