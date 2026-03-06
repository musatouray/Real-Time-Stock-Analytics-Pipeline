/*
  dim_companies
  ──────────────
  SCD Type 1 dimension seeded from the stock_symbols CSV.
  Re-running always reflects the latest seed data.
*/

select
    symbol,
    company_name,
    sector,
    industry,
    exchange,
    logo_url,
    current_timestamp() as updated_at

from {{ ref('stg_company_profiles') }}
