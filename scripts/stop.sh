#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# stop.sh — Gracefully stop all pipeline services
# ─────────────────────────────────────────────────────────────
set -euo pipefail

echo "==> Stopping all containers (preserving volumes)..."
docker compose stop

echo "Done. Data volumes are intact. Run 'make up' to restart."
