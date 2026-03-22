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

),

-- Get the closing price for each day (last trading hour's close)
daily_close as (

    select
        symbol,
        (hour_bucket::timestamp_ntz)::date as trade_date,
        close_price as daily_close_price
    from {{ ref('int_stock_ohlcv') }}
    where hour_bucket is not null
    qualify row_number() over (
        partition by symbol, (hour_bucket::timestamp_ntz)::date
        order by hour_bucket::timestamp_ntz desc
    ) = 1

),

-- Get previous trading day's close using LAG
prev_day_close as (

    select
        symbol,
        trade_date,
        daily_close_price,
        lag(daily_close_price) over (
            partition by symbol
            order by trade_date
        ) as prev_day_close_price
    from daily_close

)

select
    o.symbol,
    c.company_name,
    c.sector,
    c.exchange,
    o.hour_bucket::timestamp_ntz as hour_bucket,
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
    -- Hourly change (open to close within the hour)
    round(
        (o.close_price - o.open_price) / nullif(o.open_price, 0) * 100,
        4
    ) as pct_change,
    -- Previous trading day's close
    p.prev_day_close_price as prev_day_close,
    -- Change from previous day's close (Yahoo Finance style)
    round(o.close_price - p.prev_day_close_price, 4) as change_from_prev_close,
    round(
        (o.close_price - p.prev_day_close_price) / nullif(p.prev_day_close_price, 0) * 100,
        4
    ) as pct_change_from_prev_close,
    to_number(to_char(o.hour_bucket::date, 'YYYYMMDD')) as date_key

from ohlcv o
left join volatility v using (symbol, hour_bucket)
left join companies  c using (symbol)
left join prev_day_close p
    on o.symbol = p.symbol
    and o.hour_bucket::date = p.trade_date
