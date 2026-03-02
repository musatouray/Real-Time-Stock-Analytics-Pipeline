# Real-Time Stock Analytics Pipeline

> An end-to-end data engineering portfolio project that streams live stock market data from the Finnhub API through Kafka, lands it in AWS S3, auto-ingests it into Snowflake via Snowpipe, transforms it with dbt Core, orchestrates everything with Apache Airflow, and delivers insights through Power BI dashboards — all containerized with Docker.

---

## Project Overview

This project simulates a production-grade real-time analytics platform that a financial services company would use to monitor stock market activity. It demonstrates the full modern data engineering lifecycle:

- **Ingestion** of live WebSocket trade events at sub-second latency
- **Streaming** through a fault-tolerant Kafka message bus
- **Landing** micro-batched NDJSON files in a partitioned S3 data lake
- **Auto-ingestion** into Snowflake using Snowpipe event-driven triggers
- **Transformation** through a layered dbt project (staging → intermediate → marts)
- **Orchestration** of the entire pipeline via scheduled Airflow DAGs
- **Visualization** of business-ready mart tables in Power BI

The stack mirrors what you would find at companies like Robinhood, Bloomberg, or any trading desk running a modern cloud data platform.

---

## Business Questions & Deliverables

The pipeline is designed to answer five real-world business questions that a portfolio manager, quant analyst, or trading desk would care about. Each question drives a dedicated Power BI report page.

---

### Q1 — Intraday Volatility Heatmap
**"Which stocks show the highest intraday price volatility by hour, and during which market sessions does it peak?"**

- **Why it matters**: Traders size positions based on expected volatility. Risk managers set intraday stop-loss thresholds using hourly volatility patterns.
- **dbt model**: `fct_stock_ohlcv_hourly` — `stddev_price`, `price_range`
- **Power BI visual**: Matrix heatmap (Stock × Hour of Day) colored by `stddev_price`; slicer for date range and sector

---

### Q2 — VWAP vs Close Price Divergence
**"How does the VWAP trend compare to the hourly close price over 30 days — are stocks consistently trading above or below fair value?"**

- **Why it matters**: VWAP is the institutional benchmark for execution quality. A sustained close price above VWAP signals buying pressure; below signals distribution.
- **dbt model**: `fct_stock_ohlcv_hourly` — `vwap`, `close_price`, `pct_change`
- **Power BI visual**: Dual-axis line chart of VWAP vs Close per symbol; conditional formatting to flag divergence > 0.5%

---

### Q3 — Sector Momentum at Market Open
**"Which sectors demonstrate the strongest price momentum in the first trading hour (9:30–10:30 AM EST)?"**

- **Why it matters**: The opening hour concentrates the highest volume and most price discovery. Sector rotation patterns at open drive institutional strategies.
- **dbt model**: `fct_stock_ohlcv_hourly` joined to `dim_companies` — filter on `hour_bucket` = market open hour, group by `sector`
- **Power BI visual**: Bar chart of average `pct_change` by sector at market open; drill-through to individual stock performance

---

### Q4 — Volume Spike vs Price Movement Analysis
**"Do volume spikes reliably precede or follow significant price moves across the top 10 stocks, and by how much?"**

- **Why it matters**: Abnormal volume is a leading indicator used in technical analysis and for regulatory surveillance of unusual trading activity.
- **dbt model**: `fct_stock_ohlcv_hourly` — `total_volume`, `pct_change`; `fct_stock_trades` for tick-level granularity
- **Power BI visual**: Scatter plot of hourly volume vs price change per symbol; volume ranked bar chart with `pct_change` overlay

---

### Q5 — Rolling Cross-Stock Return Correlation
**"How correlated are individual stock returns within the same sector on a rolling hourly basis, and does correlation spike during high-volatility sessions?"**

