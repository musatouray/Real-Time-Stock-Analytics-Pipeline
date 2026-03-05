"""
finnhub_producer.py
────────────────────
Dual-mode Finnhub producer that supports both:
  1. WebSocket mode: Real-time trade ticks (sub-second granularity)
  2. Polling mode: REST API quotes at configurable intervals (default: 15 minutes)

Mode is controlled by FINNHUB_MODE environment variable:
  - "websocket" (default): Real-time streaming
  - "polling": Interval-based polling

WebSocket message schema:
    {
      "symbol":    "AAPL",
      "price":     182.35,
      "volume":    150,
      "timestamp": 1711900800000,   # Unix ms
      "conditions": ["1"]
    }

Polling message schema:
    {
      "symbol":         "AAPL",
      "current_price":  182.35,
      "open_price":     181.50,
      "high_price":     183.10,
      "low_price":      181.20,
      "previous_close": 180.95,
      "timestamp":      1711900800,   # Unix seconds
      "poll_time":      1711900815    # When we fetched this data
    }
"""

import json
import logging
import signal
import sys
import time

import websocket
from confluent_kafka import Producer, KafkaException

from config import (
    FINNHUB_API_KEY,
    FINNHUB_WS_URL,
    FINNHUB_REST_URL,
    FINNHUB_MODE,
    POLL_INTERVAL_MINUTES,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_TRADES,
    STOCK_SYMBOLS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("finnhub-producer")

# ─────────────────────────────────────────────────────────────
# Kafka producer setup
# ─────────────────────────────────────────────────────────────
producer = Producer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "linger.ms": 50,
        "compression.type": "snappy",
        "acks": "all",
        "retries": 5,
    }
)


def delivery_report(err, msg):
    if err:
        log.error("Delivery failed for key=%s: %s", msg.key(), err)
    else:
        log.debug(
            "Delivered topic=%s partition=%d offset=%d",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


# ═════════════════════════════════════════════════════════════
# MODE 1: WEBSOCKET (Real-Time Streaming)
# ═════════════════════════════════════════════════════════════

def on_open(ws):
    log.info("WebSocket opened — subscribing to %d symbols", len(STOCK_SYMBOLS))
    for symbol in STOCK_SYMBOLS:
        ws.send(json.dumps({"type": "subscribe", "symbol": symbol}))


def on_message(ws, raw_message):
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        log.warning("Non-JSON message received: %s", raw_message)
        return

    msg_type = payload.get("type")
    if msg_type != "trade":
        return  # skip ping/error frames

    for trade in payload.get("data", []):
        record = {
            "symbol":     trade.get("s"),
            "price":      trade.get("p"),
            "volume":     trade.get("v"),
            "timestamp":  trade.get("t"),
            "conditions": trade.get("c", []),
        }
        key = record["symbol"].encode("utf-8")
        value = json.dumps(record).encode("utf-8")

        try:
            producer.produce(
                topic=KAFKA_TOPIC_TRADES,
                key=key,
                value=value,
                on_delivery=delivery_report,
            )
            producer.poll(0)  # trigger callbacks without blocking
        except KafkaException as exc:
            log.error("Failed to produce message: %s", exc)


def on_error(ws, error):
    log.error("WebSocket error: %s", error)


def on_close(ws, close_status_code, close_msg):
    log.warning("WebSocket closed: %s %s", close_status_code, close_msg)
    producer.flush()


_ws_app = None


def run_websocket_mode():
    """Run in real-time WebSocket streaming mode."""
    global _ws_app
    url = f"{FINNHUB_WS_URL}?token={FINNHUB_API_KEY}"
    log.info("🔴 WEBSOCKET MODE: Connecting to Finnhub WebSocket for real-time trades")

    while True:
        _ws_app = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        _ws_app.run_forever(ping_interval=30, ping_timeout=10)
        log.warning("Connection dropped — reconnecting in 5s...")
        time.sleep(5)


# ═════════════════════════════════════════════════════════════
# MODE 2: POLLING (15-Minute Intervals)
# ═════════════════════════════════════════════════════════════

def fetch_and_publish_quotes():
    """Fetch latest quotes for all symbols and publish to Kafka."""
    import requests  # Lazy import to avoid dependency in websocket mode

    poll_time = int(time.time())
    log.info("Polling Finnhub API for %d symbols...", len(STOCK_SYMBOLS))

    success_count = 0
    error_count = 0

    for symbol in STOCK_SYMBOLS:
        try:
            # Fetch quote from Finnhub REST API
            response = requests.get(
                FINNHUB_REST_URL,
                params={"symbol": symbol, "token": FINNHUB_API_KEY},
                timeout=10
            )
            response.raise_for_status()
            quote = response.json()

            # Check if quote data is valid (Finnhub returns {"c":0} for invalid symbols or closed market)
            if quote.get("c", 0) == 0:
                log.warning("No data for %s (market closed or invalid symbol)", symbol)
                error_count += 1
                continue

            # Transform to our schema
            record = {
                "symbol": symbol,
                "current_price": quote.get("c"),      # current price
                "open_price": quote.get("o"),         # open price
                "high_price": quote.get("h"),         # high price
                "low_price": quote.get("l"),          # low price
                "previous_close": quote.get("pc"),    # previous close
                "timestamp": quote.get("t"),          # Finnhub timestamp (Unix seconds)
                "poll_time": poll_time,               # When we fetched this
            }

            # Publish to Kafka
            key = symbol.encode("utf-8")
            value = json.dumps(record).encode("utf-8")

            producer.produce(
                topic=KAFKA_TOPIC_TRADES,
                key=key,
                value=value,
                on_delivery=delivery_report,
            )
            producer.poll(0)
            success_count += 1

        except Exception as exc:
            log.error("Error processing %s: %s", symbol, exc)
            error_count += 1

    # Flush all messages
    producer.flush(timeout=10)
    log.info(
        "✅ Poll complete: %d published, %d errors",
        success_count,
        error_count,
    )


def run_polling_mode():
    """Run in polling mode (fetch quotes at intervals)."""
    poll_interval_seconds = POLL_INTERVAL_MINUTES * 60
    log.info(
        "🟢 POLLING MODE: Fetching quotes every %d minutes for %d symbols",
        POLL_INTERVAL_MINUTES,
        len(STOCK_SYMBOLS),
    )

    while _running:
        try:
            fetch_and_publish_quotes()
        except Exception as exc:
            log.exception("Error in poll cycle: %s", exc)

        # Sleep until next poll
        if _running:
            log.info("💤 Sleeping for %d minutes...", POLL_INTERVAL_MINUTES)
            time.sleep(poll_interval_seconds)


# ─────────────────────────────────────────────────────────────
# Graceful shutdown
# ─────────────────────────────────────────────────────────────
_running = True


def _handle_signal(signum, frame):
    global _running
    log.info("Shutdown signal received — flushing Kafka producer...")
    _running = False
    if _ws_app:
        _ws_app.close()
    producer.flush(timeout=10)
    sys.exit(0)


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def main():
    mode = FINNHUB_MODE.lower()

    if mode == "polling":
        run_polling_mode()
    elif mode == "websocket":
        run_websocket_mode()
    else:
        log.error("Invalid FINNHUB_MODE: %s (must be 'websocket' or 'polling')", mode)
        sys.exit(1)


if __name__ == "__main__":
    main()
