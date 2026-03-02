#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# start.sh — Start all pipeline services
# ─────────────────────────────────────────────────────────────
set -euo pipefail

echo "==> Starting infrastructure (Zookeeper, Kafka)..."
docker compose up -d zookeeper kafka

echo "==> Waiting for Kafka to be ready..."
until docker compose exec kafka kafka-broker-api-versions \
    --bootstrap-server localhost:9092 >/dev/null 2>&1; do
  echo "   Kafka not ready yet — retrying in 5s..."
  sleep 5
done
echo "   Kafka ready."

echo "==> Creating Kafka topics (if not present)..."
docker compose exec kafka kafka-topics \
    --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --topic stock.trades \
    --partitions 3 \
    --replication-factor 1

echo "==> Starting Kafka UI, producer and consumer..."
docker compose up -d kafka-ui finnhub-producer s3-consumer

echo "==> Starting Airflow..."
docker compose up -d postgres redis
sleep 5   # let postgres start
docker compose run --rm airflow-init
docker compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-triggerer

echo "==> Starting dbt container..."
docker compose up -d dbt

echo ""
echo "Pipeline started."
echo "  Airflow:   http://localhost:8081  (admin / admin)"
echo "  Kafka UI:  http://localhost:8080"
