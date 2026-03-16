import os
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]
FINNHUB_WS_URL = os.getenv("FINNHUB_WS_URL", "wss://ws.finnhub.io")
FINNHUB_REST_URL = "https://finnhub.io/api/v1/quote"

# Mode: "websocket" (real-time) or "polling" (15-min intervals)
FINNHUB_MODE = os.getenv("FINNHUB_MODE", "websocket")
POLL_INTERVAL_MINUTES = int(os.getenv("POLL_INTERVAL_MINUTES", "15"))

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_TRADES = os.getenv("KAFKA_TOPIC_TRADES", "stock.trades")

# Symbols to subscribe to via Finnhub WebSocket or poll via REST API
STOCK_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "TSLA", "META", "JPM", "V", "JNJ",
    "UNH", "XOM", "WMT", "MA", "NFLX",
    "AVGO", "AMD", "CRM", "ORCL", "DIS",
]
