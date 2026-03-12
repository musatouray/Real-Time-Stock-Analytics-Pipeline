/*
  fct_stock_ohlcv_hourly
  ───────────────────────
  Hourly OHLCV candles enriched with volatility metrics and company info.
  Incremental merge on (symbol, hour_bucket).
*/

{{
  config(
    materialized = 'incremental',
    unique_key    = ['symbol', 'hour_bucket'],
    incremental_strategy = 'merge',
    cluster_by   = ['hour_bucket::date', 'symbol']
  )
}}

with ohlcv as (

    select * from {{ ref('int_stock_ohlcv') }}

    {% if is_incremental() %}
    where hour_bucket > (select max(hour_bucket) from {{ this }})
    {% endif %}

),

volatility as (

    select * from {{ ref('int_stock_volatility') }}

),

companies as (

    select symbol, company_name, sector, exchange
    from {{ ref('dim_companies') }}

)

select
    o.symbol,
    c.company_name,
    c.sector,
    c.exchange,
    o.hour_bucket,
    o.hour_bucket::date as traded_date,
    o.hour_bucket::time as traded_hour,
    o.open_price,
    o.high_price,
    o.low_price,
    o.close_price,
    o.total_volume,
    o.trade_count,
    v.vwap,
    v.stddev_price,
    v.price_range,
    -- Simple price-change % within the hour
    round(
        (o.close_price - o.open_price) / nullif(o.open_price, 0) * 100,
        4
    ) as pct_change,
    to_number(to_char(o.hour_bucket::date, 'YYYYMMDD')) as date_key

from ohlcv o
left join volatility v using (symbol, hour_bucket)
left join companies  c using (symbol)
