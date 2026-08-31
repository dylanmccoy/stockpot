.PHONY: help install test test-backend test-frontend build typecheck \
        dev-backend dev-frontend db-reset

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install backend + frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests (pytest)
	cd backend && uv run pytest

test-frontend: ## Run frontend tests (vitest, one-shot)
	cd frontend && npm run test:run

typecheck: ## Type-check the frontend
	cd frontend && npm run typecheck

build: ## Production build of the frontend (also type-checks)
	cd frontend && npm run build

dev-backend: ## Run the backend dev server (:8000, docs at /docs)
	cd backend && uv run uvicorn app.main:app --reload

dev-frontend: ## Run the frontend dev server (:5173, proxies /api -> :8000)
	cd frontend && npm run dev

db-reset: ## Delete the local SQLite DB (no migrations; recreated on next startup)
	rm -f backend/recipe.db
