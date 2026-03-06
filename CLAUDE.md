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
| **Last updated** | 2026-03-06 (Fixed dbt container volume mount + deprecated test syntax) |

---

## Working Directory

```
c:/Users/amigomusa/OneDrive - Amigomusa/Data Engineer/snowflake_dbt_airflow/real_time_stock_analytics/
```

> Platform: Windows 11. All Docker containers run Linux internally — use Unix paths inside containers and in Python/SQL code.

---

## Architecture Overview

```
Finnhub API (dual-mode)
        │
        ├─ WebSocket (default): real-time trade ticks (sub-second)
        └─ REST API (optional): 15-min polling intervals
        │
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
| Data source | Finnhub (WebSocket + REST API dual-mode) | — |
| Streaming | Apache Kafka (Confluent) | 7.6.1 |
| Object storage | AWS S3 | — |
| Data warehouse | Snowflake | — |
| Ingestion | Snowpipe (AUTO_INGEST via SQS) | — |
| Transformation | dbt Core + dbt-snowflake | 1.8.2 |
| Orchestration | Apache Airflow (CeleryExecutor) | 3.1.7 |
| Containerization | Docker Compose | — |
| Package manager | uv (Astral) | latest |
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
| `finnhub-producer` | Finnhub (WS or REST) → Kafka | — |
| `s3-consumer` | Kafka → S3 micro-batches | — |
| `postgres` | Airflow metadata DB | internal |
| `redis` | Airflow Celery broker | internal |
| `airflow-webserver` | Airflow UI | 8081 |
| `airflow-scheduler` | DAG scheduling | — |
| `airflow-worker` | Task execution | — |
| `airflow-triggerer` | Deferred tasks | — |
| `dbt` | dbt runner (keep-alive) | — |

---

## Finnhub Producer Modes

The `finnhub-producer` service supports two modes, configurable via `.env`:

### Mode 1: WebSocket (Default)
- **Config:** `FINNHUB_MODE=websocket`
- **Data frequency:** Sub-second (every trade tick)
- **Use case:** Real-time streaming demo, high-frequency analysis
- **Data volume:** High (100K+ records/hour per symbol during active trading)
- **Message schema:**
  ```json
  {
    "symbol": "AAPL",
    "price": 182.35,
    "volume": 150,
    "timestamp": 1711900800000,
    "conditions": ["1"]
  }
  ```

### Mode 2: REST API Polling
- **Config:** `FINNHUB_MODE=polling`
- **Data frequency:** Every 15 minutes (configurable via `POLL_INTERVAL_MINUTES`)
- **Use case:** Cost optimization, hourly analytics
- **Data volume:** Low (4 records/hour per symbol)
- **Message schema:**
  ```json
  {
    "symbol": "AAPL",
    "current_price": 182.35,
    "open_price": 181.50,
    "high_price": 183.10,
    "low_price": 181.20,
    "previous_close": 180.95,
    "timestamp": 1711900800,
    "poll_time": 1711900815
  }
  ```

### How to Switch Modes
1. Edit `.env` and change `FINNHUB_MODE=websocket` to `FINNHUB_MODE=polling` (or vice versa)
2. Restart the producer: `docker compose restart finnhub-producer`
3. Verify: `docker logs finnhub-producer --tail 10`

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
- **Finnhub producer modes** — supports dual-mode operation via `FINNHUB_MODE` env var: `websocket` (real-time streaming, default) or `polling` (REST API every 15 mins); switch modes by editing `.env` and restarting container
- **Airflow 3 commands** — `airflow webserver` is removed → use `airflow api-server`; `airflow fab create-user` does not exist → use `airflow users create`; auth manager config key is `AIRFLOW__CORE__AUTH_MANAGER`; secret key is `AIRFLOW__API__SECRET_KEY` (not `AIRFLOW__WEBSERVER__SECRET_KEY`)
- **Airflow UI credentials** — username and password are set via `AIRFLOW_WWW_USER_USERNAME` and `AIRFLOW_WWW_USER_PASSWORD` in `.env`; `airflow-init` container creates the admin user on first run using `airflow users create`
- **Airflow connections**: `aws_default` is provisioned by `airflow-init`; `snowflake_default` must be added manually or via a future init step
- **Snowflake Snowpipe** requires an SQS notification on the S3 prefix after script 06
- **dbt `profiles.yml` reads from env vars** — never hard-code credentials in it
- **Package manager is uv** — dependencies declared in `pyproject.toml` per service; `uv.lock` committed for reproducible builds; never revert to bare `pip install` or `requirements.txt`
- **uv Docker pattern** — set `ENV VIRTUAL_ENV=<workdir>/.venv` and `PATH="<venv>/bin:$PATH"` before `RUN uv sync --no-dev --frozen`; do NOT use `--system` (removed in uv v0.5+) or `UV_SYSTEM_PYTHON=1` (unreliable); uv creates `.venv`, PATH makes runtime `python` use it
- **Dependency workflow**: add to `pyproject.toml` → run `make lock` → commit both files → Docker rebuilds from lockfile
- **Airflow is the exception** — providers installed via `uv pip install --system . --constraint <url>` (no lockfile); Airflow core is pre-installed in the base image and manages its own transitive deps
- **docker-compose credential pattern** — all secrets and credentials reference `.env` via `${VAR}` interpolation or `env_file: .env`; hardcoded values in `environment:` blocks are topology/non-secret config only (ports, executor type, etc.); never hardcode passwords, keys, or connection strings directly in `docker-compose.yml`
- **Postgres + Airflow credential alignment** — `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` in `.env` must match the credentials embedded in `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` and `AIRFLOW__CELERY__RESULT_BACKEND`; changing one requires changing both; if Postgres volume already exists with old credentials, run `docker compose down -v` to wipe and reinitialize
- **Local dev**: `make dev-setup` creates per-service `.venv/` folders with full dev deps; point VS Code Python interpreter to the relevant `.venv`
- **Never commit `.venv/`** — already in `.gitignore` via `**/.venv/`
- **Running dbt commands** — use `docker compose exec dbt dbt <command> --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt`; run `dbt deps` first after rebuilding the container; on Git Bash (Windows), use double slashes (`//usr/app/dbt`) or `MSYS_NO_PATHCONV=1` prefix to prevent path conversion; CMD/PowerShell work without modification
- **ALWAYS update CLAUDE.md** — whenever ANY feature is added, changed, or removed, immediately update this file with: architecture changes, new configuration options, updated conventions, and change log entry; this is MANDATORY and non-negotiable

