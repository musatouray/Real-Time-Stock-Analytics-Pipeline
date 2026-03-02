# CLAUDE.md — Project Context for Claude Code

> This file is the authoritative source of truth for Claude Code in this project.
> Update it immediately whenever the tech stack, workflow, architecture, or direction changes.

---

## Project Identity

| Field | Value |
|---|---|
| **Project name** | Real-Time Stock Analytics Pipeline |
| **Owner** | Amigomusa |
| **Goal** | Portfolio project demonstrating end-to-end data engineering skills |
| **End visualization** | Power BI (connected directly to Snowflake) |
| **Last updated** | 2026-03-02 |

---

## Working Directory

```
c:/Users/amigomusa/OneDrive - Amigomusa/Data Engineer/snowflake_dbt_airflow/real_time_stock_analytics/
```

> Platform: Windows 11. All Docker containers run Linux internally — use Unix paths inside containers and in Python/SQL code.

---

## Architecture Overview

```
Finnhub WebSocket API
        │  real-time trade ticks
        ▼
  Kafka Producer  (kafka/producer/finnhub_producer.py)
        │  topic: stock.trades  (3 partitions)
        ▼
  Kafka Broker    (Confluent cp-kafka:7.6.1)
        │
        ▼
  Kafka Consumer  (kafka/consumer/s3_consumer.py)
        │  micro-batch: 100 records OR 60 seconds
        │  NDJSON files partitioned by year/month/day/hour
        ▼
  AWS S3          s3://<bucket>/raw/trades/year=.../...
        │  SQS event notification
        ▼
  Snowpipe        AUTO_INGEST = TRUE
        │  COPY INTO RAW.STOCK_TRADES_RAW (VARIANT)
        ▼
  Snowflake       STOCK_ANALYTICS_DB
        │
        ├── RAW schema          (Snowpipe landing — VARIANT)
        ├── STAGING schema      (dbt views — typed, deduplicated)
        ├── INTERMEDIATE schema (dbt tables — OHLCV, volatility)
        └── MARTS schema        (dbt incremental — facts + dims)
                │
                ▼
        Power BI  (Direct Query or Import mode via Snowflake connector)
```

---

## Tech Stack (Current)

| Layer | Technology | Version |
|---|---|---|
| Data source | Finnhub WebSocket API | — |
| Streaming | Apache Kafka (Confluent) | 7.6.1 |
| Object storage | AWS S3 | — |
| Data warehouse | Snowflake | — |
| Ingestion | Snowpipe (AUTO_INGEST via SQS) | — |
| Transformation | dbt Core + dbt-snowflake | 1.8.2 |
| Orchestration | Apache Airflow (CeleryExecutor) | 2.9.1 |
| Containerization | Docker Compose | — |
| Visualization | Microsoft Power BI | Desktop |
| Language | Python | 3.11 |
| IDE | VS Code | — |

---

## Service Map (Docker Compose)

| Container | Purpose | Port(s) |
|---|---|---|
| `zookeeper` | Kafka coordination | internal |
| `kafka` | Message broker | 9092 (host), 29092 (internal) |
| `kafka-ui` | Kafka monitoring UI | 8080 |
| `finnhub-producer` | Finnhub WS → Kafka | — |
| `s3-consumer` | Kafka → S3 micro-batches | — |
| `postgres` | Airflow metadata DB | internal |
| `redis` | Airflow Celery broker | internal |
| `airflow-webserver` | Airflow UI | 8081 |
| `airflow-scheduler` | DAG scheduling | — |
| `airflow-worker` | Task execution | — |
| `airflow-triggerer` | Deferred tasks | — |
| `dbt` | dbt runner (keep-alive) | — |

---

## Snowflake Object Inventory

| Object | Name | Notes |
|---|---|---|
| Warehouse | `STOCK_ANALYTICS_WH` | X-SMALL, auto-suspend 120s |
| Database | `STOCK_ANALYTICS_DB` | 7-day data retention |
| Schema | `RAW` | Snowpipe landing zone |
| Schema | `STAGING` | dbt views |
| Schema | `INTERMEDIATE` | dbt tables |
| Schema | `MARTS` | dbt incremental tables |
| Schema | `SEEDS` | dbt CSV seeds |
| Raw table | `RAW.STOCK_TRADES_RAW` | VARIANT, 3-day retention |
| Stage | `RAW.S3_TRADES_STAGE` | External, Storage Integration |
| Pipe | `RAW.TRADES_PIPE` | AUTO_INGEST = TRUE |
| Integration | `STOCK_ANALYTICS_S3_INT` | IAM role-based, no static keys |
| Role | `STOCK_ANALYTICS_ROLE` | Service + dbt + Airflow |
| Role | `STOCK_ANALYTICS_READ_ROLE` | BI / analysts (SELECT on marts) |
| User | `STOCK_ANALYTICS_SVC` | Service account |

