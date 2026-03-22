# Real-Time Stock Analytics Pipeline

> An end-to-end data engineering portfolio project that streams live stock market data from the Finnhub API (WebSocket or REST API) through Kafka, lands it in AWS S3, auto-ingests it into Snowflake via Snowpipe, transforms it with dbt Core, orchestrates everything with Apache Airflow, and delivers insights through **Power BI** (historical analytics) and **Streamlit** (real-time monitoring) — all containerized with Docker.

---

## Project Overview

This project simulates a production-grade real-time analytics platform that a financial services company would use to monitor stock market activity. It demonstrates the full modern data engineering lifecycle:

- **Ingestion** of live market data via dual-mode producer (WebSocket real-time streaming or REST API 15-min polling)
- **Streaming** through a fault-tolerant Kafka message bus
- **Real-time caching** in Redis for instant price lookups (sub-second latency)
- **Landing** micro-batched NDJSON files in a partitioned S3 data lake
- **Auto-ingestion** into Snowflake using Snowpipe event-driven triggers
- **Transformation** through a layered dbt project (staging → intermediate → marts)
- **Orchestration** of the entire pipeline via scheduled Airflow DAGs
- **Dual visualization** — Power BI for historical analytics, Streamlit for real-time monitoring

The stack mirrors what you would find at any trading desk company running a modern cloud data platform.

---

## Business Questions & Deliverables

