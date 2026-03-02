.PHONY: help setup dev-setup lock up down restart logs ps \
        dbt-run dbt-test dbt-docs kafka-topics

# ─────────────────────────────────────────────────────────────
# Default target
# ─────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Real-Time Stock Analytics Pipeline"
	@echo "  ────────────────────────────────────"
	@echo "  make setup        Copy .env.example → .env and create log dirs"
	@echo "  make dev-setup    Create local .venv for each service (IDE support)"
	@echo "  make lock         Regenerate uv.lock files for all services"
	@echo ""
	@echo "  make up           Start all services"
	@echo "  make down         Stop and remove containers + volumes"
	@echo "  make restart      Rebuild and restart all services"
	@echo "  make logs         Tail all container logs"
	@echo "  make ps           Show running containers"
	@echo ""
	@echo "  make dbt-run      Run all dbt models (inside container)"
	@echo "  make dbt-test     Run dbt tests (inside container)"
	@echo "  make dbt-docs     Generate + serve dbt docs (port 8082)"
	@echo ""
	@echo "  make kafka-topics List Kafka topics"
	@echo ""

# ─────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────
setup:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env — fill in your credentials."; fi
	@mkdir -p airflow/logs airflow/plugins
	@echo "Setup complete."

# ─────────────────────────────────────────────────────────────
# Local dev — create per-service virtual environments
# Run once after cloning. Gives VS Code IntelliSense for each service.
# ─────────────────────────────────────────────────────────────
dev-setup:
	@echo "==> Setting up local virtual environments via uv..."
	@echo "--- kafka/producer ---"
	cd kafka/producer && uv venv && uv sync
	@echo "--- kafka/consumer ---"
	cd kafka/consumer && uv venv && uv sync
	@echo "--- dbt ---"
	cd dbt && uv venv && uv sync
	@echo "--- airflow (includes apache-airflow for IDE support) ---"
	cd airflow && uv venv && uv sync --group dev
	@echo ""
	@echo "Virtual environments created. Point VS Code to:"
	@echo "  kafka/producer/.venv"
	@echo "  kafka/consumer/.venv"
	@echo "  dbt/.venv"
	@echo "  airflow/.venv"

# ─────────────────────────────────────────────────────────────
# Lockfile management — run when you add or change a dependency
# ─────────────────────────────────────────────────────────────
lock:
	@echo "==> Regenerating uv.lock files..."
	cd kafka/producer && uv lock
	cd kafka/consumer && uv lock
	cd dbt          && uv lock
	@echo "Note: airflow uses constraint-based install — no lockfile."
	@echo "Done."

# ─────────────────────────────────────────────────────────────
# Docker lifecycle
# ─────────────────────────────────────────────────────────────
up:
	docker compose up -d --build

down:
	docker compose down -v

restart:
	docker compose down && docker compose up -d --build

logs:
	docker compose logs -f

ps:
	docker compose ps

# ─────────────────────────────────────────────────────────────
# dbt
# ─────────────────────────────────────────────────────────────
dbt-run:
	docker compose exec dbt dbt run --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt

dbt-test:
	docker compose exec dbt dbt test --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt

dbt-docs:
	docker compose exec dbt dbt docs generate --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt
	docker compose exec -d dbt dbt docs serve --port 8082 --project-dir /usr/app/dbt --profiles-dir /usr/app/dbt
	@echo "dbt docs available at http://localhost:8082"

# ─────────────────────────────────────────────────────────────
# Kafka
# ─────────────────────────────────────────────────────────────
kafka-topics:
	docker compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
