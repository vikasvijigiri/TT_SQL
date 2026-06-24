# TT_SQL_PLATFORM Makefile
# ---------------------------------------------------------------------
# Usage: make <target>
# Run `make help` for a full list.
# ---------------------------------------------------------------------

.DEFAULT_GOAL := help
.PHONY: start stop restart build test lint clean backup healthcheck help \
        gateway-build gateway-run gateway-test \
        backend-install backend-run backend-test backend-test-unit \
        backend-test-integration backend-lint \
        frontend-install frontend-run frontend-build \
        benchmark regression loadtest migrate \
        docker-up docker-down docker-build docker-logs \
        clean-runs

# -- Startup ----------------------------------------------------------
start: ## Start all services (gateway + backend + frontend)
	@bash scripts/start.sh

stop: ## Stop all services
	@bash scripts/stop.sh

restart: ## Restart all services
	@bash scripts/restart.sh

# -- Gateway (Go) ------------------------------------------------------
gateway-build: ## Build Go gateway binary
	cd services/gateway && go build -o gateway ./cmd/server/...

gateway-run: ## Run gateway binary
	cd services/gateway && ./gateway

gateway-test: ## Run gateway unit tests
	cd services/gateway && go test ./...

# -- Backend (Python) -------------------------------------------------
backend-install: ## Install Python dependencies
	pip install -r services/agent-service/requirements.txt

backend-run: ## Start backend dev server
	cd services/agent-service && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

backend-test: ## Run all backend tests
	cd services/agent-service && python -m pytest tests/ -v --tb=short

backend-test-unit: ## Run backend unit tests only
	cd services/agent-service && python -m pytest tests/unit/ -v --tb=short

backend-test-integration: ## Run backend integration tests
	cd services/agent-service && python -m pytest tests/integration/ -v --tb=short

backend-lint: ## Lint backend source
	ruff check services/agent-service/core/ services/agent-service/api/ --ignore E501,F401,F403 || true

# -- Frontend ---------------------------------------------------------
frontend-install: ## Install npm dependencies
	cd apps/web && npm install

frontend-run: ## Start frontend dev server
	cd apps/web && npm run dev

frontend-build: ## Build frontend for production
	cd apps/web && npm run build

# -- Benchmarks -------------------------------------------------------
benchmark: ## Run BIRD / Spider2 benchmarks
	@bash scripts/benchmark.sh

loadtest: ## Run load tests
	@bash scripts/loadtest.sh

migrate: ## Run database migrations
	@bash scripts/migrate.sh

regression: ## Run prompt + validator regression tests
	@bash scripts/regression.sh

# -- Data -------------------------------------------------------------
backup: ## Backup learning.db
	@bash scripts/backup.sh

clean-runs: ## Keep last 50 run artifacts
	@bash scripts/clean_runs.sh 50

# -- Docker -----------------------------------------------------------
docker-up: ## Start all containers
	docker-compose up -d

docker-down: ## Stop all containers
	docker-compose down

docker-build: ## Build all container images
	docker-compose build

docker-logs: ## Follow container logs
	docker-compose logs -f

# -- Health -----------------------------------------------------------
healthcheck: ## Check all service endpoints
	@bash scripts/healthcheck.sh

# -- Help -------------------------------------------------------------
help: ## Show this help
	@echo ""
	@echo "TT_SQL_PLATFORM -- Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick reference:"
	@echo "  make start          Start all services (gateway + backend + frontend)"
	@echo "  make stop           Stop all services"
	@echo "  make backend-test   Run all backend tests"
	@echo "  make healthcheck    Check all running services"
	@echo "  make docker-up      Start via Docker Compose"
	@echo ""
