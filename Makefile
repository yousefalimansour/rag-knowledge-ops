.PHONY: help up down build logs migrate seed test test-api test-web test-eval lint fmt clean

help: ## show this help
	@awk 'BEGIN{FS=":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} /^[a-zA-Z_-]+:.*?##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## bring up the full stack
	docker compose up -d --build

down: ## stop and remove containers
	docker compose down

build: ## rebuild images without starting
	docker compose build

logs: ## tail logs for api/worker/beat/web
	docker compose logs -f api worker beat web

migrate: ## apply database migrations
	docker compose exec api alembic upgrade head

seed: ## seed demo data (placeholder until step 02)
	docker compose exec api python -m app.scripts.seed

test: test-api test-web ## run all tests

test-api: ## backend unit + integration tests
	docker compose exec api pytest -q

test-web: ## frontend tests
	cd apps/web && pnpm test

test-eval: ## retrieval evaluation harness (step 07)
	docker compose exec api pytest -q eval/retrieval

lint: ## lint backend + frontend
	docker compose exec api ruff check .
	cd apps/web && pnpm lint

fmt: ## format backend + frontend
	docker compose exec api ruff format .
	cd apps/web && pnpm prettier --write .

clean: ## stop stack and remove named volumes
	docker compose down -v
