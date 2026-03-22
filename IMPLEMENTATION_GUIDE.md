# Step-by-Step Implementation Guide

> Complete guide to setting up the Real-Time Stock Analytics Pipeline from scratch.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop | Engine 24+, Compose plugin |
| AWS account | S3 bucket + IAM permissions |
| Snowflake account | Trial account is sufficient |
| Finnhub account | Free tier supports both WebSocket and REST API |
| Power BI Desktop | Windows; free to download |

---

## Step 1 — Clone & Bootstrap

```bash
git clone <your-repo-url>
cd real_time_stock_analytics
bash scripts/init.sh
```

`init.sh` creates `.env` from `.env.example` and generates an Airflow Fernet key. Copy the Fernet key output into `.env`.

---

## Step 2 — Fill in `.env` Credentials

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

# Finnhub producer mode (choose one):
FINNHUB_MODE=websocket           # Real-time streaming (default, for demo)
# FINNHUB_MODE=polling           # 15-min intervals (for cost optimization)
POLL_INTERVAL_MINUTES=15         # Only used in polling mode
```

---

## Step 2.1 — Choose Your Finnhub Data Mode

The producer supports two modes:

**WebSocket Mode (Default)**
- **Best for:** Portfolio demonstration, real-time streaming showcase
- **Data frequency:** Sub-second (every trade tick)
- **Volume:** High (100K+ records/hour during active trading)
- **Cost:** Higher S3 storage and Snowflake ingestion
- **Config:** `FINNHUB_MODE=websocket` (already set)

**REST API Polling Mode**
- **Best for:** Cost optimization, hourly analytics focus
- **Data frequency:** Every 15 minutes (configurable)
- **Volume:** Low (4 records/hour per symbol)
- **Cost:** Minimal S3 storage and Snowflake ingestion
- **Config:** Change `FINNHUB_MODE=polling` in `.env`

**To switch modes later:**
1. Edit `.env` and change `FINNHUB_MODE=websocket` to `FINNHUB_MODE=polling` (or vice versa)
2. Recreate the producer container (restart doesn't reload env vars):
   ```bash
   docker compose up -d --force-recreate finnhub-producer
   ```
3. Verify: `docker logs finnhub-producer --tail 10`

> **Recommendation:** Start with WebSocket mode to see real-time data flowing. Switch to polling mode after your demo to reduce costs.

### Tracked Symbols (20 Total)

The pipeline tracks these 20 major NASDAQ and NYSE stocks:

```
AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, JPM, V, JNJ
UNH, XOM, WMT, MA, NFLX, AVGO, AMD, CRM, ORCL, DIS
```

To modify symbols, update both:
- `kafka/producer/config.py` — real-time streaming
- `dbt/seeds/stock_symbols.csv` — company metadata

---

## Step 3 — Create the S3 Bucket

In your AWS Console (or via CLI):

```bash
aws s3 mb s3://your-stock-analytics-bucket --region us-east-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket your-stock-analytics-bucket \
  --versioning-configuration Status=Enabled
```

---

## Step 4 — Provision Snowflake (run scripts in order)

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

## Step 5 — Start All Services

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
| Streamlit (Real-time) | http://localhost:8501 | — |
| Airflow | http://localhost:8081 | admin / admin |
| Kafka UI | http://localhost:8080 | — |

---

## Step 6 — Verify Data Is Flowing

> **Note:** Data flow frequency depends on your `FINNHUB_MODE` setting:
> - **WebSocket mode:** Expect messages every few seconds during market hours (9:30 AM - 4:00 PM ET)
> - **Polling mode:** New data arrives every 15 minutes (configurable)

**Kafka** — check the topic has messages:
```bash
make kafka-topics
# You should see: stock.trades
```
Open Kafka UI → Topics → `stock.trades` → Messages to see live trade events.

**Streamlit** — open http://localhost:8501 to see live prices updating in real-time. The consumer writes to Redis alongside S3, and Streamlit reads from Redis.

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

## Step 7 — Run dbt Transformations

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

## Step 8 — Enable Airflow DAGs

1. Open Airflow at http://localhost:8081
2. Go to **DAGs**
3. Toggle on `stock_analytics_pipeline` (hourly) and `dbt_transforms` (15 min)
4. Trigger `stock_analytics_pipeline` manually for the first run
5. Monitor task status in the **Grid** view

---

## Step 9 — Backfill Historical Data (Optional)

For Yahoo Finance-style period filters (1D, 5D, 1M, 6M, YTD, 1Y, 5Y, All), backfill historical data from yfinance:

```bash
# Install dependencies
cd scripts && uv sync && cd ..

