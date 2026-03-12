/*
  stg_stock_trades
  ────────────────
  Extracts and types fields from the raw VARIANT column ingested by Snowpipe.
  One row per trade event. Deduplication and a surrogate key are applied here
  so that downstream models can assume uniqueness.
*/

with raw as (

    select
        record_content:symbol::varchar       as symbol,
        record_content:price::float          as price,
        record_content:volume::integer       as volume,
        record_content:timestamp::bigint     as timestamp_ms,
        record_content:conditions::varchar   as conditions_raw

    from {{ source('raw', 'stock_trades_raw') }}

),

cleaned as (

    select
        symbol,
        price,
        volume,
        -- Convert Unix milliseconds to UTC timestamp, then to US/Eastern
        convert_timezone(
            'UTC',
            'America/New_York',
            dateadd(
                millisecond,
                timestamp_ms,
                '1970-01-01 00:00:00'::timestamp_ntz
            )
        )::timestamp_ntz as traded_at,
        conditions_raw as conditions,

        -- Deterministic surrogate key for deduplication
        sha2(symbol || '|' || timestamp_ms || '|' || price || '|' || volume) as trade_id

    from raw
    where
        symbol    is not null
        and price > 0
        and volume > 0

),

deduplicated as (

    select *
    from cleaned
    qualify row_number() over (partition by trade_id order by traded_at) = 1

)

select * from deduplicated
