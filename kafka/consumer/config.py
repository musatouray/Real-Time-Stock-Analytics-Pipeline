import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_TRADES = os.getenv("KAFKA_TOPIC_TRADES", "stock.trades")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "stock-s3-consumer")
KAFKA_AUTO_OFFSET_RESET = os.getenv("KAFKA_AUTO_OFFSET_RESET", "earliest")

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
S3_RAW_PREFIX = os.getenv("S3_RAW_PREFIX", "raw/trades/")

# Flush to S3 when either threshold is reached
S3_BATCH_SIZE = int(os.getenv("S3_BATCH_SIZE", "100"))
S3_FLUSH_INTERVAL_SECONDS = int(os.getenv("S3_FLUSH_INTERVAL_SECONDS", "60"))

# Redis configuration for real-time price cache
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"
