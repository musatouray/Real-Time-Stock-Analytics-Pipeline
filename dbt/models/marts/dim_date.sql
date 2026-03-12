with date_spine as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2026-01-01' as date)",
        end_date="dateadd(year, 1, current_date())"
        )
    }}
),

-- Extract relevant date attributes from the date spine
date_attributes as (
    select
        cast(date_day as date) as date,
        extract(year from date_day) as year,
        extract(month from date_day) as month,
        extract(day from date_day) as day_of_month,
        extract(week from date_day) as week_of_year,
        extract(quarter from date_day) as quarter,
        extract(dayofweek from date_day) as day_of_week,
        dayname(date_day) as day_name,
        monthname(date_day) as month_name,
        case
            when extract(dayofweek from date_day) in (0, 6) then false
            else true
        end as is_weekday,
        case
            when extract(dayofweek from date_day) in (0, 6) then false
            else true
        end as is_trading_day
    from date_spine
)

select
    to_number(to_char(date, 'YYYYMMDD')) as date_key, 
    date,
    year,
    quarter,
    month,
    month_name,
    week_of_year,
    day_of_month,
    day_of_week,
    day_name,
    is_weekday,
    is_trading_day
from date_attributes