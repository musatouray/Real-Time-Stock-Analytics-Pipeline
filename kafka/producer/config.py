import os
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]
FINNHUB_WS_URL = os.getenv("FINNHUB_WS_URL", "wss://ws.finnhub.io")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_TRADES = os.getenv("KAFKA_TOPIC_TRADES", "stock.trades")

# Symbols to subscribe to via Finnhub WebSocket
STOCK_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "META", "NVDA", "JPM", "V", "JNJ",
]
