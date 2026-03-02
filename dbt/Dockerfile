FROM python:3.11-slim

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /usr/app/dbt

RUN uv pip install --system --no-cache \
    dbt-core==1.8.2 \
    dbt-snowflake==1.8.2

COPY . .

RUN dbt deps --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt

CMD ["tail", "-f", "/dev/null"]
