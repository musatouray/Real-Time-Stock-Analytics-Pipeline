"""
s3_consumer.py
──────────────
Consumes trade events from Kafka and writes micro-batches to S3 as
newline-delimited JSON (NDJSON) files, partitioned by date and hour.

S3 path pattern:
    s3://<bucket>/raw/trades/year=YYYY/month=MM/day=DD/hour=HH/<uuid>.json

Partitioning is based on the TRADE TIMESTAMP (in US/Eastern timezone),
not the flush time. This ensures:
  - Hours align with US stock market hours (9:30 AM - 4:00 PM ET)
  - Records land in partitions reflecting when they actually occurred
  - Power BI dashboards show correct market-hour heatmaps

Snowflake Snowpipe is configured to auto-ingest files from this prefix.
"""

import json
import logging
import signal
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import boto3
import redis
from confluent_kafka import Consumer, KafkaError, KafkaException

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    KAFKA_AUTO_OFFSET_RESET,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    KAFKA_TOPIC_TRADES,
    REDIS_ENABLED,
    REDIS_HOST,
    REDIS_PORT,
    S3_BATCH_SIZE,
    S3_BUCKET_NAME,
    S3_FLUSH_INTERVAL_SECONDS,
    S3_RAW_PREFIX,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("s3-consumer")

# ─────────────────────────────────────────────────────────────
# Timezone configuration - US/Eastern for market-hour alignment
# ─────────────────────────────────────────────────────────────
US_EASTERN = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────────────────────
# AWS S3 client
# ─────────────────────────────────────────────────────────────
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

# ─────────────────────────────────────────────────────────────
# Redis client for real-time price cache (optional)
# ─────────────────────────────────────────────────────────────
redis_client = None
if REDIS_ENABLED:
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        redis_client.ping()
        log.info("Redis connected at %s:%s", REDIS_HOST, REDIS_PORT)
    except redis.ConnectionError as e:
        log.warning("Redis connection failed, continuing without cache: %s", e)
        redis_client = None


def _extract_trade_timestamp(record: dict) -> datetime:
    """
    Extract the trade timestamp from a record and convert to US/Eastern.

    Handles both message schemas:
      - WebSocket: 'timestamp' in Unix milliseconds
      - Polling: 'timestamp' in Unix seconds (has 'poll_time' field)
    """
    ts = record.get("timestamp")
    if ts is None:
        # Fallback to current time if no timestamp
        return datetime.now(US_EASTERN)

    # Detect if timestamp is milliseconds (WebSocket) or seconds (Polling)
    # Unix ms timestamps are ~13 digits (1711900800000), seconds are ~10 digits
    if ts > 10_000_000_000:
        # Milliseconds - convert to seconds
        ts = ts / 1000

    # Convert Unix timestamp to datetime in US/Eastern
    dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt_utc.astimezone(US_EASTERN)


def _get_partition_key(dt: datetime) -> str:
    """
    Generate the S3 partition path (without filename) for a given datetime.
    Datetime should already be in US/Eastern timezone.
    """
    return (
        f"year={dt.year:04d}/"
        f"month={dt.month:02d}/"
        f"day={dt.day:02d}/"
        f"hour={dt.hour:02d}/"
    )


def _build_s3_key(partition: str) -> str:
    """Build full S3 key with partition path and unique filename."""
    filename = f"{uuid.uuid4()}.json"
    return f"{S3_RAW_PREFIX}{partition}{filename}"


