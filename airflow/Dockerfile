FROM apache/airflow:2.9.1-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

USER airflow

COPY requirements.txt /requirements.txt
# Use Airflow's constraints file to avoid dependency conflicts
RUN uv pip install --system --no-cache \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.1/constraints-3.11.txt" \
    -r /requirements.txt
