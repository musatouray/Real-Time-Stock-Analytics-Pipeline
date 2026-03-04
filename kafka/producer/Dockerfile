FROM python:3.11-slim

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_SYSTEM_PYTHON=1

WORKDIR /app

# Copy lockfile first — this layer is cached unless dependencies change
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Copy source code — separate layer so code changes don't bust the dep cache
COPY . .

CMD ["python", "finnhub_producer.py"]
