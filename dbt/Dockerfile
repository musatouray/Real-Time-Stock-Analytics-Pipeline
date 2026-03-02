FROM python:3.11-slim

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /usr/app/dbt

# Copy lockfile first — this layer is cached unless dependencies change
COPY pyproject.toml uv.lock ./
RUN uv sync --system --no-dev --frozen

# Copy project files and install dbt packages
COPY . .
RUN dbt deps --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt

CMD ["tail", "-f", "/dev/null"]