def update_redis_cache(record: dict) -> None:
    """
    Update Redis with the latest price for a symbol.

    Redis key structure:
      - stock:{symbol}:latest  → Hash with price, volume, timestamp, updated_at
      - stock:symbols          → Set of all active symbols

    Data expires after 5 minutes of no updates (market closed detection).
    """
    if redis_client is None:
        return

    try:
        # Extract symbol - handle both WebSocket and Polling schemas
        symbol = record.get("symbol")
        if not symbol:
            return

        # Extract price - WebSocket uses 'price', Polling uses 'current_price'
        price = record.get("price") or record.get("current_price")
        if price is None:
            return

        # Extract timestamp
        ts = record.get("timestamp", 0)
        if ts > 10_000_000_000:
            ts = ts / 1000  # Convert ms to seconds

        # Build cache entry
        cache_data = {
            "symbol": symbol,
            "price": str(price),
            "volume": str(record.get("volume", 0)),
            "timestamp": str(int(ts)),
            "updated_at": str(int(time.time())),
        }

        # Add optional fields from polling mode
        if "open_price" in record:
            cache_data["open"] = str(record["open_price"])
            cache_data["high"] = str(record.get("high_price", price))
            cache_data["low"] = str(record.get("low_price", price))
            cache_data["prev_close"] = str(record.get("previous_close", 0))

        # Update Redis with pipeline for atomicity
        pipe = redis_client.pipeline()
        pipe.hset(f"stock:{symbol}:latest", mapping=cache_data)
        pipe.expire(f"stock:{symbol}:latest", 300)  # 5 min TTL
        pipe.sadd("stock:symbols", symbol)
        pipe.expire("stock:symbols", 300)
        pipe.execute()

    except redis.RedisError as e:
        log.warning("Redis update failed for %s: %s", record.get("symbol"), e)


def flush_to_s3(batch: list[dict]) -> None:
    """
    Group records by their trade hour (US/Eastern) and write each group
    to the appropriate S3 partition.
    """
    if not batch:
        return

    # Group records by their trade hour partition
    partitioned: dict[str, list[dict]] = defaultdict(list)
    for record in batch:
        trade_dt = _extract_trade_timestamp(record)
        partition = _get_partition_key(trade_dt)
        partitioned[partition].append(record)

    # Write each partition group to S3
    for partition, records in partitioned.items():
        key = _build_s3_key(partition)
        body = "\n".join(json.dumps(record) for record in records)

        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
        )
        log.info(
            "Uploaded %d records → s3://%s/%s (partition: %s)",
            len(records), S3_BUCKET_NAME, key, partition.rstrip("/")
        )


# ─────────────────────────────────────────────────────────────
# Kafka consumer
# ─────────────────────────────────────────────────────────────
consumer = Consumer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": KAFKA_CONSUMER_GROUP,
        "auto.offset.reset": KAFKA_AUTO_OFFSET_RESET,
        "enable.auto.commit": False,   # manual commit after S3 write
        "max.poll.interval.ms": 300_000,
    }
)

_running = True


def _handle_signal(signum, frame):
    global _running
    log.info("Shutdown signal — draining buffer and stopping...")
    _running = False


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ─────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────
def main():
    consumer.subscribe([KAFKA_TOPIC_TRADES])
    log.info("Subscribed to topic: %s", KAFKA_TOPIC_TRADES)

    batch: list[dict] = []
    last_flush_time = time.monotonic()

    try:
        while _running:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                pass
            elif msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    log.debug("Reached partition EOF")
                else:
                    raise KafkaException(msg.error())
            else:
                try:
                    record = json.loads(msg.value().decode("utf-8"))
                    batch.append(record)
                    # Update Redis cache with latest price (non-blocking)
                    update_redis_cache(record)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    log.warning("Bad message skipped: %s", exc)

            elapsed = time.monotonic() - last_flush_time
            if len(batch) >= S3_BATCH_SIZE or (batch and elapsed >= S3_FLUSH_INTERVAL_SECONDS):
                flush_to_s3(batch)
                consumer.commit(asynchronous=False)
                batch.clear()
                last_flush_time = time.monotonic()

    finally:
        # Flush remaining records before exit
        if batch:
            flush_to_s3(batch)
            consumer.commit(asynchronous=False)
        consumer.close()
        log.info("Consumer shut down cleanly.")


if __name__ == "__main__":
    main()
