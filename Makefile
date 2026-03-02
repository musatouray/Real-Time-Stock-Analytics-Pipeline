.PHONY: help setup up down restart logs ps dbt-run dbt-test dbt-docs kafka-topics

# ─────────────────────────────────────────────────────────────
# Default target
# ─────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Real-Time Stock Analytics Pipeline"
	@echo "  ────────────────────────────────────"
	@echo "  make setup        Copy .env.example → .env and create log dirs"
	@echo "  make up           Start all services"
	@echo "  make down         Stop and remove containers"
	@echo "  make restart      Restart all services"
	@echo "  make logs         Tail all container logs"
	@echo "  make ps           Show running containers"
	@echo ""
	@echo "  make dbt-run      Run all dbt models"
	@echo "  make dbt-test     Run dbt tests"
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
