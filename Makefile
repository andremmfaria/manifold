# Manifold root Makefile

.PHONY: help setup install dev build test lint format clean docker-up docker-down ci-check

# ──────────────────────────────────────────────────────────
# Help
# ──────────────────────────────────────────────────────────
help:
	@echo "Manifold development targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN {FS = ":.*?## "}; {printf "  %-25s %s\n", $$1, $$2}'

# ──────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────
setup: install-backend install-frontend ## Install all dependencies
	@cp -n .env.example .env || true
	@cp -n backend/.env.example backend/.env || true
	@echo "✓ Setup complete. Edit .env and backend/.env before starting."

install-backend: ## Install backend dependencies (uv)
	cd backend && uv sync

install-frontend: ## Install frontend dependencies (npm)
	cd frontend && npm ci

# ──────────────────────────────────────────────────────────
# Development servers
# ──────────────────────────────────────────────────────────
dev-backend: ## Start backend dev server (hot reload)
	cd backend && uv run uvicorn manifold.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

dev: ## Start all services (requires tmux or parallel; shows combined log)
	@echo "Run in separate terminals: make dev-backend / make dev-frontend"
	@echo "Or: docker compose -f docker-compose.yml -f docker-compose.dev.yml up"

# ──────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────
db-migrate: ## Run Alembic migrations
	cd backend && uv run alembic upgrade head

db-revision: ## Create a new Alembic migration revision
	cd backend && uv run alembic revision --autogenerate -m "$(MSG)"

db-downgrade: ## Rollback one migration
	cd backend && uv run alembic downgrade -1

# ──────────────────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────────────────
test-backend: ## Run backend tests
	cd backend && uv run pytest tests/ -v

test-frontend: ## Run frontend tests
	cd frontend && npm run test

test: test-backend test-frontend ## Run all tests

test-cov: ## Backend tests with coverage report
	cd backend && uv run pytest tests/ --cov=manifold --cov-report=html

ci-check: lint typecheck-backend typecheck-frontend test ## Full CI gate: lint + type-check + tests (mirrors GitHub Actions pipelines)

# ──────────────────────────────────────────────────────────
# Linting
# ──────────────────────────────────────────────────────────
lint-backend: ## Lint backend (ruff)
	cd backend && uv run ruff check src/manifold/ tests/

lint-frontend: ## Lint frontend (eslint)
	cd frontend && npm run lint

lint: lint-backend lint-frontend ## Lint everything

# ──────────────────────────────────────────────────────────
# Formatting
# ──────────────────────────────────────────────────────────
format-backend: ## Format backend (ruff format)
	cd backend && uv run ruff format src/manifold/ tests/

format-frontend: ## Format frontend (prettier)
	cd frontend && npm run format

format: format-backend format-frontend ## Format everything

# ──────────────────────────────────────────────────────────
# Type checking
# ──────────────────────────────────────────────────────────
typecheck-backend: ## Type check backend (mypy)
	cd backend && uv run mypy src/manifold/

typecheck-frontend: ## Type check frontend (tsc)
	cd frontend && npm run typecheck

# ──────────────────────────────────────────────────────────
# Build
# ──────────────────────────────────────────────────────────
build-frontend: ## Build frontend for production
	cd frontend && npm run build

build-backend: ## Build backend wheel/sdist
	cd backend && uv build

build: build-frontend build-backend ## Build everything

# ──────────────────────────────────────────────────────────
# Docker
# ──────────────────────────────────────────────────────────
docker-build: ## Build Docker images
	docker compose build

docker-up: ## Start Docker Compose stack
	docker compose up -d

docker-up-dev: ## Start Docker Compose dev stack
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

docker-down: ## Stop Docker Compose stack
	docker compose down

docker-logs: ## Follow Docker Compose logs
	docker compose logs -f

# ──────────────────────────────────────────────────────────
# Release helpers
# ──────────────────────────────────────────────────────────
release-dry-run: ## Preview release changes (requires git tags)
	@echo "Current version: $$(git describe --tags --abbrev=0 2>/dev/null || echo 'no tags')"
	@echo "Commits since last tag:"
	@git log $$(git describe --tags --abbrev=0 2>/dev/null)..HEAD --oneline 2>/dev/null || git log --oneline -10

# ──────────────────────────────────────────────────────────
# Cleanup
# ──────────────────────────────────────────────────────────
clean: ## Remove build artifacts
	rm -rf backend/dist/ backend/.venv/ backend/htmlcov/
	rm -rf frontend/dist/ frontend/node_modules/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
