/*
  assert_positive_volume
  ───────────────────────
  Custom singular test: no trade should have volume ≤ 0.
  dbt treats any rows returned as test failures.
*/

select
    trade_id,
    symbol,
    volume
from {{ ref('fct_stock_trades') }}
where volume <= 0