---

## dbt Layer Design

| Layer | Materialization | Purpose |
|---|---|---|
| `staging` | view | Extract + type from VARIANT; surrogate key (SHA2); dedup |
| `intermediate` | table | Hourly OHLCV aggregation, VWAP, stddev volatility |
| `marts` | incremental (merge) | Business-facing facts + SCD1 dimension |

### Key Models

| Model | Layer | Grain |
|---|---|---|
| `stg_stock_trades` | staging | 1 row per trade |
| `stg_company_profiles` | staging | 1 row per symbol |
| `int_stock_ohlcv` | intermediate | 1 row per (symbol, hour) |
| `int_stock_volatility` | intermediate | 1 row per (symbol, hour) |
| `fct_stock_trades` | marts | 1 row per trade (incremental) |
| `fct_stock_ohlcv_hourly` | marts | 1 row per (symbol, hour) (incremental) |
| `dim_companies` | marts | 1 row per symbol (SCD1) |

---

## Airflow DAGs

| DAG | Schedule | Purpose |
|---|---|---|
| `stock_analytics_pipeline` | `@hourly` | Full pipeline: S3 verify → Snowpipe refresh → dbt run → dbt test |
| `dbt_transforms` | `*/15 * * *` | Standalone dbt run for near-real-time mart refresh |

---

## Key Files Reference

```
.env.example                      ← template for all secrets
docker-compose.yml                ← all 12 services
Makefile                          ← make up / down / dbt-run / kafka-topics
kafka/producer/finnhub_producer.py
kafka/consumer/s3_consumer.py
airflow/dags/stock_pipeline_dag.py
airflow/dags/dbt_transform_dag.py
dbt/dbt_project.yml
dbt/profiles.yml                  ← Snowflake credentials via env vars
dbt/models/staging/stg_stock_trades.sql
dbt/models/marts/fct_stock_trades.sql
dbt/models/marts/fct_stock_ohlcv_hourly.sql
dbt/macros/generate_schema_name.sql  ← schemas named exactly, no prefix
snowflake/setup/01–07_*.sql       ← ordered Snowflake provisioning scripts
snowflake/queries/monitoring_queries.sql
scripts/init.sh / start.sh / stop.sh
```

---

## Business Questions This Pipeline Answers

1. **Intraday Volatility**: Which stocks show the highest intraday price volatility by hour, and during which market sessions does it peak?
2. **VWAP vs Close**: How does the VWAP trend compare to the hourly close price over 30 days — are stocks consistently trading above or below fair value?
3. **Sector Momentum**: Which sectors show the strongest price momentum in the first trading hour (market open effect)?
4. **Volume-Price Correlation**: Do volume spikes reliably precede or follow significant price moves, and by how much?
5. **Cross-Stock Correlation**: How correlated are individual stock returns within the same sector on a rolling hourly basis?

---

## Conventions & Rules for Claude

- **Never commit secrets** — all credentials go in `.env` (git-ignored)
- **Never add SQL prefixes to dbt schema names** — `generate_schema_name.sql` macro handles this
- **Incremental models use MERGE** — unique keys are `trade_id` for trades, `(symbol, hour_bucket)` for OHLCV
- **S3 files are NDJSON** — one JSON object per line, not a JSON array
- **Kafka internal listener is `kafka:29092`** — external is `localhost:9092`; use the internal one inside Docker
- **Airflow connections**: `snowflake_default` and `aws_default` are provisioned by `airflow-init`
- **Snowflake Snowpipe** requires an SQS notification on the S3 prefix after script 06
- **dbt `profiles.yml` reads from env vars** — never hard-code credentials in it
- **Update this file** whenever: stack changes, new tools added, direction pivots, new DAGs or models added

---

## Change Log

| Date | Change |
|---|---|
| 2026-03-02 | Initial scaffold created: Kafka, S3, Snowpipe, dbt, Airflow, Docker Compose |
| 2026-03-02 | CLAUDE.md and README.md added |
