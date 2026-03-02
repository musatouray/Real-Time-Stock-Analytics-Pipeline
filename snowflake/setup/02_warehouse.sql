-- ─────────────────────────────────────────────────────────────
-- 02_warehouse.sql
-- Run as SYSADMIN
-- ─────────────────────────────────────────────────────────────

USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS STOCK_ANALYTICS_WH
    WAREHOUSE_SIZE        = 'X-SMALL'
    AUTO_SUSPEND          = 120          -- suspend after 2 minutes idle
    AUTO_RESUME           = TRUE
    INITIALLY_SUSPENDED   = TRUE
    COMMENT               = 'Warehouse for dbt transforms and ad-hoc queries';

GRANT USAGE ON WAREHOUSE STOCK_ANALYTICS_WH
    TO ROLE STOCK_ANALYTICS_ROLE;
