.PHONY: help up down build logs migrate seed \
        test test-api test-web eval e2e coverage \
        lint lint-api lint-web typecheck fmt clean

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

seed: ## seed demo data
	docker compose exec api python -m app.scripts.seed

test: test-api test-web ## run all tests (backend + frontend unit, no e2e/eval)

test-api: ## backend unit + integration + worker tests
	docker compose exec api pytest -q

test-web: ## frontend unit tests (vitest)
	cd apps/web && pnpm test

eval: ## retrieval-quality eval harness — needs GOOGLE_API_KEY
	docker compose exec -e GOOGLE_API_KEY=$$GOOGLE_API_KEY api bash -c 'cd /srv/eval/retrieval && pytest -v'

coverage: ## pytest with coverage report on the targeted modules
	docker compose exec api pytest --cov --cov-report=term-missing \
	  --cov-fail-under=70 \
	  --cov-config=pyproject.toml

e2e: ## frontend e2e (playwright) — needs the stack up
	cd apps/web && pnpm test:e2e

lint: lint-api lint-web ## lint backend + frontend

lint-api: ## ruff lint + format check
	docker compose exec api ruff check .
	docker compose exec api ruff format --check .

lint-web: ## eslint + prettier check + tsc --noEmit
	cd apps/web && pnpm lint
	cd apps/web && pnpm prettier --check .
	cd apps/web && pnpm typecheck

typecheck: ## strict mypy on the new + sensitive modules
	docker compose exec api mypy --ignore-missing-imports app/core app/retrieval app/insights

fmt: ## format backend + frontend
	docker compose exec api ruff format .
	cd apps/web && pnpm prettier --write .

clean: ## stop stack and remove named volumes
	docker compose down -v
