/*
  int_stock_ohlcv
  ────────────────
  Aggregates raw trade ticks into standard OHLCV bars at hourly granularity.

  FIRST/LAST use Snowflake window functions ordered by traded_at to derive
  the open (first trade price) and close (last trade price) within each bucket.
*/

with trades as (

    select * from {{ ref('stg_stock_trades') }}

),

hourly as (

    select
        symbol,
        date_trunc('hour', traded_at) as hour_bucket,

        -- OHLCV
        first_value(price) over (
            partition by symbol, date_trunc('hour', traded_at)
            order by traded_at
            rows between unbounded preceding and unbounded following
        ) as open_price,

        max(price)                              as high_price,
        min(price)                              as low_price,

        last_value(price) over (
            partition by symbol, date_trunc('hour', traded_at)
            order by traded_at
            rows between unbounded preceding and unbounded following
        ) as close_price,

        sum(volume)                             as total_volume,
        count(*)                                as trade_count

    from trades
    group by
        symbol,
        hour_bucket,
        traded_at,    -- needed for window functions above
        price         -- needed for window functions above

),

-- Collapse back to one row per (symbol, hour_bucket)
collapsed as (

    select
        symbol,
        hour_bucket,
        any_value(open_price)   as open_price,
        max(high_price)         as high_price,
        min(low_price)          as low_price,
        any_value(close_price)  as close_price,
        sum(total_volume)       as total_volume,
        sum(trade_count)        as trade_count

    from hourly
    group by symbol, hour_bucket

)

select * from collapsed
