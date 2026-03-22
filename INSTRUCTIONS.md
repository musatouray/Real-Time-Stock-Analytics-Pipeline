# Real-Time Stock Analytics Pipeline — Execution Guide

> Follow every step in order. Do not skip ahead.

All terminal commands are bash (Git Bash, WSL, or macOS/Linux terminal).
Snowflake commands run inside a Snowflake Worksheet unless stated otherwise.
Replace every `<PLACEHOLDER>` with your actual value before running.

---

## Table of Contents

| Phase | Description |
|-------|-------------|
| [Phase 0](#phase-0--prerequisites) | Prerequisites (one-time installs) |
| [Phase 1](#phase-1--clone-the-repository) | Clone the Repository |
| [Phase 2](#phase-2--configure-environment-variables) | Configure Environment Variables |
| [Phase 3](#phase-3--aws-setup) | AWS Setup |
| [Phase 4](#phase-4--snowflake-setup) | Snowflake Setup |
| [Phase 5](#phase-5--start-the-pipeline) | Start the Pipeline |
| [Phase 6](#phase-6--verify-kafka-and-s3-data-flow) | Verify Kafka and S3 Data Flow |
| [Phase 7](#phase-7--verify-snowpipe-ingestion) | Verify Snowpipe Ingestion |
| [Phase 8](#phase-8--dbt-transformations) | dbt Transformations |
| [Phase 9](#phase-9--airflow-orchestration) | Airflow Orchestration |
| [Phase 10](#phase-10--historical-data-backfill) | Historical Data Backfill (optional) |
| [Phase 11](#phase-11--power-bi-connection) | Power BI Connection |
| [Phase 12](#phase-12--local-dev-setup) | Local Dev Setup (optional) |
| [Phase 13](#phase-13--daily-operations) | Daily Operations |
| [Quick Reference](#quick-reference--urls-and-ports) | URLs and Ports |
| [Troubleshooting](#troubleshooting) | Troubleshooting |

---

## Phase 0 — Prerequisites

> One-time installs

### Step 0.1 — Install Docker Desktop

Download: https://www.docker.com/products/docker-desktop/

After install, open Docker Desktop and wait for the engine to start.

```bash
docker --version
docker compose version
```

### Step 0.2 — Install uv (Python package manager)

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Verify:
```bash
uv --version
```

### Step 0.3 — Install Git

Download: https://git-scm.com/downloads

```bash
git --version
```

### Step 0.4 — Create required accounts

If you don't have them already:

| Account | URL |
|---------|-----|
| Finnhub API key | https://finnhub.io (free tier) |
| AWS account | https://aws.amazon.com |
| Snowflake trial | https://signup.snowflake.com |

Keep all credentials handy — you will need them in Phase 2.

### Step 0.5 — Review tracked symbols

The pipeline tracks 20 major NASDAQ and NYSE stocks:

| Symbol | Company | Sector |
|--------|---------|--------|
| AAPL | Apple Inc. | Technology |
| MSFT | Microsoft Corporation | Technology |
| GOOGL | Alphabet Inc. | Communication Services |
| AMZN | Amazon.com Inc. | Consumer Cyclical |
| NVDA | NVIDIA Corporation | Technology |
| TSLA | Tesla Inc. | Consumer Cyclical |
| META | Meta Platforms Inc. | Communication Services |
| JPM | JPMorgan Chase & Co. | Financial Services |
| V | Visa Inc. | Financial Services |
| JNJ | Johnson & Johnson | Healthcare |
| UNH | UnitedHealth Group Inc. | Healthcare |
| XOM | Exxon Mobil Corporation | Energy |
| WMT | Walmart Inc. | Consumer Defensive |
| MA | Mastercard Inc. | Financial Services |
| NFLX | Netflix Inc. | Communication Services |
| AVGO | Broadcom Inc. | Technology |
| AMD | Advanced Micro Devices Inc. | Technology |
| CRM | Salesforce Inc. | Technology |
| ORCL | Oracle Corporation | Technology |
| DIS | The Walt Disney Company | Communication Services |

To modify symbols, update:
- `kafka/producer/config.py` — real-time streaming
- `dbt/seeds/stock_symbols.csv` — company metadata for dim_companies

### Step 0.6 — Install Power BI Desktop (Windows only)

Download: https://www.microsoft.com/en-us/download/details.aspx?id=58494

---

## Phase 1 — Clone the Repository

### Step 1.1 — Clone and enter the project

```bash
git clone https://github.com/musatouray/Real-Time-Stock-Analytics-Pipeline.git
cd Real-Time-Stock-Analytics-Pipeline
```

### Step 1.2 — Switch to the dev branch

```bash
git checkout dev
```

### Step 1.3 — Confirm you are on dev and all files are present

```bash
git branch
ls
```

---

## Phase 2 — Configure Environment Variables

### Step 2.1 — Copy the template

```bash
cp .env.example .env
```

### Step 2.2 — Generate an Airflow Fernet key

Copy the output:

```bash
docker run --rm python:3.11-slim python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Step 2.3 — Generate an Airflow webserver secret key

Copy the output:

```bash
docker run --rm python:3.11-slim python -c \
  "import secrets; print(secrets.token_hex(32))"
```

### Step 2.4 — Open .env in VS Code and fill in every value

```bash
code .env
```

| Variable | Source |
|----------|--------|
| `FINNHUB_API_KEY` | finnhub.io dashboard |
| `AWS_ACCESS_KEY_ID` | AWS IAM console |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM console |
| `AWS_REGION` | e.g. `us-east-1` |
| `S3_BUCKET_NAME` | name you will create in Step 3.1 |
| `SNOWFLAKE_ACCOUNT` | e.g. `xy12345.snowflakecomputing.com` |
| `SNOWFLAKE_USER` | `STOCK_ANALYTICS_SVC` |
| `SNOWFLAKE_PASSWORD` | password you set in Step 4.1 |
| `AIRFLOW__CORE__FERNET_KEY` | output from Step 2.2 |
| `AIRFLOW__WEBSERVER__SECRET_KEY` | output from Step 2.3 |

### Step 2.5 — Create Airflow directories

```bash
mkdir -p airflow/logs airflow/plugins
```

---

## Phase 3 — AWS Setup

### Step 3.1 — Create the S3 bucket

```bash
aws s3 mb s3://<YOUR_BUCKET_NAME> --region us-east-1
```

Example:
```bash
aws s3 mb s3://stock-analytics-amigo --region us-east-1
```

### Step 3.2 — Verify the bucket was created

```bash
aws s3 ls | grep stock
```

### Step 3.3 — Create the IAM policy for Snowflake access

1. Open AWS Console → IAM → Policies → Create policy
2. Choose JSON and paste:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetObjectVersion"],
      "Resource": "arn:aws:s3:::<YOUR_BUCKET_NAME>/raw/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::<YOUR_BUCKET_NAME>",
      "Condition": {"StringLike": {"s3:prefix": ["raw/*"]}}
    }
  ]
}
```

3. Name the policy: `SnowflakeS3ReadPolicy`
4. Click Create policy

### Step 3.4 — Create the IAM role for Snowflake

1. Open AWS Console → IAM → Roles → Create role
2. Trusted entity type: AWS account → This account
3. Attach the policy: `SnowflakeS3ReadPolicy`
4. Role name: `SnowflakeS3Role`
5. Click Create role
6. Copy the **Role ARN** — you will need it in Step 4.5
   - Format: `arn:aws:iam::<ACCOUNT_ID>:role/SnowflakeS3Role`

> **NOTE:** You will come back to update the trust relationship in Step 4.6.

---

## Phase 4 — Snowflake Setup

> Run scripts in order, exactly as shown

Open Snowflake → Worksheets → New Worksheet

### Step 4.1 — Run script 01: Roles and service user

- **Role:** `ACCOUNTADMIN`
- **File:** `snowflake/setup/01_roles_and_users.sql`

Copy the full file contents, paste into the worksheet, run all.

**IMPORTANT:** After running, set the service account password:

```sql
ALTER USER STOCK_ANALYTICS_SVC
    SET PASSWORD = '<CHOOSE_A_STRONG_PASSWORD>';
```

Save that password — add it to `.env` as `SNOWFLAKE_PASSWORD`.

### Step 4.2 — Run script 02: Warehouse

- **Role:** `SYSADMIN`
- **File:** `snowflake/setup/02_warehouse.sql`

### Step 4.3 — Run script 03: Database and schemas

- **Role:** `SYSADMIN`
- **File:** `snowflake/setup/03_database_schemas.sql`

### Step 4.4 — Run script 04: Raw table

- **Role:** `STOCK_ANALYTICS_ROLE`
- **File:** `snowflake/setup/04_raw_tables.sql`

### Step 4.5 — Edit script 05 before running it

Open `snowflake/setup/05_s3_integration.sql` in VS Code and replace:

| Placeholder | Value |
|-------------|-------|
| `<YOUR_AWS_ACCOUNT_ID>` | your 12-digit AWS account ID |
| `<YOUR_BUCKET_NAME>` | the bucket name from Step 3.1 |

Save the file.

### Step 4.6 — Run script 05: Storage Integration

- **Role:** `ACCOUNTADMIN`

Copy the edited `05_s3_integration.sql` → paste → run all.

After it runs, execute:

```sql
DESC INTEGRATION STOCK_ANALYTICS_S3_INT;
```

Find and copy these two values:

| Value | Looks like |
|-------|------------|
| `STORAGE_AWS_IAM_USER_ARN` | `arn:aws:iam::123456789:user/abc` |
| `STORAGE_AWS_EXTERNAL_ID` | `ABC12345_SFCRole=...` |

### Step 4.7 — Update the AWS IAM trust relationship

1. Go to: AWS Console → IAM → Roles → `SnowflakeS3Role` → Trust relationships
2. Click Edit trust policy
3. Replace the content with:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "<STORAGE_AWS_IAM_USER_ARN>"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "<STORAGE_AWS_EXTERNAL_ID>"
        }
      }
    }
  ]
}
```

4. Replace both placeholders with the values from Step 4.6
5. Click Update policy

### Step 4.8 — Edit script 06 before running it

Open `snowflake/setup/06_stage_and_pipe.sql` in VS Code and replace:

- `<YOUR_BUCKET_NAME>` → your bucket name from Step 3.1

Save the file.

### Step 4.9 — Run script 06: Stage and Snowpipe

- **Role:** `STOCK_ANALYTICS_ROLE`

Copy the edited `06_stage_and_pipe.sql` → paste → run all.

After it runs, execute:

```sql
SHOW PIPES LIKE 'TRADES_PIPE';
```

Find and copy the value in the `notification_channel` column.
It looks like: `arn:aws:sqs:us-east-1:123456789:sf-snowpipe-abc...`

This is the **SQS queue ARN**.

### Step 4.10 — Configure S3 event notification

1. Go to: AWS Console → S3 → `<YOUR_BUCKET_NAME>`
2. Click Properties → Event notifications → Create event notification
3. Fill in:

| Field | Value |
|-------|-------|
| Event name | `snowpipe-trigger` |
| Prefix | `raw/trades/` |
| Event types | All object create events |
| Destination | SQS queue |
| SQS queue ARN | paste the ARN from Step 4.9 |

4. Click Save changes

### Step 4.11 — Run script 07: Final grants

- **Role:** `ACCOUNTADMIN`
- **File:** `snowflake/setup/07_grants.sql`

### Step 4.12 — Verify Snowflake setup

Run this in any worksheet (as `STOCK_ANALYTICS_ROLE`):

```sql
USE ROLE STOCK_ANALYTICS_ROLE;
USE WAREHOUSE STOCK_ANALYTICS_WH;
SHOW TABLES IN SCHEMA STOCK_ANALYTICS_DB.RAW;
SHOW PIPES   IN SCHEMA STOCK_ANALYTICS_DB.RAW;
SHOW STAGES  IN SCHEMA STOCK_ANALYTICS_DB.RAW;
```

You should see `STOCK_TRADES_RAW`, `TRADES_PIPE`, and `S3_TRADES_STAGE`.

---

## Phase 5 — Start the Pipeline

### Step 5.1 — Build and start all services

```bash
docker compose up -d --build
```

This will take 5–10 minutes on first run (downloading images, building).

### Step 5.2 — Check all containers are running

```bash
docker compose ps
```

Every container should show `STATUS = Up` or `Up (healthy)`.

Expected containers:
- `zookeeper`, `kafka`, `kafka-ui` — Kafka infrastructure
- `finnhub-producer` — Market data ingestion
- `s3-consumer` — Kafka → S3 + Redis cache
- `airflow-redis`, `airflow-postgres` — Airflow infrastructure
- `airflow-webserver`, `airflow-scheduler`, `airflow-triggerer` — Airflow services
- `dbt-runner` — dbt transformation container
- `stock-monitor` — Streamlit real-time dashboard

If any container shows `Exiting` or `Restarting`, check its logs:
```bash
docker compose logs <container-name>
```

### Step 5.3 — Wait for Airflow to fully initialize

The `airflow-init` container runs database migrations and creates the admin user:

```bash
docker compose logs -f airflow-init
```

Wait until you see: `"Admin user admin created"`

Then press `Ctrl+C` to stop tailing.

### Step 5.4 — Verify the Airflow webserver is ready

```bash
docker compose logs airflow-webserver | tail -20
```

You should see: `"Serving on http://0.0.0.0:8080"`

---

## Phase 6 — Verify Kafka and S3 Data Flow

### Step 6.1 — Open Kafka UI in your browser

URL: http://localhost:8080

Navigate to: Topics → `stock.trades` → Messages

You should see live trade events appearing every few seconds.

If the topic is empty, check the producer logs:
```bash
docker compose logs -f finnhub-producer
```

### Step 6.2 — List Kafka topics from the terminal

```bash
docker compose exec kafka kafka-topics \
    --list \
    --bootstrap-server localhost:9092
```

Expected output includes: `stock.trades`

### Step 6.3 — Check consumer logs (Kafka → S3 writer)

```bash
docker compose logs -f s3-consumer
```

You should see lines like:
```
"Uploaded 100 records → s3://your-bucket/raw/trades/year=.../..."
```

The consumer flushes every 100 records or 60 seconds, whichever comes first.

### Step 6.4 — Verify files are landing in S3

```bash
aws s3 ls s3://<YOUR_BUCKET_NAME>/raw/trades/ --recursive | head -20
```

You should see `.json` files with paths like:
```
raw/trades/year=2026/month=03/day=02/hour=14/<uuid>.json
```

### Step 6.5 — Inspect one of the S3 files

```bash
aws s3 cp s3://<YOUR_BUCKET_NAME>/raw/trades/year=2026/month=03/day=02/<path>.json -
```

You should see newline-delimited JSON trade records.

### Step 6.6 — Verify Streamlit real-time dashboard

Open in browser: http://localhost:8501

You should see:
- Live stock prices updating every 2 seconds
- Price change indicators (green/red)
- Volume and timestamp for each symbol
- Sector filter in the sidebar

If you see "No stock data available":
- Check if the market is open (9:30 AM - 4:00 PM ET)
- Wait 1-2 minutes for data to flow through Kafka → Consumer → Redis

### Step 6.7 — Verify Redis cache from command line

```bash
# Check which symbols are cached
docker exec -it airflow-redis redis-cli SMEMBERS stock:symbols

# Check data for a specific symbol
docker exec -it airflow-redis redis-cli HGETALL stock:AAPL:latest
```

---

## Phase 7 — Verify Snowpipe Ingestion

### Step 7.1 — Check Snowpipe status

In Snowflake worksheet:

```sql
SELECT SYSTEM$PIPE_STATUS('STOCK_ANALYTICS_DB.RAW.TRADES_PIPE');
```

Look for `"pendingFileCount"` and `"executionState": "RUNNING"`.

It takes 1–3 minutes for the first files to be ingested after S3 upload.

### Step 7.2 — Count raw records

```sql
SELECT COUNT(*) FROM STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW;
```

After a few minutes you should see a count greater than 0.

### Step 7.3 — Preview raw records

```sql
SELECT
    record_content:symbol::VARCHAR  AS symbol,
    record_content:price::FLOAT     AS price,
    record_content:volume::INTEGER  AS volume,
    record_content:timestamp::BIGINT AS timestamp_ms
FROM STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW
LIMIT 10;
```

### Step 7.4 — Check copy history

```sql
SELECT
    file_name,
    row_count,
    status,
    first_error_message
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME  => 'STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW',
    START_TIME  => DATEADD(hour, -1, CURRENT_TIMESTAMP())
))
ORDER BY last_load_time DESC
LIMIT 20;
```

`STATUS` column should show `"Loaded"` for each file.

### Step 7.5 — If Snowpipe is not ingesting, manually refresh it

```sql
ALTER PIPE STOCK_ANALYTICS_DB.RAW.TRADES_PIPE REFRESH;
```

Then re-run Step 7.2 after waiting 2 minutes.

---

## Phase 8 — dbt Transformations

### Step 8.1 — Load reference data

Seed CSV → Snowflake SEEDS schema:

```bash
docker compose exec dbt dbt seed \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

Expected: 1 seed loaded (`stock_symbols.csv` → `SEEDS.STOCK_SYMBOLS` table)

### Step 8.2 — Run staging models

Views on top of raw data:

```bash
docker compose exec dbt dbt run \
    --select staging \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

Expected: 2 models created (`stg_stock_trades`, `stg_company_profiles`)

### Step 8.3 — Run intermediate models

Hourly OHLCV and volatility tables:

```bash
docker compose exec dbt dbt run \
    --select intermediate \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

Expected: 2 models created (`int_stock_ohlcv`, `int_stock_volatility`)

### Step 8.4 — Run mart models

Final business-facing tables:

```bash
docker compose exec dbt dbt run \
    --select marts \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

Expected: 4 models created (`fct_stock_trades`, `fct_stock_ohlcv_hourly`, `dim_companies`, `dim_date`)

### Step 8.5 — Run all models at once

Shortcut for above 3 steps:

```bash
docker compose exec dbt dbt run \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

### Step 8.6 — Run data quality tests

```bash
docker compose exec dbt dbt test \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

All tests should pass (unique, not_null, positive volume).

### Step 8.7 — Verify transformed data in Snowflake

```sql
SELECT
    symbol,
    hour_bucket,
    open_price,
    close_price,
    vwap,
    total_volume,
    pct_change,
    prev_day_close,
    change_from_prev_close,
    pct_change_from_prev_close
FROM STOCK_ANALYTICS_DB.MARTS.FCT_STOCK_OHLCV_HOURLY
ORDER BY hour_bucket DESC
LIMIT 20;
```

Key columns:
- `pct_change`: Hourly change (close - open) / open
- `prev_day_close`: Previous trading day's closing price
- `change_from_prev_close`: Dollar change from previous day's close (Yahoo Finance style)
- `pct_change_from_prev_close`: Percentage change from previous day's close

### Step 8.8 — Generate and serve dbt documentation

```bash
docker compose exec dbt dbt docs generate \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt

docker compose exec -d dbt dbt docs serve \
    --port 8082 \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

Open in browser: http://localhost:8082

Explore the lineage graph: click a model → then "See lineage graph" button.

---

## Phase 9 — Airflow Orchestration

### Step 9.1 — Open Airflow UI

| Field | Value |
|-------|-------|
| URL | http://localhost:8081 |
| Username | admin |
| Password | admin |

### Step 9.2 — Add the Snowflake connection

Go to: Admin → Connections → + (Add a new record)

| Field | Value |
|-------|-------|
| Connection Id | `snowflake_default` |
| Connection Type | Snowflake |
| Host | `<SNOWFLAKE_ACCOUNT>` (e.g. xy12345.snowflakecomputing.com) |
| Login | `STOCK_ANALYTICS_SVC` |
| Password | `<SNOWFLAKE_PASSWORD>` |
| Schema | `RAW` |
| Extra | `{"warehouse": "STOCK_ANALYTICS_WH", "database": "STOCK_ANALYTICS_DB", "role": "STOCK_ANALYTICS_ROLE"}` |

Click Save.

> **Note:** The `snowflake_default` connection is now auto-provisioned by `airflow-init`. Skip this step if it already exists.

### Step 9.3 — Add the AWS connection

Go to: Admin → Connections → + (Add a new record)

| Field | Value |
|-------|-------|
| Connection Id | `aws_default` |
| Connection Type | Amazon Web Services |
| Login | `<AWS_ACCESS_KEY_ID>` |
| Password | `<AWS_SECRET_ACCESS_KEY>` |
| Extra | `{"region_name": "us-east-1"}` |

Click Save.

> **Note:** The `aws_default` connection is now auto-provisioned by `airflow-init`. Skip this step if it already exists.

### Step 9.4 — Enable the DAGs

Go to: DAGs (main page)

- Find `stock_analytics_pipeline` → Toggle ON (blue)
- Find `dbt_transforms` → Toggle ON (blue)

### Step 9.5 — Trigger the first pipeline run manually

1. Click on: `stock_analytics_pipeline`
2. Click the Play button (▶) top right → Trigger DAG
3. Click Trigger

### Step 9.6 — Monitor the run

Click on: `stock_analytics_pipeline` → Graph view (or Grid view)

Watch each task turn green as it completes:

```
health_check_snowflake ──┐
verify_s3_new_files    ──┴──→ trigger_snowpipe_refresh
                                      ↓
                                dbt_run_staging
                                      ↓
                              dbt_run_intermediate
                                      ↓
                                 dbt_run_marts
                                      ↓
                                   dbt_test
```

- Green = success
- Red = failure (click task → Logs to see the error)

### Step 9.7 — Confirm scheduled runs are active

- `stock_analytics_pipeline` runs every hour (`@hourly`)
- `dbt_transforms` runs every 15 minutes

Both will run automatically from now on. No manual trigger needed.

---

## Phase 10 — Historical Data Backfill

> Optional — enables Yahoo Finance-style period filters (1D, 5D, 1M, 6M, YTD, 1Y, 5Y, All)

### Step 10.1 — Install backfill script dependencies

```bash
cd scripts && uv sync && cd ..
```

Required packages: `yfinance`, `snowflake-connector-python`, `pandas`, `python-dotenv`

### Step 10.2 — Run the backfill script

```bash
uv run --directory scripts python backfill_historical.py
```

This fetches:
- **Daily data**: 2020-01-01 to present (5+ years)
- **Hourly data**: ~2 years back (yfinance limitation)

For all 20 tracked symbols. Data loads into `INTERMEDIATE.STOCK_OHLCV_HISTORICAL`.

### Step 10.3 — Rebuild dbt models with historical data

```bash
docker compose exec dbt dbt run --full-refresh \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

The `int_stock_ohlcv` model automatically unions historical data with real-time data, preferring real-time for any overlapping periods.

### Step 10.4 — Verify historical data in Snowflake

```sql
-- Check historical table
SELECT COUNT(*), MIN(hour_bucket), MAX(hour_bucket)
FROM STOCK_ANALYTICS_DB.INTERMEDIATE.STOCK_OHLCV_HISTORICAL;

-- Check combined data in marts
SELECT symbol, MIN(hour_bucket) as earliest, MAX(hour_bucket) as latest
FROM STOCK_ANALYTICS_DB.MARTS.FCT_STOCK_OHLCV_HOURLY
GROUP BY symbol
ORDER BY symbol;
```

You should see data going back to 2020 for daily granularity.

---

## Phase 11 — Power BI Connection

### Step 11.1 — Install the Snowflake ODBC driver

Download: https://developers.snowflake.com/odbc/

Install and follow the setup wizard.

### Step 11.2 — Open Power BI Desktop

File → New report (blank)

### Step 11.3 — Connect to Snowflake

Home → Get data → More → Search "Snowflake" → Connect

| Field | Value |
|-------|-------|
| Server | `<SNOWFLAKE_ACCOUNT>` (e.g. xy12345.snowflakecomputing.com) |
| Warehouse | `STOCK_ANALYTICS_WH` |

Click OK.

Authentication: Database

| Field | Value |
|-------|-------|
| Username | `STOCK_ANALYTICS_SVC` |
| Password | `<SNOWFLAKE_PASSWORD>` |

Click Connect.

### Step 11.4 — Load the mart tables

In the Navigator panel expand: `STOCK_ANALYTICS_DB` → `MARTS`

Check these tables:
- [ ] `DIM_COMPANIES`
- [ ] `DIM_DATE`
- [ ] `FCT_STOCK_TRADES`
- [ ] `FCT_STOCK_OHLCV_HOURLY`

Click **Load** (Import mode) or **Transform Data** (if you want to preview first).

### Step 11.5 — Set up Direct Query for near-real-time refresh (optional)

1. Go back to Get data → Snowflake
2. At the bottom of the connection dialog, select: **DirectQuery**

This makes Power BI query Snowflake live on each report refresh.

### Step 11.6 — Build your first visual (Volatility Heatmap)

In the Fields panel, drag:

| Field | Drop Zone |
|-------|-----------|
| `FCT_STOCK_OHLCV_HOURLY[symbol]` | Rows |
| `FCT_STOCK_OHLCV_HOURLY[hour_bucket]` | Columns |
| `FCT_STOCK_OHLCV_HOURLY[stddev_price]` | Values |

Change visual type to: **Matrix**

Apply a color scale to Values to create the heatmap effect.

### Step 11.7 — Save your Power BI report

File → Save As → `stock_analytics_dashboard.pbix`

---

## Phase 12 — Local Dev Setup

> Optional — for VS Code IntelliSense

### Step 12.1 — Create local virtual environments

```bash
make dev-setup
```

This creates a `.venv/` inside each service folder.

### Step 12.2 — Point VS Code to the right interpreter

| For files in... | Choose interpreter... |
|-----------------|----------------------|
| `kafka/producer/` | `kafka/producer/.venv/...` |
| `airflow/dags/` | `airflow/.venv/...` |
| `dbt/` | `dbt/.venv/...` |

`Ctrl+Shift+P` → Python: Select Interpreter

### Step 12.3 — Verify IntelliSense works

1. Open `airflow/dags/stock_pipeline_dag.py`
2. Hover over `SnowflakeHook` — you should see its docstring
3. If you see "import could not be resolved", check the interpreter selection

---

## Phase 13 — Daily Operations

### Stop everything (data volumes preserved)

```bash
docker compose stop
```

### Start again after stopping

```bash
docker compose up -d
```

### Full teardown including all volumes

> **WARNING:** Deletes all local data

```bash
docker compose down -v
```

### Tail all container logs

```bash
docker compose logs -f
```

### Tail one service's logs

```bash
docker compose logs -f finnhub-producer
docker compose logs -f s3-consumer
docker compose logs -f airflow-scheduler
```

### Run a specific dbt model

```bash
docker compose exec dbt dbt run \
    --select fct_stock_ohlcv_hourly \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

### Run dbt tests only

```bash
docker compose exec dbt dbt test \
    --project-dir /usr/app/dbt \
    --profiles-dir /usr/app/dbt
```

### Force a Snowpipe refresh

In Snowflake worksheet:

```sql
ALTER PIPE STOCK_ANALYTICS_DB.RAW.TRADES_PIPE REFRESH;
```

### Check how many records are in each layer

In Snowflake worksheet:

```sql
SELECT 'RAW'          AS layer, COUNT(*) AS records FROM STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW
UNION ALL
SELECT 'TRADES_MART',           COUNT(*) FROM STOCK_ANALYTICS_DB.MARTS.FCT_STOCK_TRADES
UNION ALL
SELECT 'OHLCV_MART',            COUNT(*) FROM STOCK_ANALYTICS_DB.MARTS.FCT_STOCK_OHLCV_HOURLY;
```

### Add a new Python dependency to a service

1. Edit the service's `pyproject.toml` and add the package
2. Regenerate the lockfile:
   ```bash
   cd kafka/producer    # or whichever service
   uv lock
   ```
3. Go back to root and rebuild:
   ```bash
   cd ..
   docker compose up -d --build finnhub-producer
   ```

### Update all lockfiles at once

```bash
make lock
```

### Check which containers are running

```bash
docker compose ps
```

### Reload environment variable changes

> `docker compose restart` does NOT reload `.env` — use this instead:

```bash
docker compose up -d --force-recreate <service-name>
```

### Rebuild and restart one service

```bash
docker compose up -d --build finnhub-producer
```

---

## Quick Reference — URLs and Ports

| Service | URL | Credentials |
|---------|-----|-------------|
| Streamlit (Real-time) | http://localhost:8501 | (no login) |
| Airflow UI | http://localhost:8081 | admin / admin |
| Kafka UI | http://localhost:8080 | (no login) |
| dbt docs | http://localhost:8082 | (run `make dbt-docs` first) |
| Kafka broker | localhost:9092 | (external) |
| Redis | internal only | (real-time price cache) |
| PostgreSQL | internal only | (Airflow metadata) |

---

## Troubleshooting

### Container keeps restarting

```bash
docker compose logs <container-name>
```

Read the last 20 lines of the log for the error message.

### Kafka producer shows "Connection refused"

The Kafka broker is not ready yet. Wait 30 seconds and check:

```bash
docker compose ps kafka
```

If it is not healthy yet, wait and re-check.

### Snowpipe shows 0 records after 5 minutes

1. Confirm S3 files exist: `aws s3 ls s3://<bucket>/raw/trades/ --recursive`
2. Confirm event notification is configured (Step 4.10)
3. Run a manual refresh: `ALTER PIPE ... REFRESH;`
4. Check copy history: see Step 7.4

### dbt run fails with "invalid identifier"

The raw table might be empty. Confirm Step 7.2 shows records > 0 first.

### Airflow task fails

Click the red task → Log tab → scroll to the bottom for the Python traceback.

### Airflow shows "connection does not exist: snowflake_default"

The connection wasn't provisioned. Either:
- Re-run `docker compose up -d airflow-init` to auto-provision, or
- Add the connection manually via the Airflow UI (Step 9.2)

### Power BI cannot connect to Snowflake

1. Ensure the Snowflake ODBC driver is installed (Step 10.1)
2. Check that the warehouse is not suspended:

```sql
ALTER WAREHOUSE STOCK_ANALYTICS_WH RESUME;
```

### Environment variable changes not taking effect

`docker compose restart` doesn't reload `.env`. Use:

```bash
docker compose up -d --force-recreate <service-name>
```

### Streamlit shows "No stock data available"

1. Check if the market is open (9:30 AM - 4:00 PM ET, Mon-Fri)
2. Check consumer logs: `docker logs s3-consumer` — look for "Redis connected"
3. Check Redis has data:
   ```bash
   docker exec -it airflow-redis redis-cli SMEMBERS stock:symbols
   docker exec -it airflow-redis redis-cli HGETALL stock:AAPL:latest
   ```
4. If Redis is empty, wait for trades to flow through the pipeline

### Streamlit shows "Unable to connect to Redis"

1. Check if Redis container is running: `docker compose ps redis`
2. Check consumer can reach Redis: `docker logs s3-consumer | grep -i redis`
3. Restart the consumer: `docker compose restart s3-consumer`