# Run backfill (fetches 5Y daily + 2Y hourly for all 20 symbols)
uv run --directory scripts python backfill_historical.py

# Rebuild dbt models with historical data
docker compose exec dbt dbt run --full-refresh \
  --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt
```

The backfill loads data into `INTERMEDIATE.STOCK_OHLCV_HISTORICAL`, which is automatically unioned with real-time data in the `int_stock_ohlcv` model.

---

## Step 10 — Connect Power BI to Snowflake

1. Open **Power BI Desktop**
2. **Get Data** → **Snowflake**
3. Enter your Snowflake account URL (e.g., `xy12345.snowflakecomputing.com`)
4. Database: `STOCK_ANALYTICS_DB` | Warehouse: `STOCK_ANALYTICS_WH`
5. Authenticate with `STOCK_ANALYTICS_SVC` credentials
6. Load these tables:
   - `MARTS.FCT_STOCK_TRADES`
   - `MARTS.FCT_STOCK_OHLCV_HOURLY`
   - `MARTS.DIM_COMPANIES`
   - `MARTS.DIM_DATE`
7. Build your five dashboard pages (one per business question)
8. Set **Direct Query** mode for near-real-time refresh

> Tip: Use Power BI's **Auto Page Refresh** (available in Direct Query mode) to set a refresh interval matching your `dbt_transforms` schedule (15 minutes).

---

## Step 11 — Monitoring & Maintenance

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

## Daily Operations (During Market Hours)

If running the pipeline for extended periods:

| Time (ET) | Action |
|-----------|--------|
| ~9:00 AM | Start Docker Desktop |
| ~9:15 AM | Run `docker compose up -d` |
| 9:30 AM | Market opens, data starts flowing |
| 4:00 PM | Market closes, WebSocket stream stops |
| After 4:00 PM | `docker compose down`, close Docker Desktop |

> **Tip:** WebSocket mode only produces data during market hours. No need to run Docker overnight or on weekends.

---

## Troubleshooting

### No data in marts tables
1. Check if data is in RAW: `SELECT COUNT(*) FROM RAW.STOCK_TRADES_RAW`
2. If RAW is empty, check Snowpipe: `SELECT SYSTEM$PIPE_STATUS('RAW.TRADES_PIPE')`
3. If Snowpipe has no pending files, check S3: `aws s3 ls s3://bucket/raw/trades/`
4. If S3 is empty, check consumer logs: `docker logs s3-consumer`

### Snowpipe not ingesting
```sql
-- Force refresh to pick up missed files
ALTER PIPE STOCK_ANALYTICS_DB.RAW.TRADES_PIPE REFRESH;

-- Check copy history for errors
SELECT * FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME => 'STOCK_TRADES_RAW',
    START_TIME => DATEADD(HOURS, -24, CURRENT_TIMESTAMP())
)) ORDER BY LAST_LOAD_TIME DESC;
```

### Environment variable changes not taking effect
`docker compose restart` doesn't reload `.env` — use:
```bash
docker compose up -d --force-recreate <service-name>
```

### Market hours timestamp confusion
In WebSocket mode, data only flows during market hours (9:30 AM - 4:00 PM ET). If you see "old" timestamps, the market may be closed. Check current market status before debugging.

### Streamlit shows "No stock data available"
1. Check if the market is open (9:30 AM - 4:00 PM ET, Mon-Fri)
2. Check consumer logs: `docker logs s3-consumer` — look for "Redis connected"
3. Check Redis has data: `docker exec -it airflow-redis redis-cli SMEMBERS stock:symbols`
4. If Redis is empty, wait for trades to flow through the pipeline
