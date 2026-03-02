/*
  fct_stock_trades
  ─────────────────
  Fact table — one row per trade.
  Incremental strategy: MERGE on trade_id so re-runs are idempotent.
*/

{{
  config(
    materialized = 'incremental',
    unique_key    = 'trade_id',
    incremental_strategy = 'merge',
    cluster_by   = ['traded_at::date', 'symbol']
  )
}}

with trades as (

    select * from {{ ref('stg_stock_trades') }}

    {% if is_incremental() %}
    -- Only process records newer than the latest already loaded
    where traded_at > (select max(traded_at) from {{ this }})
    {% endif %}

),

companies as (

    select symbol, company_name, sector, exchange
    from {{ ref('dim_companies') }}

)

select
    t.trade_id,
    t.symbol,
    c.company_name,
    c.sector,
    c.exchange,
    t.price,
    t.volume,
    t.price * t.volume  as trade_value_usd,
    t.conditions,
    t.traded_at,
    date_trunc('hour', t.traded_at) as traded_hour,
    date_trunc('day',  t.traded_at) as traded_date

from trades t
left join companies c using (symbol)
