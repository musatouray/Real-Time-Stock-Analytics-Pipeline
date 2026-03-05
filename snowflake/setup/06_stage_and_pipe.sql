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


-- ── JSON File Format ─────────────────────────────────────────
CREATE OR REPLACE FILE FORMAT STOCK_ANALYTICS_DB.RAW.JSON_FILE_FORMAT
    TYPE               = 'JSON'
    STRIP_OUTER_ARRAY  = FALSE -- matches single-object Kafka messages
    COMPRESSION        = 'AUTO'
    IGNORE_UTF8_ERRORS = TRUE;
   


-- ── External Stage ─────────────────────────────────────────
CREATE OR REPLACE STAGE STOCK_ANALYTICS_DB.RAW.S3_TRADES_STAGE 
    STORAGE_INTEGRATION      = stock_analytics_s3_integration
    URL                      = 's3://stock-files-raw/raw/trades/'
    FILE_FORMAT              = STOCK_ANALYTICS_DB.RAW.JSON_FILE_FORMAT
    COMMENT = 'External stage pointing to the Kafka consumer S3 bucket';


-- ── Snowpipe ────────────────────────────────────────────────
CREATE OR REPLACE PIPE STOCK_ANALYTICS_DB.RAW.TRADES_PIPE 
AUTO_INGEST = TRUE
COMMENT = 'Auto-ingest trade JSON files from S3 into STOCK_TRADES_RAW'
AS 
COPY INTO STOCK_ANALYTICS_DB.RAW.STOCK_TRADES_RAW (RECORD_CONTENT)
FROM @STOCK_ANALYTICS_DB.RAW.S3_TRADES_STAGE
FILE_FORMAT = STOCK_ANALYTICS_DB.RAW.JSON_FILE_FORMAT;


-- ── Inspect pipe status ─────────────────────────────────────
SELECT SYSTEM$PIPE_STATUS('STOCK_ANALYTICS_DB.RAW.TRADES_PIPE');

-- ── Get the SQS ARN to configure S3 event notification ─────
SHOW PIPES LIKE 'TRADES_PIPE';
-- ──  Copy the notification_channel value → configure S3 → SQS notification
