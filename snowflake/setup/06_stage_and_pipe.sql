-- ─────────────────────────────────────────────────────────────
-- 06_stage_and_pipe.sql
-- Run as STOCK_ANALYTICS_ROLE
--
-- Creates an external S3 stage and a Snowpipe that auto-ingests
-- NDJSON files from S3 into STOCK_TRADES_RAW.
--
-- Prerequisites:
--   - Script 05 executed and IAM trust policy updated in AWS
--   - SQS notification configured on the S3 bucket prefix
-- ─────────────────────────────────────────────────────────────

USE ROLE STOCK_ANALYTICS_ROLE;
USE DATABASE STOCK_ANALYTICS_DB;
USE SCHEMA RAW;
USE WAREHOUSE STOCK_ANALYTICS_WH;

-- ── External Stage ─────────────────────────────────────────
CREATE STAGE IF NOT EXISTS STOCK_ANALYTICS_DB.RAW.S3_TRADES_STAGE
    STORAGE_INTEGRATION = STOCK_ANALYTICS_S3_INT
    URL                 = 's3://<YOUR_BUCKET_NAME>/raw/trades/'
    FILE_FORMAT         = (
        TYPE              = 'JSON'
        STRIP_OUTER_ARRAY = FALSE    -- files are NDJSON (one JSON per line)
        COMPRESSION       = 'AUTO'
    )
    COMMENT = 'External stage pointing to the Kafka consumer S3 output';

-- ── Snowpipe ────────────────────────────────────────────────
CREATE PIPE IF NOT EXISTS STOCK_ANALYTICS_DB.RAW.TRADES_PIPE
    AUTO_INGEST = TRUE
    COMMENT     = 'Auto-ingest trade NDJSON files from S3 into STOCK_TRADES_RAW'
AS
COPY INTO STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW (
    RECORD_CONTENT,
    RECORD_METADATA
)
FROM (
    SELECT
        $1,                          -- the JSON record
        METADATA$FILENAME            -- file path from S3
    FROM @STOCK_ANALYTICS_DB.RAW.S3_TRADES_STAGE
)
FILE_FORMAT = (
    TYPE              = 'JSON'
    STRIP_OUTER_ARRAY = FALSE
);

-- ── Inspect pipe status ─────────────────────────────────────
-- SELECT SYSTEM$PIPE_STATUS('STOCK_ANALYTICS_DB.RAW.TRADES_PIPE');
--
-- ── Get the SQS ARN to configure S3 event notification ─────
-- SHOW PIPES LIKE 'TRADES_PIPE';
-- ──  Copy the notification_channel value → configure S3 → SQS notification
