#!/bin/bash
set -e

# Ensure venv exists and has dbt installed
# This handles the case where a named volume mounts over the image's .venv
if [ ! -f "$VIRTUAL_ENV/bin/dbt" ]; then
    echo "dbt not found in venv, running uv sync..."
    uv sync --no-dev --frozen
    echo "Installing dbt packages..."
    dbt deps --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt
    echo "dbt setup complete."
fi

# Execute the CMD
exec "$@"
