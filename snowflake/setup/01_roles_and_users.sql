-- ─────────────────────────────────────────────────────────────
-- 01_roles_and_users.sql
-- Run as ACCOUNTADMIN
-- ─────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;

-- ── Roles ──────────────────────────────────────────────────
CREATE ROLE IF NOT EXISTS STOCK_ANALYTICS_ROLE
    COMMENT = 'Role for the real-time stock analytics pipeline';

CREATE ROLE IF NOT EXISTS STOCK_ANALYTICS_READ_ROLE
    COMMENT = 'Read-only access to mart tables (BI / analysts)';

-- Role hierarchy
GRANT ROLE STOCK_ANALYTICS_READ_ROLE TO ROLE STOCK_ANALYTICS_ROLE;
GRANT ROLE STOCK_ANALYTICS_ROLE      TO ROLE SYSADMIN;

-- ── Service user (used by dbt, Airflow, Snowpipe) ──────────
CREATE USER IF NOT EXISTS STOCK_ANALYTICS_SVC
    PASSWORD             = 'CHANGE_ME_ON_FIRST_LOGIN'
    DEFAULT_ROLE         = STOCK_ANALYTICS_ROLE
    DEFAULT_WAREHOUSE    = STOCK_ANALYTICS_WH
    DEFAULT_NAMESPACE    = STOCK_ANALYTICS_DB.RAW
    MUST_CHANGE_PASSWORD = TRUE
    COMMENT              = 'Service account for the stock analytics pipeline';

GRANT ROLE STOCK_ANALYTICS_ROLE TO USER STOCK_ANALYTICS_SVC;