---

## Change Log

| Date | Change |
|---|---|
| 2026-03-02 | Initial scaffold created: Kafka, S3, Snowpipe, dbt, Airflow, Docker Compose |
| 2026-03-02 | CLAUDE.md and README.md added |
| 2026-03-02 | Migrated all Dockerfiles from pip to uv (ghcr.io/astral-sh/uv:latest) |
| 2026-03-02 | Upgraded Airflow 2.9.1 → 3.1.7; providers: amazon 9.21.0, snowflake 6.9.1; added providers-fab for auth |
| 2026-03-02 | Full professional uv setup: pyproject.toml + uv.lock per service; `uv sync --frozen` in Docker; `make dev-setup` + `make lock` targets |
| 2026-03-04 | Fixed Docker uv install: replaced `--system` flag (removed in uv v0.5) with `ENV VIRTUAL_ENV + PATH` pattern; added `.dockerignore` per service |
| 2026-03-04 | Wired all docker-compose credentials to `.env`: Postgres service uses `${POSTGRES_USER/PASSWORD/DB}`; Airflow connection strings use `${AIRFLOW__DATABASE__SQL_ALCHEMY_CONN}` and `${AIRFLOW__CELERY__RESULT_BACKEND}` |
| 2026-03-04 | Fixed Airflow 3 breaking changes: `webserver` → `api-server`; attempted `airflow fab create-user` (incorrect); `AIRFLOW__AUTH_MANAGER` → `AIRFLOW__CORE__AUTH_MANAGER`; `AIRFLOW__WEBSERVER__SECRET_KEY` → `AIRFLOW__API__SECRET_KEY` |
| 2026-03-05 | Fixed Airflow user creation: corrected `airflow fab create-user` (non-existent in Airflow 3.1.7) → `airflow users create`; verified admin user creation from `AIRFLOW_WWW_USER_USERNAME` and `AIRFLOW_WWW_USER_PASSWORD` env vars |
| 2026-03-05 | **Dual-mode Finnhub producer**: Implemented switchable WebSocket (real-time) and REST API (15-min polling) modes via `FINNHUB_MODE` env var; added `requests` dependency; updated `config.py`, `finnhub_producer.py`, `pyproject.toml`, `.env`, `.env.example`; regenerated lockfile; default mode is `websocket` for real-time streaming demo |
| 2026-03-06 | Fixed dbt container: added `dbt_venv` named volume to preserve `.venv` from bind mount overwrite; updated deprecated `tests:` → `data_tests:` in `_staging.yml`, `_int_models.yml`, `_marts.yml` for dbt 1.8 compatibility; upgraded `dbt_utils` 1.1.1 → 1.3.3 and `audit_helper` 0.9.0 → 0.13.0 |
