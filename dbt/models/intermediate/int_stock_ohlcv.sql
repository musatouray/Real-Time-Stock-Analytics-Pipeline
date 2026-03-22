/*
  int_stock_ohlcv
  ────────────────
  Aggregates raw trade ticks into standard OHLCV bars at hourly granularity.
  Unions real-time data with historical backfill data from yfinance.

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
realtime_ohlcv as (

    select
        symbol::varchar as symbol,
        hour_bucket::timestamp_ntz as hour_bucket,
        any_value(open_price)::float as open_price,
        max(high_price)::float as high_price,
        min(low_price)::float as low_price,
        any_value(close_price)::float as close_price,
        sum(total_volume)::number as total_volume,
        sum(trade_count)::number as trade_count,
        'realtime' as data_source

    from hourly
    group by symbol, hour_bucket

),

-- Historical backfill data from yfinance (loaded via backfill script)
-- Uses hourly granularity only; daily data excluded to maintain consistency
historical_ohlcv as (

    select
        symbol::varchar as symbol,
        hour_bucket::timestamp_ntz as hour_bucket,
        open_price::float as open_price,
        high_price::float as high_price,
        low_price::float as low_price,
        close_price::float as close_price,
        total_volume::number as total_volume,
        trade_count::number as trade_count,
        'historical' as data_source
    from {{ source('intermediate', 'stock_ohlcv_historical') }}
    where granularity = 'hourly'
      and hour_bucket is not null

),

-- Union real-time and historical, preferring real-time for overlapping periods
combined as (

    select * from realtime_ohlcv

    union all

    select * from historical_ohlcv h
    where not exists (
        select 1 from realtime_ohlcv r
        where r.symbol = h.symbol
          and r.hour_bucket = h.hour_bucket
    )

)

select
    symbol::varchar as symbol,
    hour_bucket::timestamp_ntz as hour_bucket,
    open_price::float as open_price,
    high_price::float as high_price,
    low_price::float as low_price,
    close_price::float as close_price,
    total_volume::number as total_volume,
    trade_count::number as trade_count
from combined
where hour_bucket is not null
