-- ─────────────────────────────────────────────────────────────
-- 04_raw_tables.sql
-- Run as STOCK_ANALYTICS_ROLE
-- ─────────────────────────────────────────────────────────────

USE ROLE STOCK_ANALYTICS_ROLE;
USE DATABASE STOCK_ANALYTICS_DB;
USE SCHEMA RAW;
USE WAREHOUSE STOCK_ANALYTICS_WH;

-- ── Raw trade events (Snowpipe target) ─────────────────────
-- Snowpipe will COPY INTO this table from S3.
-- RECORD_CONTENT holds the full NDJSON trade object as VARIANT.
-- RECORD_METADATA holds the Snowpipe file metadata injected by Snowflake.

CREATE TABLE IF NOT EXISTS STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW (
    RECORD_CONTENT  VARIANT         COMMENT 'Full trade JSON from Finnhub',
    RECORD_METADATA VARIANT         COMMENT 'Snowpipe ingestion metadata',
    INGESTED_AT     TIMESTAMP_NTZ   DEFAULT CURRENT_TIMESTAMP()
)
DATA_RETENTION_TIME_IN_DAYS = 3
COMMENT = 'Raw landing table — one row per trade JSON record';

-- Allow dbt transformations to read from RAW
GRANT SELECT ON TABLE STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW
    TO ROLE STOCK_ANALYTICS_ROLE;
