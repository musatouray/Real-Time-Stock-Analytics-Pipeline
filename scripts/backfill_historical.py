"""
Historical Stock Data Backfill Script
======================================
Fetches historical OHLCV data from Yahoo Finance and loads it into Snowflake.

Usage:
    cd scripts && uv sync && cd ..
    uv run --directory scripts python backfill_historical.py

Dependencies managed via scripts/pyproject.toml (uv)
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Configuration
SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "TSLA", "META", "JPM", "V", "JNJ",
    "UNH", "XOM", "WMT", "MA", "NFLX",
    "AVGO", "AMD", "CRM", "ORCL", "DIS"
]

# Date range for backfill
END_DATE = datetime.now()
START_DATE_DAILY = datetime(2020, 1, 1)  # 5+ years of daily data
START_DATE_HOURLY = END_DATE - timedelta(days=729)  # ~2 years of hourly (yfinance limit)

# Snowflake connection parameters
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", "").replace(".snowflakecomputing.com", ""),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "role": os.getenv("SNOWFLAKE_ROLE", "STOCK_ANALYTICS_ROLE"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "STOCK_ANALYTICS_WH"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "STOCK_ANALYTICS_DB"),
    "schema": "INTERMEDIATE",
}

# Target table name
TABLE_NAME = "STOCK_OHLCV_HISTORICAL"


def fetch_daily_data(symbol: str) -> pd.DataFrame:
    """Fetch daily OHLCV data for a symbol."""
    print(f"  Fetching daily data for {symbol}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=START_DATE_DAILY, end=END_DATE, interval="1d")

    if df.empty:
        print(f"  WARNING: No daily data for {symbol}")
        return pd.DataFrame()

    df = df.reset_index()
    df["symbol"] = symbol
    df["granularity"] = "daily"
    return df


def fetch_hourly_data(symbol: str) -> pd.DataFrame:
    """Fetch hourly OHLCV data for a symbol (limited to ~2 years by yfinance)."""
    print(f"  Fetching hourly data for {symbol}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=START_DATE_HOURLY, end=END_DATE, interval="1h")

    if df.empty:
        print(f"  WARNING: No hourly data for {symbol}")
        return pd.DataFrame()

    df = df.reset_index()
    df["symbol"] = symbol
    df["granularity"] = "hourly"
    return df


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance DataFrame to match Snowflake schema."""
    if df.empty:
        return df

    # Rename columns to match Snowflake schema
    column_map = {
        "Date": "hour_bucket",
        "Datetime": "hour_bucket",
        "Open": "open_price",
        "High": "high_price",
        "Low": "low_price",
        "Close": "close_price",
        "Volume": "total_volume",
        "symbol": "symbol",
        "granularity": "granularity",
    }

    # Keep only relevant columns
    df = df.rename(columns=column_map)
    cols_to_keep = ["symbol", "hour_bucket", "open_price", "high_price",
                    "low_price", "close_price", "total_volume", "granularity"]
    df = df[[c for c in cols_to_keep if c in df.columns]]

    # Convert timezone-aware timestamps to timezone-naive (America/New_York)
    if df["hour_bucket"].dt.tz is not None:
        # Timezone-aware: convert to Eastern Time, then remove timezone info
        df["hour_bucket"] = df["hour_bucket"].dt.tz_convert("America/New_York").dt.tz_localize(None)

    # Ensure proper datetime format
    df["hour_bucket"] = pd.to_datetime(df["hour_bucket"])

    # Drop any rows with invalid timestamps (NaT)
    df = df.dropna(subset=["hour_bucket"])

    # Convert to string format that Snowflake can reliably parse
    df["hour_bucket"] = df["hour_bucket"].dt.strftime("%Y-%m-%d %H:%M:%S")

    # Add trade_count as 1 (we don't have this from yfinance)
    df["trade_count"] = 1

    # Ensure correct data types
    df["open_price"] = df["open_price"].astype(float)
    df["high_price"] = df["high_price"].astype(float)
    df["low_price"] = df["low_price"].astype(float)
    df["close_price"] = df["close_price"].astype(float)
    df["total_volume"] = df["total_volume"].astype(int)

    return df


