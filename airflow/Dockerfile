FROM apache/airflow:3.1.7-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

USER airflow

# Copy project definition — uv reads dependencies from pyproject.toml
COPY pyproject.toml ./

# Airflow is pre-installed in the base image; we only add providers.
# uv.lock is intentionally NOT used here: the base image's pre-installed
# Airflow pins its own transitive deps, so we defer to Airflow's official
# constraints file to guarantee compatibility.
RUN uv pip install --system --no-cache \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.1.7/constraints-3.11.txt" \
    .
