"""
finnhub_producer.py
────────────────────
Connects to the Finnhub WebSocket API, subscribes to real-time trade
events for a configured list of stock symbols, and publishes each event
to a Kafka topic as a JSON-encoded message.

Message schema (Finnhub trade event):
    {
      "symbol":    "AAPL",
      "price":     182.35,
      "volume":    150,
      "timestamp": 1711900800000,   # Unix ms
      "conditions": ["1"]
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
        "linger.ms": 50,          # micro-batch for throughput
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


# ─────────────────────────────────────────────────────────────
# WebSocket callbacks
# ─────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# Graceful shutdown
# ─────────────────────────────────────────────────────────────
_ws_app = None


def _handle_signal(signum, frame):
    log.info("Shutdown signal received — flushing Kafka producer...")
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
    global _ws_app
    url = f"{FINNHUB_WS_URL}?token={FINNHUB_API_KEY}"
    log.info("Connecting to Finnhub WebSocket: %s", FINNHUB_WS_URL)

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


if __name__ == "__main__":
    main()
