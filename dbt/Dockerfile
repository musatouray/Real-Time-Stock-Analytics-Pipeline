FROM python:3.11-slim

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /usr/app/dbt

# Create venv via uv and add it to PATH so 'dbt' and 'python' resolve to venv
ENV VIRTUAL_ENV=/usr/app/dbt/.venv \
    PATH="/usr/app/dbt/.venv/bin:$PATH"

# Copy lockfile first — this layer is cached unless dependencies change
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy project files and install dbt packages
COPY . .
RUN uv run dbt deps --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt

# Entrypoint ensures venv is populated even if volume mounts over it
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]
