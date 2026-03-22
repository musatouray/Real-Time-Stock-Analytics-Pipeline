import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Refresh interval in seconds
REFRESH_INTERVAL = int(os.getenv("STREAMLIT_REFRESH_INTERVAL", "2"))

# Stock symbol metadata for display
STOCK_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOGL": "Communication Services",
    "AMZN": "Consumer Cyclical",
    "NVDA": "Technology",
    "TSLA": "Consumer Cyclical",
    "META": "Communication Services",
    "JPM": "Financial Services",
    "V": "Financial Services",
    "JNJ": "Healthcare",
    "UNH": "Healthcare",
    "XOM": "Energy",
    "WMT": "Consumer Defensive",
    "MA": "Financial Services",
    "NFLX": "Communication Services",
    "AVGO": "Technology",
    "AMD": "Technology",
    "CRM": "Technology",
    "ORCL": "Technology",
    "DIS": "Communication Services",
}
