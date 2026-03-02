/*
  int_stock_volatility
  ─────────────────────
  Computes intra-hour price volatility metrics per symbol:
    - stddev_price  : standard deviation of trade prices within the hour
    - price_range   : high - low
    - vwap          : volume-weighted average price
*/

with trades as (

    select * from {{ ref('stg_stock_trades') }}

)

select
    symbol,
    date_trunc('hour', traded_at) as hour_bucket,

    round(stddev(price), 4)                                 as stddev_price,
    max(price) - min(price)                                 as price_range,

    -- VWAP = sum(price * volume) / sum(volume)
    round(
        sum(price * volume) / nullif(sum(volume), 0),
        4
    )                                                        as vwap,

    count(*)                                                 as trade_count

from trades
group by
    symbol,
    date_trunc('hour', traded_at)
