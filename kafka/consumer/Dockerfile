FROM python:3.11-slim

# Install uv — fast Rust-based package installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy lockfile first — this layer is cached unless dependencies change
COPY pyproject.toml uv.lock ./
RUN uv sync --system --no-dev --frozen

# Copy source code — separate layer so code changes don't bust the dep cache
COPY . .

CMD ["python", "s3_consumer.py"]
