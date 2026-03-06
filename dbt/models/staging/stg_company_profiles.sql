/*
  stg_company_profiles
  ─────────────────────
  Reads the stock_symbols seed to produce a clean company reference table.
*/

select
    symbol,
    company_name,
    sector,
    industry,
    exchange,
    logo_url
from {{ ref('stock_symbols') }}
