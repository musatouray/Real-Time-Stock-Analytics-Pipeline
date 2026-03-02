-- ─────────────────────────────────────────────────────────────
-- 05_s3_integration.sql
-- Run as ACCOUNTADMIN
--
-- Creates a Storage Integration so Snowflake can access S3 without
-- embedding long-lived AWS credentials inside Snowflake.
--
-- After running:
--   1. Run DESC INTEGRATION STOCK_ANALYTICS_S3_INT;
--   2. Copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID
--   3. Update your S3 bucket IAM trust policy with those values
-- ─────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;

CREATE STORAGE INTEGRATION IF NOT EXISTS STOCK_ANALYTICS_S3_INT
    TYPE                      = EXTERNAL_STAGE
    STORAGE_PROVIDER          = 'S3'
    ENABLED                   = TRUE
    STORAGE_AWS_ROLE_ARN      = 'arn:aws:iam::<YOUR_AWS_ACCOUNT_ID>:role/SnowflakeS3Role'
    STORAGE_ALLOWED_LOCATIONS = ('s3://<YOUR_BUCKET_NAME>/raw/')
    COMMENT                   = 'Snowflake ↔ S3 integration for stock analytics';

-- Grant usage to the service role
GRANT USAGE ON INTEGRATION STOCK_ANALYTICS_S3_INT
    TO ROLE STOCK_ANALYTICS_ROLE;

-- ── Inspect (run after creation) ───────────────────────────
-- DESC INTEGRATION STOCK_ANALYTICS_S3_INT;
-- ──  Take STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID
-- ──  and add them to your IAM role trust relationship in AWS.