The pipeline is designed to answer five real-world business questions that a portfolio manager, quant analyst, or trading desk would care about.
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
| Data source | [Finnhub](https://finnhub.io) (WebSocket + REST API) | Dual-mode: Real-time trades or 15-min polling |
| Message bus | Apache Kafka (Confluent 7.6.1) | Durable, fault-tolerant event queue |
| Real-time cache | Redis 7.2 | Sub-second price lookups for live dashboard |
| Object storage | AWS S3 | Partitioned NDJSON data lake |
| Auto-ingestion | Snowflake Snowpipe (SQS) | Event-driven, zero-touch S3 → Snowflake |
| Data warehouse | Snowflake | Cloud-native analytical SQL engine |
| Transformation | dbt Core 1.8.2 + dbt-snowflake | Modular, tested SQL transformations |
| Orchestration | Apache Airflow 2.10.4 | DAG scheduling, monitoring, alerting |
| Containerization | Docker Compose | Reproducible local environment |
| Package manager | [uv](https://github.com/astral-sh/uv) (Astral) | Fast Rust-based pip replacement in all Docker images |
| Visualization (historical) | Microsoft Power BI | Business dashboards via Snowflake connector |
| Visualization (real-time) | Streamlit 1.32.2 | Live price ticker with auto-refresh |
| Language | Python 3.11 | Producer, consumer, DAG logic |
| IDE | VS Code | Development environment |

---

## Key Features

- **Dual-mode data ingestion** — Switch between WebSocket (sub-second real-time trades) and REST API (15-min polling) via environment variable; default is WebSocket for portfolio demo, polling mode for cost optimization
- **Real-time price cache** — Redis stores latest prices with 5-minute TTL; consumer writes to Redis alongside S3 for instant lookups
- **Dual visualization layer** — Streamlit for live price monitoring (2-second refresh), Power BI for historical analytics and business dashboards
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

## Development Approach

This project was built using modern data engineering practices that mirror how professional data engineers work at leading tech companies in 2026.

### AI-Assisted Development
I used **Claude Code** as a development accelerator to help me move 5x faster.

**What this means:**
- AI handled code scaffolding, boilerplate generation, and documentation formatting
- **I designed** the architecture, made the technical decisions, and owned the business logic

### My Core Contributions

**Architecture & Design Decisions:**
- Dual-mode Finnhub producer (WebSocket vs REST API) with cost/latency trade-offs
- Redis cache layer for real-time price lookups (sub-second latency)
- Dual visualization strategy: Streamlit for operational monitoring, Power BI for historical analytics
- Layered dbt transformation strategy (staging → intermediate → marts)
- Incremental merge patterns with surrogate keys for idempotency
- Snowpipe auto-ingest architecture with SQS event notifications
- Airflow DAG orchestration strategy (hourly full pipeline + 15-min near-real-time)

**Infrastructure & Configuration:**
- AWS IAM role setup with Snowflake Storage Integration (no static credentials)
- Snowflake database architecture (4 schemas, roles, warehouse sizing)
- Docker Compose service orchestration with health checks and dependencies
- Kafka topic partitioning and consumer micro-batching strategy
- dbt project structure with custom macros and data quality tests

**Business Logic:**
- Designed 5 analytical questions the pipeline answers for portfolio managers
- Built dbt models for OHLCV aggregation, VWAP calculation, volatility metrics
- Created data quality tests (unique constraints, not-null checks, positive volume assertions)

### The Bottom Line
I architected the system, made the hard decisions, and owned the implementation. AI helped me execute efficiently.

---

## Repository Structure

```
real_time_stock_analytics/
│
├── CLAUDE.md                          # Claude Code project context (auto-updated)
├── README.md                          # This file
├── IMPLEMENTATION_GUIDE.md            # Detailed step-by-step setup instructions
├── INSTRUCTIONS.md                    # Complete execution guide (12 phases)
├── docker-compose.yml                 # All 12 services defined
├── .env.example                       # Template for all credentials
├── .gitignore
├── .python-version                    # Pins Python 3.11 for uv and pyenv
├── Makefile                           # make up / down / dev-setup / lock / dbt-run / kafka-topics
│
├── kafka/
│   ├── producer/
│   │   ├── finnhub_producer.py        # Dual-mode: WebSocket (real-time) or REST API (polling)
│   │   ├── config.py                  # Symbol list, Kafka config, mode selector
│   │   ├── pyproject.toml             # Dependency declaration
│   │   ├── uv.lock                    # Pinned lockfile (committed to git)
│   │   └── Dockerfile                 # uv sync --frozen for reproducible builds
│   └── consumer/
│       ├── s3_consumer.py             # Kafka → S3 + Redis cache writer
│       ├── config.py                  # Batch size, flush interval, S3/Redis config
│       ├── pyproject.toml
│       ├── uv.lock
│       └── Dockerfile
│
├── streamlit/
│   ├── app.py                         # Real-time stock monitor dashboard
│   ├── config.py                      # Redis connection, symbol metadata
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
│
├── airflow/
│   ├── Dockerfile                     # Airflow 2.10.4 + providers (constraint-based)
│   ├── pyproject.toml                 # Providers + dev group (apache-airflow for IDE)
│   ├── dags/
│   │   ├── stock_pipeline_dag.py      # Hourly: S3 check → Snowpipe → dbt run → test
│   │   └── dbt_transform_dag.py       # Every 15 min: standalone dbt transforms
│   ├── plugins/                       # Custom Airflow operators (future use)
│   └── logs/                          # Airflow task logs (git-ignored)
│
├── dbt/
│   ├── Dockerfile                     # dbt-core + dbt-snowflake (uv sync --frozen)
│   ├── entrypoint.sh                  # Ensures venv exists on container startup
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
  │  Finnhub    │  DUAL-MODE   │   Kafka     │
  │  API        │──────────────│   Producer  │
  │             │ WebSocket OR │             │
  │  • WebSocket│  REST (15m)  └──────┬──────┘
  │  • REST API │                     │ topic: stock.trades
  └─────────────┘                     │ (3 partitions)
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



## Quick Start

### Prerequisites

- Docker Desktop (Engine 24+)
- AWS account with S3 access
- Snowflake account (trial is fine)
- Finnhub API key (free tier)

### Get Running in 5 Minutes

```bash
# 1. Clone and bootstrap
git clone <your-repo-url>
cd real_time_stock_analytics
bash scripts/init.sh

# 2. Fill in credentials
cp .env.example .env
# Edit .env with your API keys and passwords

# 3. Start all services
make up

# 4. Verify everything is healthy
docker compose ps
```

| Service | URL | Purpose |
|---------|-----|---------|
| Streamlit | http://localhost:8501 | Real-time stock monitor |
| Airflow UI | http://localhost:8081 | Pipeline orchestration |
| Kafka UI | http://localhost:8080 | Message monitoring |
| dbt Docs | http://localhost:8082 | Data lineage |

> **Full setup instructions:**
> - **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** — Condensed 10-step guide
> - **[INSTRUCTIONS.md](INSTRUCTIONS.md)** — Complete 12-phase walkthrough with troubleshooting

---

## Author

**Amigomusa** | Data Engineering Portfolio
> Built to demonstrate end-to-end real-time data engineering using industry-standard tools.

### Visualization Architecture

| Dashboard | Data Source | Latency | Use Case |
|-----------|-------------|---------|----------|
| **Streamlit** | Redis cache | ~2 seconds | Real-time price monitoring, live ticker |
| **Power BI** | Snowflake marts | ~15 minutes | Historical analytics, trend analysis, business reporting |

This dual-layer approach mirrors production systems where operational dashboards (Streamlit) serve traders needing instant updates, while analytical dashboards (Power BI) serve portfolio managers analyzing trends over time.
