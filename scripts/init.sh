#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# init.sh — First-time project bootstrap
# ─────────────────────────────────────────────────────────────
set -euo pipefail

echo "==> Checking prerequisites..."
command -v docker  >/dev/null 2>&1 || { echo "ERROR: docker not found";  exit 1; }
command -v docker  >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || \
    { echo "ERROR: docker compose plugin not found"; exit 1; }

echo "==> Creating .env from .env.example..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env — fill in your credentials before continuing."
else
    echo "  .env already exists, skipping."
fi

echo "==> Creating Airflow log and plugin directories..."
mkdir -p airflow/logs airflow/plugins

echo "==> Generating a Fernet key for Airflow..."
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || \
             docker run --rm python:3.11-slim python -c \
             "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "  Add this to your .env as AIRFLOW__CORE__FERNET_KEY:"
echo "  $FERNET_KEY"

echo ""
echo "Bootstrap complete."
echo "  1. Edit .env with your real credentials"
echo "  2. Run: make up"
echo "  3. Open Airflow at http://localhost:8081"
echo "  4. Open Kafka UI at http://localhost:8080"
