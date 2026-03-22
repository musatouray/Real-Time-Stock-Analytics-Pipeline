"""
Real-Time Stock Monitor
───────────────────────
Streamlit dashboard that displays live stock prices from Redis cache.
The cache is populated by the Kafka s3-consumer service.
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import redis
import streamlit as st

from config import REDIS_HOST, REDIS_PORT, REFRESH_INTERVAL, STOCK_SECTORS

US_EASTERN = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────────────────────
# Page configuration
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Real-Time Stock Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stMetric {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
    }
    .price-up { color: #00c853 !important; }
    .price-down { color: #ff1744 !important; }
    .price-neutral { color: #9e9e9e !important; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
    div[data-testid="stMetricDelta"] { font-size: 1rem; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Redis connection
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def get_redis_client():
    """Create a cached Redis connection."""
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        client.ping()
        return client
    except redis.ConnectionError:
        return None


def get_stock_data(client: redis.Redis) -> list[dict]:
    """Fetch all stock data from Redis cache."""
    if client is None:
        return []

    try:
        # Get all active symbols
        symbols = client.smembers("stock:symbols")
        if not symbols:
            return []

        # Fetch data for each symbol
        stocks = []
        for symbol in sorted(symbols):
            data = client.hgetall(f"stock:{symbol}:latest")
            if data:
                stocks.append(data)

        return stocks
    except redis.RedisError:
        return []


def calculate_change(current: float, prev_close: float) -> tuple[float, float]:
    """Calculate price change and percentage."""
    if prev_close and prev_close > 0:
        change = current - prev_close
        pct_change = (change / prev_close) * 100
        return change, pct_change
    return 0.0, 0.0


def format_timestamp(ts: str) -> str:
    """Format Unix timestamp to readable time."""
    try:
        dt = datetime.fromtimestamp(int(ts), tz=US_EASTERN)
        return dt.strftime("%I:%M:%S %p ET")
    except (ValueError, TypeError):
        return "N/A"


# ─────────────────────────────────────────────────────────────
# Main app
# ─────────────────────────────────────────────────────────────
def main():
    st.title("📈 Real-Time Stock Monitor")

    # Connect to Redis
    redis_client = get_redis_client()

    if redis_client is None:
        st.error("Unable to connect to Redis. Make sure the pipeline is running.")
        st.info("Start the pipeline with: `docker compose up -d`")
        return

    # Sidebar controls
    with st.sidebar:
        st.header("Settings")
        auto_refresh = st.checkbox("Auto-refresh", value=True)
        refresh_rate = st.slider("Refresh rate (seconds)", 1, 10, REFRESH_INTERVAL)
        sector_filter = st.multiselect(
            "Filter by sector",
            options=sorted(set(STOCK_SECTORS.values())),
            default=[],
        )

    # Status bar
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        current_time = datetime.now(US_EASTERN).strftime("%I:%M:%S %p ET")
        st.caption(f"🕐 {current_time}")
    with col2:
        st.caption("🟢 Connected to Redis" if redis_client else "🔴 Disconnected")
    with col3:
        if st.button("🔄 Refresh"):
            st.rerun()

    st.divider()

    # Fetch stock data
    stocks = get_stock_data(redis_client)

    if not stocks:
        st.warning("No stock data available. Waiting for market data...")
        st.info("""
        **Possible reasons:**
        - Market is closed (US markets: 9:30 AM - 4:00 PM ET, Mon-Fri)
        - Pipeline is starting up
        - Finnhub producer is not running
        """)

        # Show connection status
        with st.expander("Debug Info"):
            st.code(f"Redis Host: {REDIS_HOST}:{REDIS_PORT}")
            try:
                symbols = redis_client.smembers("stock:symbols")
                st.code(f"Active symbols in cache: {symbols or 'None'}")
            except Exception as e:
                st.code(f"Error: {e}")
    else:
        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(stocks)

        # Add sector info
        df["sector"] = df["symbol"].map(STOCK_SECTORS).fillna("Unknown")

        # Apply sector filter
        if sector_filter:
            df = df[df["sector"].isin(sector_filter)]

        # Sort by symbol
        df = df.sort_values("symbol").reset_index(drop=True)

        # Display metrics in grid
        st.subheader(f"📊 Live Prices ({len(df)} stocks)")

        # Create columns for stock cards (4 per row)
        cols_per_row = 4
        for i in range(0, len(df), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(df):
                    row = df.iloc[i + j]
                    symbol = row["symbol"]
                    price = float(row.get("price", 0))
                    volume = int(float(row.get("volume", 0)))
                    prev_close = float(row.get("prev_close", 0)) if row.get("prev_close") else 0
                    timestamp = row.get("timestamp", "")

                    change, pct_change = calculate_change(price, prev_close)

                    with col:
                        # Determine delta color
                        if pct_change > 0:
                            delta_color = "normal"  # Green
                        elif pct_change < 0:
                            delta_color = "inverse"  # Red
                        else:
                            delta_color = "off"  # Gray

                        # Show metric
                        delta_str = f"{change:+.2f} ({pct_change:+.2f}%)" if prev_close else None
                        st.metric(
                            label=f"{symbol}",
                            value=f"${price:,.2f}",
                            delta=delta_str,
                            delta_color=delta_color,
                        )

                        # Show additional info
                        st.caption(f"Vol: {volume:,} | {format_timestamp(timestamp)}")
                        st.caption(f"_{row['sector']}_")

        st.divider()

        # Summary stats
        st.subheader("📈 Market Summary")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            gainers = len(df[df.apply(lambda x: calculate_change(
                float(x.get("price", 0)),
                float(x.get("prev_close", 0)) if x.get("prev_close") else 0
            )[0] > 0, axis=1)])
            st.metric("Gainers", gainers, delta=None)

        with col2:
            losers = len(df[df.apply(lambda x: calculate_change(
                float(x.get("price", 0)),
                float(x.get("prev_close", 0)) if x.get("prev_close") else 0
            )[0] < 0, axis=1)])
            st.metric("Losers", losers, delta=None)

        with col3:
            total_volume = df["volume"].astype(float).sum()
            st.metric("Total Volume", f"{total_volume:,.0f}")

        with col4:
            last_update = df["updated_at"].astype(int).max() if "updated_at" in df.columns else 0
            if last_update:
                age = int(time.time()) - last_update
                st.metric("Data Age", f"{age}s ago")
            else:
                st.metric("Data Age", "N/A")

    # Auto-refresh logic
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()


if __name__ == "__main__":
    main()
