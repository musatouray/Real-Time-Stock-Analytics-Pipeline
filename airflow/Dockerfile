FROM apache/airflow:2.10.4-python3.11

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy project definition — uv reads dependencies from pyproject.toml
COPY pyproject.toml ./

# Airflow is pre-installed in the base image; we only add providers.
# Must run as root to write to site-packages
RUN uv pip install --system --no-cache \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.4/constraints-3.11.txt" \
    .

# Switch back to airflow user for runtime (security best practice)
USER airflow