def create_table_if_not_exists(conn):
    """Create the historical OHLCV table in Snowflake if it doesn't exist."""
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {SNOWFLAKE_CONFIG['database']}.{SNOWFLAKE_CONFIG['schema']}.{TABLE_NAME} (
        SYMBOL VARCHAR(10) NOT NULL,
        HOUR_BUCKET TIMESTAMP_NTZ NOT NULL,
        OPEN_PRICE FLOAT,
        HIGH_PRICE FLOAT,
        LOW_PRICE FLOAT,
        CLOSE_PRICE FLOAT,
        TOTAL_VOLUME NUMBER,
        TRADE_COUNT NUMBER DEFAULT 1,
        GRANULARITY VARCHAR(10),
        LOADED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
        PRIMARY KEY (SYMBOL, HOUR_BUCKET, GRANULARITY)
    );
    """
    cursor = conn.cursor()
    cursor.execute(create_sql)
    print(f"Table {TABLE_NAME} ready.")


def truncate_table(conn):
    """Truncate the table before full reload."""
    cursor = conn.cursor()
    cursor.execute(f"TRUNCATE TABLE IF EXISTS {SNOWFLAKE_CONFIG['database']}.{SNOWFLAKE_CONFIG['schema']}.{TABLE_NAME}")
    print(f"Table {TABLE_NAME} truncated.")


def load_to_snowflake(df: pd.DataFrame, conn):
    """Load DataFrame to Snowflake using write_pandas."""
    if df.empty:
        print("  No data to load.")
        return

    success, num_chunks, num_rows, _ = write_pandas(
        conn=conn,
        df=df,
        table_name=TABLE_NAME,
        database=SNOWFLAKE_CONFIG["database"],
        schema=SNOWFLAKE_CONFIG["schema"],
        quote_identifiers=False,
    )

    if success:
        print(f"  Loaded {num_rows} rows in {num_chunks} chunk(s).")
    else:
        print(f"  ERROR: Failed to load data.")


def main():
    print("=" * 60)
    print("Historical Stock Data Backfill")
    print("=" * 60)
    print(f"Symbols: {', '.join(SYMBOLS)}")
    print(f"Daily data from: {START_DATE_DAILY.date()}")
    print(f"Hourly data from: {START_DATE_HOURLY.date()}")
    print(f"Target: {SNOWFLAKE_CONFIG['database']}.{SNOWFLAKE_CONFIG['schema']}.{TABLE_NAME}")
    print("=" * 60)

    # Connect to Snowflake
    print("\nConnecting to Snowflake...")
    try:
        conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
        print("Connected successfully.")
    except Exception as e:
        print(f"ERROR: Failed to connect to Snowflake: {e}")
        sys.exit(1)

    # Create table and truncate for fresh load
    create_table_if_not_exists(conn)
    truncate_table(conn)

    # Fetch and load data for each symbol
    all_data = []

    for symbol in SYMBOLS:
        print(f"\nProcessing {symbol}...")

        # Fetch daily data
        daily_df = fetch_daily_data(symbol)
        if not daily_df.empty:
            daily_df = normalize_dataframe(daily_df)
            all_data.append(daily_df)

        # Fetch hourly data
        hourly_df = fetch_hourly_data(symbol)
        if not hourly_df.empty:
            hourly_df = normalize_dataframe(hourly_df)
            all_data.append(hourly_df)

    # Combine all data
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        print(f"\nTotal records to load: {len(combined_df)}")

        # Load to Snowflake
        print("\nLoading to Snowflake...")
        load_to_snowflake(combined_df, conn)
    else:
        print("\nNo data fetched.")

    conn.close()
    print("\n" + "=" * 60)
    print("Backfill complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run dbt to rebuild models:")
    print("   docker exec dbt-runner dbt run --full-refresh --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt")
    print("2. Refresh Power BI dataset")


if __name__ == "__main__":
    main()