- **Why it matters**: Portfolio managers use correlation to manage diversification. Rising intra-sector correlation during drawdowns is a known risk-off signal.
- **dbt model**: `fct_stock_ohlcv_hourly` — `pct_change` pivoted by symbol, windowed rolling correlation
- **Power BI visual**: Correlation matrix (heatmap) per sector; time-series line chart of average sector correlation over the trading day

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Data source | [Finnhub](https://finnhub.io) WebSocket API | Real-time trade tick stream |
| Message bus | Apache Kafka (Confluent 7.6.1) | Durable, fault-tolerant event queue |
| Object storage | AWS S3 | Partitioned NDJSON data lake |
| Auto-ingestion | Snowflake Snowpipe (SQS) | Event-driven, zero-touch S3 → Snowflake |
| Data warehouse | Snowflake | Cloud-native analytical SQL engine |
| Transformation | dbt Core 1.8.2 + dbt-snowflake | Modular, tested SQL transformations |
| Orchestration | Apache Airflow 3.1.7 | DAG scheduling, monitoring, alerting |
| Containerization | Docker Compose | Reproducible local environment |
| Package manager | [uv](https://github.com/astral-sh/uv) (Astral) | Fast Rust-based pip replacement in all Docker images |
| Visualization | Microsoft Power BI | Business dashboards via Snowflake connector |
| Language | Python 3.11 | Producer, consumer, DAG logic |
| IDE | VS Code | Development environment |

---

## Key Features

- **True real-time ingestion** — Finnhub WebSocket delivers sub-second trade ticks; Kafka buffers them with zero data loss
- **Micro-batch S3 landing** — Consumer flushes every 100 records or 60 seconds, maintaining near-real-time latency without per-record S3 writes
- **Event-driven Snowpipe** — SQS notifications trigger Snowpipe automatically the moment a file lands in S3; no polling required
- **Layered dbt architecture** — Staging (views) → Intermediate (tables) → Marts (incremental merge) follows the industry-standard medallion-style pattern
- **Idempotent incremental loads** — All mart models use `MERGE` on surrogate keys; re-running any DAG is safe and produces no duplicates
- **Built-in data quality** — Every dbt model has schema tests (unique, not_null); custom singular tests (positive volume); audit trail via dbt test logs
- **Full observability** — Kafka UI for topic monitoring, Airflow UI for DAG health, Snowflake COPY_HISTORY for pipe audit, `monitoring_queries.sql` for ad-hoc checks
- **Secrets-free config** — All credentials injected via `.env` at runtime; Snowflake uses a Storage Integration (IAM role) — no static AWS keys in Snowflake
- **Fully reproducible builds** — `pyproject.toml` + `uv.lock` per service; Docker images built with `uv sync --frozen` ensuring byte-for-byte identical dependency trees in dev, CI, and cloud
- **One-command startup** — `make up` builds all images and starts all 12 services in dependency order; `make dev-setup` bootstraps local venvs for IDE support

---

## Repository Structure

```
real_time_stock_analytics/
│
├── CLAUDE.md                          # Claude Code project context (auto-updated)
├── README.md                          # This file
├── docker-compose.yml                 # All 12 services defined
├── .env.example                       # Template for all credentials
├── .gitignore
├── .python-version                    # Pins Python 3.11 for uv and pyenv
├── Makefile                           # make up / down / dev-setup / lock / dbt-run / kafka-topics
│
├── kafka/
│   ├── producer/
│   │   ├── finnhub_producer.py        # Finnhub WebSocket → Kafka (stock.trades)
│   │   ├── config.py                  # Symbol list, Kafka config
│   │   ├── pyproject.toml             # Dependency declaration
│   │   ├── uv.lock                    # Pinned lockfile (committed to git)
│   │   └── Dockerfile                 # uv sync --frozen for reproducible builds
│   └── consumer/
│       ├── s3_consumer.py             # Kafka → S3 micro-batch writer
│       ├── config.py                  # Batch size, flush interval, S3 config
│       ├── pyproject.toml
│       ├── uv.lock
│       └── Dockerfile
│
├── airflow/
│   ├── Dockerfile                     # Airflow 3.1.7 + providers (constraint-based)
│   ├── pyproject.toml                 # Providers + dev group (apache-airflow for IDE)
│   ├── dags/
│   │   ├── stock_pipeline_dag.py      # Hourly: S3 check → Snowpipe → dbt run → test
│   │   └── dbt_transform_dag.py       # Every 15 min: standalone dbt transforms
│   ├── plugins/                       # Custom Airflow operators (future use)
│   └── logs/                          # Airflow task logs (git-ignored)
│
├── dbt/
│   ├── Dockerfile                     # dbt-core + dbt-snowflake (uv sync --frozen)
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── dbt_project.yml                # Project config, materializations, tags
│   ├── profiles.yml                   # Snowflake connection via env vars
│   ├── packages.yml                   # dbt-utils, audit_helper
│   ├── models/
│   │   ├── staging/
│   │   │   ├── _sources.yml           # Raw Snowpipe table source definition
│   │   │   ├── _staging.yml           # Column tests and descriptions
│   │   │   ├── stg_stock_trades.sql   # VARIANT extraction, dedup, SHA2 key
│   │   │   └── stg_company_profiles.sql
│   │   ├── intermediate/
│   │   │   ├── _int_models.yml
│   │   │   ├── int_stock_ohlcv.sql    # Hourly OHLCV aggregation
│   │   │   └── int_stock_volatility.sql # stddev, VWAP, price range
│   │   └── marts/
│   │       ├── _marts.yml
│   │       ├── fct_stock_trades.sql   # Per-trade fact (incremental/merge)
│   │       ├── fct_stock_ohlcv_hourly.sql # Hourly OHLCV + volatility (incremental)
│   │       └── dim_companies.sql      # Company dimension (SCD Type 1)
│   ├── macros/
│   │   └── generate_schema_name.sql   # Exact schema names (no target prefix)
│   ├── seeds/
│   │   └── stock_symbols.csv          # 10 symbols with sector/exchange metadata
│   └── tests/
│       └── assert_positive_volume.sql # Custom singular data quality test
│
├── snowflake/
│   ├── setup/
│   │   ├── 01_roles_and_users.sql     # ACCOUNTADMIN: roles, service user
│   │   ├── 02_warehouse.sql           # SYSADMIN: warehouse creation
│   │   ├── 03_database_schemas.sql    # Database, 5 schemas, grants
│   │   ├── 04_raw_tables.sql          # STOCK_TRADES_RAW (VARIANT)
│   │   ├── 05_s3_integration.sql      # Storage Integration (IAM role)
│   │   ├── 06_stage_and_pipe.sql      # External stage + Snowpipe
│   │   └── 07_grants.sql              # Final permissions sweep
│   └── queries/
│       └── monitoring_queries.sql     # Pipe status, copy history, mart freshness
│
└── scripts/
    ├── init.sh                        # First-time bootstrap, Fernet key gen
    ├── start.sh                       # Ordered service startup with health checks
    └── stop.sh                        # Graceful shutdown
```

---

## Pipeline Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        REAL-TIME STOCK ANALYTICS PIPELINE                    │
└──────────────────────────────────────────────────────────────────────────────┘

  MARKET DATA                  STREAMING LAYER                  STORAGE LAYER
  ───────────                  ───────────────                  ─────────────
  ┌─────────────┐              ┌─────────────┐
  │  Finnhub    │  WebSocket   │   Kafka     │
  │  API        │─────────────▶│   Producer  │
  │  (trades,   │  sub-second  │             │
  │   quotes)   │   ticks      └──────┬──────┘
  └─────────────┘                     │ topic: stock.trades
                                      │ (3 partitions)
                                      ▼
                               ┌─────────────┐    micro-batch     ┌──────────────┐
                               │   Kafka     │   (100 records     │   AWS S3     │
                               │   Broker    │────or 60 sec)─────▶│  raw/trades/ │
                               │  (cp-kafka) │    NDJSON files    │  year=.../   │
                               └─────────────┘                    │  month=.../  │
                                      │                           │  day=.../    │
                               ┌──────┴──────┐                    │  hour=.../   │
                               │   Kafka     │                    └──────┬───────┘
                               │   UI        │                           │
                               │  :8080      │                    SQS event notification
                               └─────────────┘                           │
                                                                         ▼
  ─────────────────────────────────────────────────────────────────────────────
  SNOWFLAKE DATA WAREHOUSE
  ─────────────────────────────────────────────────────────────────────────────

                                                              ┌──────────────────┐
                                                              │    Snowpipe      │
                                                              │  AUTO_INGEST     │
                                                              │  (SQS trigger)   │
                                                              └───────┬──────────┘
                                                                      │ COPY INTO
                                                                      ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │  STOCK_ANALYTICS_DB                                                         │
  │                                                                             │
  │  RAW schema                                                                 │
  │  ┌─────────────────────────────────────────────────────────────────────┐   │
  │  │  STOCK_TRADES_RAW  (VARIANT — raw JSON, no schema enforcement)      │   │
  │  └───────────────────────────────┬─────────────────────────────────────┘   │
  │                                  │ dbt run --select staging                │
  │  STAGING schema                  ▼                                         │
  │  ┌─────────────────────────────────────────────────────────────────────┐   │
  │  │  stg_stock_trades       (view — typed, deduped, SHA2 surrogate key) │   │
  │  │  stg_company_profiles   (view — from seeds CSV)                     │   │
  │  └───────────────────────────────┬─────────────────────────────────────┘   │
  │                                  │ dbt run --select intermediate           │
  │  INTERMEDIATE schema             ▼                                         │
  │  ┌─────────────────────────────────────────────────────────────────────┐   │
  │  │  int_stock_ohlcv        (table — hourly Open/High/Low/Close/Volume) │   │
  │  │  int_stock_volatility   (table — VWAP, stddev, price range)         │   │
  │  └───────────────────────────────┬─────────────────────────────────────┘   │
  │                                  │ dbt run --select marts                  │
  │  MARTS schema                    ▼                                         │
  │  ┌─────────────────────────────────────────────────────────────────────┐   │
  │  │  fct_stock_trades       (incremental table — 1 row per trade)       │   │
  │  │  fct_stock_ohlcv_hourly (incremental table — 1 row per sym + hour)  │   │
  │  │  dim_companies          (table — company metadata, SCD Type 1)      │   │
  │  └───────────────────────────────┬─────────────────────────────────────┘   │
  └──────────────────────────────────┼─────────────────────────────────────────┘
                                     │ Snowflake Connector
                                     ▼
                              ┌──────────────┐
                              │  Power BI    │
                              │  Dashboards  │
                              │              │
                              │  • Volatility│
                              │    Heatmap   │
                              │  • VWAP vs   │
                              │    Close     │
                              │  • Sector    │
                              │    Momentum  │
                              │  • Volume vs │
                              │    Price     │
                              │  • Correl-   │
                              │    ation     │
                              └──────────────┘

  ORCHESTRATION (Apache Airflow :8081)
  ──────────────────────────────────────────────────────────────────
  stock_analytics_pipeline  [@hourly]
    health_check_snowflake ──┐
    verify_s3_new_files    ──┴──▶ trigger_snowpipe_refresh
                                        │
                                        ▼
                               dbt_run_staging
                                        │
                                        ▼
                               dbt_run_intermediate
                                        │
                                        ▼
                               dbt_run_marts
                                        │
                                        ▼
                               dbt_test

  dbt_transforms  [*/15 * * * *]   ← independent near-real-time mart refresh
```

---

## Step-by-Step Implementation Guide

### Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop | Engine 24+, Compose plugin |
| AWS account | S3 bucket + IAM permissions |
| Snowflake account | Trial account is sufficient |
| Finnhub account | Free tier gives WebSocket access |
| Power BI Desktop | Windows; free to download |

---

### Step 1 — Clone & Bootstrap

```bash
git clone <your-repo-url>
cd real_time_stock_analytics
bash scripts/init.sh
```

`init.sh` creates `.env` from `.env.example` and generates an Airflow Fernet key. Copy the Fernet key output into `.env`.

---

### Step 2 — Fill in `.env` Credentials

Open `.env` and populate every value:

```bash
# Minimum required before starting:
FINNHUB_API_KEY=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=...
SNOWFLAKE_ACCOUNT=...
SNOWFLAKE_USER=...
SNOWFLAKE_PASSWORD=...
AIRFLOW__CORE__FERNET_KEY=...   # from init.sh output
AIRFLOW__WEBSERVER__SECRET_KEY=...  # any random string
```

---

### Step 3 — Create the S3 Bucket

In your AWS Console (or via CLI):

```bash
aws s3 mb s3://your-stock-analytics-bucket --region us-east-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket your-stock-analytics-bucket \
  --versioning-configuration Status=Enabled
```

---

### Step 4 — Provision Snowflake (run scripts in order)

Open a Snowflake worksheet and run the scripts in `snowflake/setup/` one by one:

```
01_roles_and_users.sql    → run as ACCOUNTADMIN
02_warehouse.sql          → run as SYSADMIN
03_database_schemas.sql   → run as SYSADMIN
04_raw_tables.sql         → run as STOCK_ANALYTICS_ROLE
05_s3_integration.sql     → run as ACCOUNTADMIN
```

After script 05, run this to get the IAM details:
```sql
DESC INTEGRATION STOCK_ANALYTICS_S3_INT;
```
Copy `STORAGE_AWS_IAM_USER_ARN` and `STORAGE_AWS_EXTERNAL_ID` into your AWS IAM role trust relationship.

```
06_stage_and_pipe.sql     → run as STOCK_ANALYTICS_ROLE
```

After script 06, get the SQS queue ARN:
```sql
SHOW PIPES LIKE 'TRADES_PIPE';
-- copy the notification_channel value
```
Go to your S3 bucket → Properties → Event notifications → Add notification:
- Event type: `All object create events`
- Prefix: `raw/trades/`
- Destination: SQS → paste the ARN from above

```
07_grants.sql             → run as ACCOUNTADMIN
```

---

### Step 5 — Start All Services

```bash
make up
# or for the first time with ordered startup:
bash scripts/start.sh
```

Verify services are healthy:
```bash
make ps
```

| UI | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8081 | admin / admin |
| Kafka UI | http://localhost:8080 | — |

---

### Step 6 — Verify Data Is Flowing

**Kafka** — check the topic has messages:
```bash
make kafka-topics
# You should see: stock.trades
```
Open Kafka UI → Topics → `stock.trades` → Messages to see live trade events.

**S3** — check files are landing:
```bash
aws s3 ls s3://your-stock-analytics-bucket/raw/trades/ --recursive | head -20
```

**Snowflake** — check Snowpipe is ingesting:
```sql
SELECT SYSTEM$PIPE_STATUS('STOCK_ANALYTICS_DB.RAW.TRADES_PIPE');
SELECT COUNT(*) FROM STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW;
```

---

### Step 7 — Run dbt Transformations

Seed reference data first:
```bash
docker compose exec dbt dbt seed \
  --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt
```

Run all models:
```bash
make dbt-run
```

Run tests:
```bash
make dbt-test
```

Generate and view docs:
```bash
make dbt-docs
# Open http://localhost:8082
```

---

### Step 8 — Enable Airflow DAGs

1. Open Airflow at http://localhost:8081
2. Go to **DAGs**
3. Toggle on `stock_analytics_pipeline` (hourly) and `dbt_transforms` (15 min)
4. Trigger `stock_analytics_pipeline` manually for the first run
5. Monitor task status in the **Grid** view

---

### Step 9 — Connect Power BI to Snowflake

1. Open **Power BI Desktop**
2. **Get Data** → **Snowflake**
3. Enter your Snowflake account URL (e.g., `xy12345.snowflakecomputing.com`)
4. Database: `STOCK_ANALYTICS_DB` | Warehouse: `STOCK_ANALYTICS_WH`
5. Authenticate with `STOCK_ANALYTICS_SVC` credentials
6. Load these tables:
   - `MARTS.FCT_STOCK_TRADES`
   - `MARTS.FCT_STOCK_OHLCV_HOURLY`
   - `MARTS.DIM_COMPANIES`
7. Build your five dashboard pages (one per business question)
8. Set **Direct Query** mode for near-real-time refresh

> Tip: Use Power BI's **Auto Page Refresh** (available in Direct Query mode) to set a refresh interval matching your `dbt_transforms` schedule (15 minutes).

---

### Step 10 — Monitoring & Maintenance

```bash
# Check Snowpipe copy history (Snowflake)
# See snowflake/queries/monitoring_queries.sql

# Tail all container logs
make logs

# Run ad-hoc dbt model
docker compose exec dbt dbt run \
  --select fct_stock_ohlcv_hourly \
  --project-dir /usr/app/dbt \
  --profiles-dir /usr/app/dbt

# Stop everything (volumes preserved)
bash scripts/stop.sh

# Full teardown including volumes
make down
```

---

## Author

**Amigomusa** | Data Engineering Portfolio
> Built to demonstrate end-to-end real-time data engineering using industry-standard tools.
