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
| **Last updated** | 2026-03-12 (S3 + Snowflake timezone fixes, dim_date, fact table enhancements) |

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
        │  NDJSON files partitioned by trade timestamp (US/Eastern)
        ▼
  AWS S3          s3://<bucket>/raw/trades/year=.../...  (hours = ET market hours)
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
| Orchestration | Apache Airflow (LocalExecutor) | 2.10.4 |
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
| `airflow-worker` | ~~Removed~~ (LocalExecutor runs tasks in scheduler) | — |
| `airflow-triggerer` | Deferred tasks | — |
| `dbt` | dbt runner (keep-alive) | 8082 (docs) |

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
2. Recreate the producer (restart doesn't reload env vars): `docker compose up -d --force-recreate finnhub-producer`
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
| `dim_date` | marts | 1 row per calendar day (date spine) |

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
README.md                         ← project overview + quick start
IMPLEMENTATION_GUIDE.md           ← condensed 10-step setup guide
INSTRUCTIONS.md                   ← complete 12-phase walkthrough
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
- **S3 partitioning is by trade timestamp in US/Eastern** — hour folders (hour=09 to hour=16) align with market hours; consumer extracts timestamp from each record (handles both WebSocket ms and Polling s formats) and groups by hour before writing; `zoneinfo.ZoneInfo("America/New_York")` handles EST/EDT transitions automatically
- **Snowflake timestamps are US/Eastern** — `stg_stock_trades` converts raw UTC timestamps to America/New_York using `convert_timezone()`; all downstream models inherit this timezone
- **date_key pattern for Power BI** — `dim_date.date_key` is integer YYYYMMDD (e.g., 20260312); fact tables (`fct_stock_trades`, `fct_stock_ohlcv_hourly`) include matching `date_key` FK for efficient relationships; `traded_hour` is TIME type, `traded_date` is DATE type
- **Kafka internal listener is `kafka:29092`** — external is `localhost:9092`; use the internal one inside Docker
- **Finnhub producer modes** — supports dual-mode operation via `FINNHUB_MODE` env var: `websocket` (real-time streaming, default) or `polling` (REST API every 15 mins); switch modes by editing `.env` and running `docker compose up -d --force-recreate finnhub-producer`
- **US market hours** — Regular trading: 9:30 AM - 4:00 PM ET (14:30 - 21:00 UTC); WebSocket mode only produces data during market hours; polling mode returns data 24/7 but `timestamp` field reflects last trade time (stale on weekends/holidays)
- **Airflow 2.10.4 commands** — use `airflow webserver` (not api-server); user creation via `airflow users create`; secret key is `AIRFLOW__WEBSERVER__SECRET_KEY`; healthcheck endpoint is `/health`; LocalExecutor runs tasks directly in scheduler (no separate worker needed)
- **Airflow UI credentials** — username and password are set via `AIRFLOW_WWW_USER_USERNAME` and `AIRFLOW_WWW_USER_PASSWORD` in `.env`; `airflow-init` container creates the admin user on first run using `airflow users create`
- **Airflow connections**: `aws_default` and `snowflake_default` are both provisioned by `airflow-init` on first startup
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
- **dbt + Airflow architecture** — `dbt-snowflake` and `airflow-providers-snowflake` have incompatible `snowflake-connector-python` versions; dbt runs in a separate container (`dbt-runner`); Airflow DAGs use `BashOperator` with `docker exec dbt-runner` to run dbt commands in the persistent container; this approach is faster and more reliable than `DockerOperator` (no ephemeral container spawning); never install dbt in the Airflow container
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
| 2026-03-08 | Added port 8082 mapping to dbt service for `dbt docs serve` local previews |
| 2026-03-08 | Fixed Airflow 3 Celery worker: added `AIRFLOW__WORKERS__EXECUTION_API_SERVER_URL` pointing to `http://airflow-webserver:8080/execution/` — required for workers to report task status via the new Task Execution API |
| 2026-03-08 | Fixed Airflow 3 webserver healthcheck: updated `/health` → `/api/v2/monitor/health` (endpoint moved in Airflow 3) |
| 2026-03-08 | **Refactored dbt execution to DockerOperator**: `dbt-snowflake` and `airflow-providers-snowflake` have incompatible `snowflake-connector-python` versions (dbt needs <4.0, Airflow needs ==4.0); solution: keep dbt in separate container, use `DockerOperator` to run dbt commands; added `apache-airflow-providers-docker`, mounted Docker socket in scheduler, rewrote both DAGs to use `DockerOperator` instead of `BashOperator` |
| 2026-03-08 | **Downgraded Airflow 3.1.7 → 2.10.4**: Airflow 3.1.7's Task SDK requires an Execution API that doesn't work (returns 404), breaking both CeleryExecutor and LocalExecutor; Airflow 2.10.4 uses stable, proven execution model; updated Dockerfile, pyproject.toml, docker-compose.yml (webserver command, healthcheck URL, removed Airflow 3-specific config); fixed DAG imports from `airflow.providers.standard.operators` → `airflow.operators` |
| 2026-03-09 | **Replaced DockerOperator with BashOperator + docker exec**: DockerOperator spawned ephemeral containers without bind-mounted dbt files, causing "Connection refused" errors; solution: use `BashOperator` with `docker exec dbt-runner` to run dbt commands in the persistent dbt container; added `docker.io` to Airflow Dockerfile; added dbt healthcheck + depends_on; added `snowflake_default` connection to `airflow-init`; removed `apache-airflow-providers-docker` (no longer needed) |
| 2026-03-09 | **Documentation reorganization**: Split README.md step-by-step guide into `IMPLEMENTATION_GUIDE.md` (condensed 10-step) and `INSTRUCTIONS.md` (complete 12-phase walkthrough with TOC and troubleshooting); added market hours documentation; fixed Airflow version references (3.1.7 → 2.10.4); documented `--force-recreate` requirement for env var changes |
| 2026-03-12 | **S3 partitioning fix**: Changed S3 consumer to partition by trade timestamp in US/Eastern timezone instead of flush time in UTC; records now land in correct market-hour partitions (hour=09 to hour=16) for Power BI heatmaps; handles both WebSocket (ms) and Polling (s) timestamp formats; uses Python `zoneinfo` (no new dependencies) |
| 2026-03-12 | **Snowflake timezone fix**: Updated `stg_stock_trades` to convert timestamps from UTC to US/Eastern using `convert_timezone('UTC', 'America/New_York', ...)`; all downstream models now show trades in market-local time |
| 2026-03-12 | **dim_date model**: Fixed incomplete model (missing SELECT); changed `date_key` from hash to integer YYYYMMDD format (e.g., 20260312) for efficient Power BI relationships; added calendar attributes (quarter, day_of_week, day_name, month_name, is_weekday, is_trading_day) |
| 2026-03-12 | **Fact table enhancements**: Added `date_key` FK to `fct_stock_trades` and `fct_stock_ohlcv_hourly` for dim_date joins; changed `traded_hour` to TIME type and `traded_date` to DATE type; added `traded_date`/`traded_hour` columns to `fct_stock_ohlcv_hourly` split from `hour_bucket` |
