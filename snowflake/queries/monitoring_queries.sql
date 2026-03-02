-- ─────────────────────────────────────────────────────────────
-- monitoring_queries.sql
-- Handy operational queries for monitoring the pipeline
-- ─────────────────────────────────────────────────────────────

USE DATABASE STOCK_ANALYTICS_DB;
USE WAREHOUSE STOCK_ANALYTICS_WH;

-- ── 1. Snowpipe status ─────────────────────────────────────
SELECT SYSTEM$PIPE_STATUS('STOCK_ANALYTICS_DB.RAW.TRADES_PIPE');

-- ── 2. Records ingested in the last hour ───────────────────
SELECT
    COUNT(*)                        AS records_last_hour,
    MIN(ingested_at)                AS first_ingested,
    MAX(ingested_at)                AS last_ingested
FROM STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW
WHERE ingested_at >= DATEADD(hour, -1, CURRENT_TIMESTAMP());

-- ── 3. Trade count per symbol (last 24 hours) ──────────────
SELECT
    record_content:symbol::VARCHAR  AS symbol,
    COUNT(*)                        AS trade_count,
    AVG(record_content:price::FLOAT) AS avg_price
FROM STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW
WHERE ingested_at >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
GROUP BY 1
ORDER BY 2 DESC;

-- ── 4. Latest mart data ────────────────────────────────────
SELECT
    symbol,
    hour_bucket,
    open_price,
    close_price,
    pct_change,
    vwap,
    total_volume
FROM STOCK_ANALYTICS_DB.MARTS.FCT_STOCK_OHLCV_HOURLY
WHERE hour_bucket >= DATEADD(hour, -6, CURRENT_TIMESTAMP())
ORDER BY hour_bucket DESC, symbol;

-- ── 5. dbt model freshness check ──────────────────────────
SELECT
    TABLE_NAME,
    LAST_ALTERED
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA IN ('STAGING', 'INTERMEDIATE', 'MARTS')
ORDER BY LAST_ALTERED DESC;

-- ── 6. Top movers (last completed hour) ───────────────────
SELECT
    symbol,
    company_name,
    pct_change,
    close_price,
    total_volume,
    vwap
FROM STOCK_ANALYTICS_DB.MARTS.FCT_STOCK_OHLCV_HOURLY
WHERE hour_bucket = DATE_TRUNC('hour', DATEADD(hour, -1, CURRENT_TIMESTAMP()))
ORDER BY ABS(pct_change) DESC
LIMIT 10;

-- ── 7. Pipe copy history ───────────────────────────────────
SELECT
    pipe_name,
    file_name,
    row_count,
    row_parsed,
    first_error_message,
    status
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME    => 'STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW',
    START_TIME    => DATEADD(hour, -24, CURRENT_TIMESTAMP())
))
ORDER BY last_load_time DESC
LIMIT 50;
