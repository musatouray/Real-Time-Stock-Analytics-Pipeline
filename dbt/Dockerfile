FROM python:3.11-slim

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_SYSTEM_PYTHON=1

WORKDIR /usr/app/dbt

# Copy lockfile first — this layer is cached unless dependencies change
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy project files and install dbt packages
COPY . .
RUN uv run dbt deps --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt

CMD ["tail", "-f", "/dev/null"]
