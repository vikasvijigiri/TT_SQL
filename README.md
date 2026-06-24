# TT_SQL -- Complete Operations Manual

> **nquire.ai**  Agentic Text-to-SQL Platform  Enterprise-Grade  Multi-Dialect

This document is the **single source of truth** for everyone who touches this project -- from a first-time developer setting up on a laptop to an SRE deploying a production cluster. Read the section that applies to you. No prior experience with the codebase is assumed.

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [System Architecture](#2-system-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Prerequisites](#4-prerequisites)
5. [First-Time Setup](#5-first-time-setup)
6. [Environment Configuration](#6-environment-configuration)
7. [Running in Development Mode](#7-running-in-development-mode)
8. [Running in Test Mode](#8-running-in-test-mode)
9. [Running in Production Mode](#9-running-in-production-mode)
10. [API Reference](#10-api-reference)
11. [Benchmark & Evaluation](#11-benchmark--evaluation)
12. [Learning System](#12-learning-system)
13. [Observability & Monitoring](#13-observability--monitoring)
14. [Makefile Quick Reference](#14-makefile-quick-reference)
15. [Troubleshooting](#15-troubleshooting)
16. [Contributing](#16-contributing)

---

## 1. What Is This?

**TT_SQL** (nquire) is an **Agentic Text-to-SQL Platform**. It converts natural language questions into SQL queries that execute against your databases and return accurate business answers.

### What it does, end-to-end

```
User asks: "Which region had the highest sales in Q3?"
              |
              
    +-----------------+
    |   Go Gateway    |  Auth + rate-limiting + routing
    +-----------------+
             |
             
    +-----------------------------------------------------+
    |              Python AI Agent Pipeline               |
    |                                                     |
    |  1. QuestionAnalyzer  -> understand intent           |
    |  2. SchemaLinker      -> find relevant tables/cols   |
    |  3. SemanticPlanner   -> build reasoning plan        |
    |  4. SQLGenerator      -> generate candidate SQL      |
    |  5. SQLCritic         -> review and critique SQL     |
    |  6. SQLCorrector      -> fix errors if any           |
    |  7. ResultValidator   -> verify the output           |
    |  8. FinalAnswer       -> format the response         |
    |  9. MetaLearner       -> save successful pattern     |
    +-----------------------------------------------------+
             |
             
    SELECT region, SUM(sales)
    FROM orders WHERE quarter = 3
    GROUP BY region ORDER BY 2 DESC
    LIMIT 1
              |
              
    {"region": "North", "sales": 4200000}
```

### Supported databases
| Dialect | Status |
|:--------|:-------|
| Snowflake | [OK] Production |
| DuckDB | [OK] Production |
| SQLite | [OK] Production |
| PostgreSQL | [OK] Production |
| BigQuery | [OK] Production |
| MySQL | [!] Beta |
| MongoDB | [!] Beta |

### Supported benchmarks
- **Spider2-Lite** -- cross-database enterprise SQL (Snowflake/BigQuery/SQLite)
- **DataAgentBench (DAB)** -- multi-turn agent evaluation
- **BIRD** -- business-oriented NL-to-SQL

---

## 2. System Architecture

### High-Level View

```
                        Internet / Users
                               |
                        +------------+
                        |    Nginx    |  :80 / :443
                        | Reverse Proxy|
                        +-------------+
                               |
              +----------------+----------------+
              |                |                |
       +------------+  +------------+        |
       |   Frontend  |  |  Go Gateway |        |
       | React/Vite  |  |  :8002      |        |
       |   :3000     |  |             |        |
       +-------------+  +-------------+        |
                               |               |
                        +------------+        |
                        | Python AI   |        |
                        | Agent-Svc   |        |
                        |   :8001     |        |
                        +-------------+        |
                               |               |
              +----------------+-------+       |
              |                |       |       |
       +--------+      +--------+   |       |
       |Postgres |      |  Redis  |   |       |
       |  :5432  |      |  :6379  |   |       |
       +---------+      +---------+   |       |
                                      |       |
                               +--------+    |
                               |Prometheus|   |
                               | /Grafana |   |
                               +---------+   |
```

### Service Responsibilities

| Service | Language | Port | Responsibility |
|:--------|:---------|:-----|:---------------|
| **Nginx** | -- | 80/443 | Reverse proxy, SSL termination, static files |
| **Frontend** | React + Vite | 3000 | Dashboard UI, query submission, result display |
| **Go Gateway** | Go 1.22 + Gin | 8002 | Auth (JWT + Google OAuth), rate-limiting, fast file-based endpoints, proxies AI calls to Python |
| **Python Agent** | Python 3.12 + FastAPI | 8001 | AI pipeline, all LLM calls, orchestration, learning |
| **PostgreSQL** | -- | 5432 | Users, runs, learning patterns, audit logs |
| **Redis** | -- | 6379 | Session cache, rate-limit counters, run state, task queues |

### Why Two Backends?

The Go gateway handles **everything that doesn't need AI**:
- Serving results from disk (CSV/MD files)
- JWT auth validation
- Prometheus metrics
- Schema drift detection
- Fast regex-based log diagnostics

This keeps Python free to focus 100% on LLM orchestration without being blocked by file I/O or auth overhead.

### AI Agent Pipeline (inside Python)

```
QuestionAnalyzer -- SchemaLinker -- SemanticPlanner
                                              |
                                       SQLGenerator
                                              |
                                    +--------  --------+
                                    |  SQLCritic loop   | (max 3 rounds)
                                    |  SQLCorrector     |
                                    +--------  --------+
                                       ResultValidator
                                              |
                                       FinalAnswer -- MetaLearner
```

Each agent is independent, has its own prompt YAML, and writes to a shared **Blackboard** (in-memory context object passed through the pipeline).

---

## 3. Repository Structure

```
TT_SQL_V2/
|
+--- services/                     <- All running services
|   +--- agent-service/            <- Python AI backend
|   |   +--- agent/
|   |   |   +--- app/              <- Core AI application (live, running)
|   |   |   |   +--- agents/       <- All AI agents (SQLGenerator, SchemaLinker, etc.)
|   |   |   |   +--- core/         <- Orchestrator, learning, retrieval, validators
|   |   |   |   +--- routes/       <- FastAPI route handlers
|   |   |   |   +--- db/           <- SQLAlchemy models + database session
|   |   |   |   +--- services/     <- SemanticContextEngine, db_executor
|   |   |   |   +-- api.py        <- FastAPI application (2700+ lines)
|   |   |   +--- agents/           <- New canonical agent modules
|   |   |   +-- orchestration/    <- New canonical orchestrator
|   |   +--- api/                  <- New canonical API layer
|   |   |   +--- api.py
|   |   |   +--- routes/
|   |   |   +--- mcp/              <- Model Context Protocol server
|   |   |   +-- custom/           <- Custom project API
|   |   +--- core/                 <- New canonical core modules
|   |   |   +--- agents/           <- Agent implementations
|   |   |   +--- orchestration/    <- Orchestrator
|   |   |   +--- retrieval/        <- SemanticEngine, HierarchicalRetriever
|   |   |   +--- sql/              <- DatabaseExecutor
|   |   |   +--- telemetry/        <- ForensicReporter, PromptRegistry
|   |   |   +-- utils/            <- LLMClient, logger, cache
|   |   +--- workers/              <- Background workers
|   |   |   +-- dab/              <- DataAgentBench runner/evaluator
|   |   +--- config/               <- system_params.yaml, config.py
|   |   +--- tests/                <- Unit + integration tests
|   |   +--- main.py               <- Uvicorn entry point
|   |   +-- requirements.txt
|   |
|   +-- gateway/                  <- Go API gateway
|       +--- cmd/server/main.go    <- Gateway entry point
|       +--- internal/
|       |   +--- handlers/         <- HTTP handlers (health, results, diagnose, proxy)
|       |   +--- router/           <- Gin router setup
|       |   +--- middleware/       <- Auth, logging, recovery
|       |   +--- config/           <- Config loading
|       |   +--- db/               <- SQLite client
|       |   +--- logparser/        <- Regex log parsing
|       |   +-- csvutil/          <- Gold evaluation
|       +--- go.mod
|       +-- go.sum
|
+--- apps/
|   +-- web/                      <- React + Vite frontend
|       +--- src/
|       |   +--- components/       <- UI components
|       |   +--- pages/            <- Route pages
|       |   +-- api/              <- API client
|       +--- Dockerfile
|       +-- package.json
|
+--- data/                         <- Runtime data (mounted in Docker)
|   +--- knowledge/                <- dynamic_lessons.json, query_analytics.jsonl
|   +--- runs/                     <- Per-run result artifacts
|   +--- benchmarks/               <- Benchmark result CSVs
|   +--- evaluations/              <- DAB evaluation results (SQLite)
|   +-- migrations/               <- PostgreSQL schema migrations (applied at boot)
|
+--- infrastructure/               <- Infra configs
|   +--- nginx/                    <- nginx.conf + Dockerfile
|   +--- docker/                   <- Per-service Dockerfiles
|   +--- postgres/                 <- DB init scripts
|   +-- redis/                    <- Redis config
|
+--- monitoring/                   <- Observability stack
|   +--- prometheus/prometheus.yml <- Scrape config
|   +--- grafana/                  <- Dashboards
|   +-- alerts/                   <- Alerting rules
|
+--- scripts/                      <- Operational scripts
|   +--- start.sh                  <- Start all services
|   +--- stop.sh                   <- Stop all services
|   +--- restart.sh                <- Restart all services
|   +--- healthcheck.sh            <- Health endpoint checks
|   +--- benchmark.sh              <- Run BIRD/Spider2 benchmarks
|   +--- regression.sh             <- Prompt + validator regression
|   +-- backup.sh                 <- Backup learning DB
|
+--- tests/                        <- Root-level E2E + smoke tests
+--- docs/                         <- Architecture documentation
+--- .github/workflows/            <- CI/CD (GitHub Actions)
|
+--- .env                          <- Local secrets (never commit)
+--- .env.example                  <- Template -- copy to .env
+--- docker-compose.yml            <- Standard deployment
+--- docker-compose.dev.yml        <- Dev overrides (hot-reload)
+--- docker-compose.prod.yml       <- Production hardening
+--- docker-compose.db.yml         <- DB-only stack (Postgres + Redis)
+--- Makefile                      <- All commands in one place
+-- README.md                     <- This file
```

---

## 4. Prerequisites

### Required tools

| Tool | Minimum Version | Install |
|:-----|:----------------|:--------|
| Python | 3.11+ | [python.org](https://python.org) |
| Go | 1.22+ | [go.dev](https://go.dev) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org) |
| Docker | 24+ | [docker.com](https://docker.com) |
| Docker Compose | 2.20+ | Bundled with Docker Desktop |
| Git | Any | [git-scm.com](https://git-scm.com) |

### For development only (optional but recommended)

| Tool | Purpose |
|:-----|:--------|
| `make` | Run all commands via Makefile (on Windows: install via Chocolatey `choco install make`) |
| `ruff` | Python linter: `pip install ruff` |
| `pytest` | Python tests: `pip install pytest` |

### LLM credentials (at least one required)

You need credentials for at least one LLM provider:

| Provider | What you need |
|:---------|:-------------|
| **AWS Bedrock** (default) | `BEDROCK_ACCESS_KEY_ID`, `BEDROCK_SECRET_ACCESS_KEY`, region |
| **OpenAI** | `OPENAI_API_KEY` |
| **Anthropic** | `ANTHROPIC_API_KEY` |
| **OpenRouter** | `OPENROUTER_API_KEY` |

> [!] **Without LLM credentials the AI pipeline won't work.** You can still run the Go gateway, frontend, and benchmark viewer without credentials.

---

## 5. First-Time Setup

### Step 1 -- Clone the repo

```bash
git clone https://github.com/nquire/ttsql.git TT_SQL_V2
cd TT_SQL_V2
```

### Step 2 -- Create your `.env` file

```bash
cp .env.example .env
```

Now open `.env` in any editor and fill in the required fields:

```bash
# Minimum required for AI to work:
BEDROCK_ACCESS_KEY_ID=AKIA...
BEDROCK_SECRET_ACCESS_KEY=...
BEDROCK_REGION=us-east-1

# OR if using OpenAI:
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Set a strong random string:
JWT_SECRET=change-me-to-a-random-64-char-string
DATABASE_PASSWORD=your-postgres-password
```

>  Never commit `.env` to Git. It is already in `.gitignore`.

### Step 3 -- Install dependencies

**Python backend:**
```bash
cd services/agent-service
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
cd ../..
```

**Go gateway:**
```bash
cd services/gateway
go mod download
cd ../..
```

**Frontend:**
```bash
cd apps/web
npm install
cd ../..
```

### Step 4 -- Copy frontend env

The frontend needs its own `.env` file (Vite only reads its own directory):

```bash
cp .env.example apps/web/.env
# Edit apps/web/.env and set VITE_GOOGLE_CLIENT_ID if using Google OAuth
```

---

## 6. Environment Configuration

All configuration lives in `.env` at the root. Here is every variable explained:

### Application

| Variable | Default | Description |
|:---------|:--------|:------------|
| `APP_NAME` | `nquire` | Application name |
| `ENVIRONMENT` | `development` | `development` / `production` |

### Ports

| Variable | Default | Description |
|:---------|:--------|:------------|
| `FRONTEND_PORT` | `3000` | React dev server port |
| `GO_PORT` | `8002` | Go gateway port |
| `PYTHON_PORT` | `8001` | Python agent port |

### PostgreSQL

| Variable | Default | Description |
|:---------|:--------|:------------|
| `DATABASE_HOST` | `postgres` (Docker) / `localhost` (local) | Postgres host |
| `DATABASE_PORT` | `5432` | Postgres port |
| `DATABASE_NAME` | `ttsql` | Database name |
| `DATABASE_USER` | `ttsql` | Database user |
| `DATABASE_PASSWORD` | -- | **Required** -- set a strong password |

### Redis

| Variable | Default | Description |
|:---------|:--------|:------------|
| `REDIS_HOST` | `redis` (Docker) / `localhost` (local) | Redis host |
| `REDIS_PORT` | `6379` | Redis port |

### LLM Provider

| Variable | Default | Description |
|:---------|:--------|:------------|
| `LLM_PROVIDER` | `bedrock` | `bedrock` / `openai` / `anthropic` / `openrouter` |
| `LLM_MODEL` | -- | Model ID (e.g. `anthropic.claude-3-5-sonnet-20241022-v2:0`) |
| `BEDROCK_ACCESS_KEY_ID` | -- | AWS access key |
| `BEDROCK_SECRET_ACCESS_KEY` | -- | AWS secret key |
| `BEDROCK_REGION` | `us-east-1` | AWS Bedrock region |
| `OPENAI_API_KEY` | -- | OpenAI key |
| `ANTHROPIC_API_KEY` | -- | Anthropic key |
| `OPENROUTER_API_KEY` | -- | OpenRouter key |

### Auth

| Variable | Default | Description |
|:---------|:--------|:------------|
| `JWT_SECRET` | -- | **Required** -- min 32 characters, random |
| `GOOGLE_CLIENT_ID` | -- | Google OAuth client ID |
| `ENABLE_AUTH` | `false` | Set `true` in production to require API keys |
| `API_KEY_SECRET` | -- | API key for protected endpoints (when `ENABLE_AUTH=true`) |

### LangSmith (optional, for tracing)

| Variable | Default | Description |
|:---------|:--------|:------------|
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | -- | Your LangSmith API key |
| `LANGCHAIN_PROJECT` | -- | LangSmith project name |

---

## 7. Running in Development Mode

Development mode gives you hot-reload on all three services so changes take effect immediately without restarting.

### Option A -- All services via Docker Compose (easiest)

This requires only Docker. All services start in one command.

```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

What starts:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- Python agent on `localhost:8001` (with `--reload`)
- Go gateway on `localhost:8002`
- React frontend on `localhost:3000`
- Nginx on `localhost:80` (routes everything)

Visit `http://localhost` in your browser.

To stop:
```bash
docker-compose down
```

---

### Option B -- Services running natively (faster iteration)

This is faster because native processes have no Docker overhead.

**Terminal 1 -- Start PostgreSQL + Redis only:**
```bash
docker-compose -f docker-compose.db.yml up -d
```
This starts only Postgres and Redis as containers. Everything else runs natively.

**Terminal 2 -- Python AI Agent:**
```bash
cd services/agent-service
source venv/bin/activate          # Windows: venv\Scripts\activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
You will see:
```
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process
```

**Terminal 3 -- Go Gateway:**
```bash
cd services/gateway
go run ./cmd/server/...
```
You will see:
```
[GIN-debug] Listening and serving HTTP on :8002
```

**Terminal 4 -- Frontend:**
```bash
cd apps/web
npm run dev
```
You will see:
```
VITE v5.x.x  ready in 800ms
  Local:   http://localhost:3000/
```

Now open `http://localhost:3000` in your browser.

> [!] **Local dev note:** When running locally without Docker networking, update these in `.env`:
> ```
> DATABASE_HOST=localhost
> REDIS_HOST=localhost
> PYTHON_API_URL=http://localhost:8001
> ```

---

### Verifying everything is working

```bash
# Check Python agent health
curl http://localhost:8010/api/health

# Check Go gateway health
curl http://localhost:8002/api/health

# Submit a test query
curl -X POST http://localhost:8002/api/demo/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many tables are in the database?", "db_name": "IPL", "dialect": "sqlite"}'
```

Or use the Makefile:
```bash
make healthcheck
```

---

## 8. Running in Test Mode

### Unit Tests (Python)

```bash
cd services/agent-service
source venv/bin/activate

# All tests
pytest tests/ -v

# Unit tests only (no LLM calls, fast)
pytest tests/unit/ -v

# Integration tests (requires running services)
pytest tests/integration/ -v
```

Via Makefile:
```bash
make backend-test          # All tests
make backend-test-unit     # Unit only
make backend-test-integration
```

### What gets tested

| Test Suite | Location | What it tests |
|:-----------|:---------|:--------------|
| Unit | `tests/unit/` | Individual agents, validators, parsers -- no LLM |
| Integration | `tests/integration/` | Health endpoints, database connections |
| Pipeline | `agent/tests/test_pipeline_units.py` | Full agent pipeline with mocked LLM |

### Go Gateway Tests

```bash
cd services/gateway
go test ./... -v
```

Via Makefile:
```bash
make gateway-test
```

### Regression Tests

Regression tests check that prompts haven't accidentally changed (hash comparison):

```bash
make regression
```

This runs `scripts/regression.sh` which:
1. Compares SHA-256 hashes of all YAML prompt files against the stored baseline
2. Reports any modified prompts
3. Exits non-zero if critical prompts changed (use in CI to prevent accidental prompt regressions)

### Linting

```bash
make backend-lint    # Python: ruff check
```

---

## 9. Running in Production Mode

### Option A -- Docker Compose (recommended for single-server production)

**Step 1 -- Set production environment:**

In your `.env`:
```bash
ENVIRONMENT=production
GIN_MODE=release
ENABLE_AUTH=true
API_KEY_SECRET=your-secret-api-key

# Use real passwords
DATABASE_PASSWORD=a-very-strong-random-password-here
JWT_SECRET=a-64-character-random-string-here

# Set real domain
DOMAIN=yourdomain.com
```

**Step 2 -- Build all images:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
```

**Step 3 -- Start:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**Step 4 -- Verify:**
```bash
docker-compose ps
# All services should show "Up (healthy)"

make healthcheck
# All checks should show "ok"
```

**Step 5 -- View logs:**
```bash
docker-compose logs -f gateway    # Go gateway logs
docker-compose logs -f agent      # Python agent logs
docker-compose logs -f frontend   # Frontend build logs
```

---

### Production checklist

Before going live, verify all of these:

- [ ] `ENABLE_AUTH=true` is set
- [ ] `JWT_SECRET` is a random 64+ character string
- [ ] `DATABASE_PASSWORD` is strong (16+ chars, mixed)
- [ ] `API_KEY_SECRET` is set
- [ ] `.env` is not committed to Git
- [ ] SSL/TLS is configured in Nginx (add certs to `infrastructure/nginx/`)
- [ ] `ENVIRONMENT=production` is set
- [ ] `GIN_MODE=release` is set
- [ ] LLM credentials are valid
- [ ] `docker-compose -f docker-compose.prod.yml` is used (not the dev compose)
- [ ] Monitoring is reachable at `/prometheus/metrics`
- [ ] Backup script is scheduled: `make backup`

---

### Nginx + SSL

For production SSL, place your certificates in `infrastructure/nginx/certs/` and update `infrastructure/nginx/nginx.conf`:

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;
    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ...
}
```

For free SSL via Let's Encrypt:
```bash
certbot certonly --standalone -d yourdomain.com
# Copy certs to infrastructure/nginx/certs/
```

---

### Data backup

```bash
# Run once
make backup

# Schedule in cron (runs daily at 2 AM):
0 2 * * * cd /path/to/TT_SQL_V2 && make backup
```

The backup script saves:
- PostgreSQL dump
- Learning state (`data/knowledge/`)
- Run artifacts (`data/runs/`)

---

## 10. API Reference

All API calls go through the Go gateway on port `8002` (or port `80` via Nginx in production).

### Health

```http
GET /api/health
```
Returns status of all subsystems (results dir, databases dir, lessons file, LLM config, prompts, DAB repo).

```json
{
  "overall": "healthy",
  "checks": [
    {"name": "results_dir", "status": "ok", "detail": {...}},
    {"name": "llm_config", "status": "ok", "detail": {...}}
  ]
}
```

---

### Run a Single Query

```http
POST /api/demo/query
Content-Type: application/json

{
  "question": "Which customers placed the most orders last month?",
  "db_name": "orders_db",
  "dialect": "sqlite"
}
```

| Field | Required | Description |
|:------|:---------|:------------|
| `question` | [OK] | Natural language question |
| `db_name` | [OK] | Database name (must exist in databases dir) |
| `dialect` | [OK] | `sqlite` / `duckdb` / `snowflake` / `postgres` / `bigquery` |
| `instance_id` | [X] | Optional ID for tracking (auto-generated if omitted) |

**Response:**
```json
{
  "status": "success",
  "sql": "SELECT customer_id, COUNT(*) FROM orders WHERE ...",
  "result": [...],
  "latency_ms": 8420,
  "tokens_used": 12400
}
```

---

### Run Instance by ID (Benchmark)

```http
POST /api/run_instance/{instance_id}
```
Runs a specific benchmark instance from the loaded JSONL file.

---

### Run All Instances for a Database

```http
POST /api/run/{db_name}
```
Runs all questions for the specified database.

---

### Stream Live Execution

```http
GET /api/stream/{db_name}/{instance_id}
```
Returns Server-Sent Events (SSE) with live stage-by-stage updates as the pipeline runs.

```
event: stage
data: {"stage": "schema_linking", "status": "running", "agent": "SchemaLinker"}

event: stage
data: {"stage": "sql_generation", "status": "complete", "sql": "SELECT ..."}

event: done
data: {"is_running": false, "status": "success"}
```

---

### Results

```http
GET /api/results/recent          # Last 50 results across all databases
GET /api/results/all             # All results
GET /api/results/{db_name}       # Results for specific database
GET /api/details/{db_name}/{instance_id}   # Full execution log for one run
```

---

### Metrics & Analytics

```http
GET /api/metrics?date=all        # Aggregate accuracy, latency, cost
GET /api/performance             # Real-time P50/P95/P99 latency percentiles
GET /api/analytics/queries       # Recent query events
GET /api/analytics/failures      # Failure breakdown by category
GET /api/analytics/stats         # Success rate, avg latency
GET /api/analytics/quality       # Data quality scores
GET /api/analytics/validation    # Validator pass rates
GET /api/analytics/retrieval     # RAG retrieval hit rates
```

---

### DAB (DataAgentBench)

```http
GET  /api/dab/queries            # List all DAB queries
POST /api/dab/run/{query_id}     # Run a specific DAB query
GET  /api/dab/status             # Running task status
GET  /api/dab/results            # All DAB evaluation results
```

---

### Diagnose a Failed Run

```http
GET /api/diagnose/{db_name}/{instance_id}
```
Returns structured diagnosis of what went wrong: schema gaps, SQL errors, validator rejections -- without making any LLM call. Pure file regex parsing.

---

### Fix a Failed Run (with AI)

```http
POST /api/fix_issues/{db_name}/{instance_id}
```
Triggers the AI pipeline to retry a failed instance with context from the previous failure.

---

### Learning / Lessons

```http
GET  /api/lessons                # Get all active learning rules
GET  /api/lessons/count          # Number of active rules
POST /api/lessons/rollback/{version}  # Rollback to a previous lessons snapshot
POST /api/improvement/run        # Trigger self-improvement cycle
```

---

## 11. Benchmark & Evaluation

### Running Spider2-Lite

```bash
# Full benchmark run (all instances)
make benchmark

# Or directly:
cd services/agent-service
python -m agent.scripts.run_batch --config config/spider2_lite.yaml
```

Results are saved to `data/runs/` as `.csv` (results) and `.md` (execution log) per instance.

### Evaluating Results

```bash
# Check accuracy against gold answers
python -m agent.scripts.compile_submission

# View via API
curl http://localhost:8002/api/metrics?date=all
```

### Running DataAgentBench (DAB)

```bash
# Via UI: go to the Dashboard -> DAB tab -> Run All
# Or via API:
curl -X POST http://localhost:8002/api/dab/run/all

# Or via CLI:
cd services/agent-service
python workers/dab/dab_runner.py
```

### Gold Evaluation

Gold evaluation runs automatically after each instance. It:
1. Loads the gold CSV from `data/knowledge/gold/exec_result/`
2. Compares predicted CSV against gold
3. Marks as `gold_pass` or `gold_fail`
4. Includes tolerance for floating-point comparisons

---

## 12. Learning System

The platform learns from its own runs automatically.

### How it works

```
Successful run -> MetaLearner captures pattern -> Saved to dynamic_lessons.json
                                                        |
                                                 Loaded by Orchestrator
                                                 on next query (TTL-cached 60s)
                                                        |
                                             SchemaLinker + SQLGenerator
                                             inject relevant rules into prompts
```

### Managing lessons

```bash
# View active lessons count
curl http://localhost:8002/api/lessons/count

# View all active lessons
curl http://localhost:8002/api/lessons

# Run manual self-improvement cycle
curl -X POST http://localhost:8002/api/improvement/run

# Rollback if a bad lesson degraded accuracy
curl -X POST http://localhost:8002/api/lessons/rollback/v3
```

### Lesson versioning

Every time lessons are modified, a snapshot is saved. You can always roll back:

```bash
# List available snapshots
ls data/knowledge/snapshots/

# Rollback to specific version via API
curl -X POST "http://localhost:8002/api/lessons/rollback/2024-01-15_v2"
```

---

## 13. Observability & Monitoring

### Prometheus metrics

Available at: `http://localhost:8002/prometheus/metrics`

Key metrics:
- `http_requests_total` -- request counts by endpoint + status
- `http_request_duration_seconds` -- latency histogram
- `agent_pipeline_duration_seconds` -- AI pipeline latency
- `llm_tokens_total` -- token usage by model

### Grafana dashboards

Start monitoring stack:
```bash
docker-compose -f docker-compose.yml up -d monitoring
```

Access Grafana at: `http://localhost:3001` (default: admin/admin)

Pre-built dashboards in `monitoring/grafana/`:
- **Pipeline Overview** -- success rate, latency, token cost
- **Agent Performance** -- per-agent latency breakdown
- **Learning System** -- lesson count, self-improvement rounds

### Logs

```bash
# Follow all logs
make docker-logs

# Python agent logs only
docker-compose logs -f agent

# Go gateway access logs only
docker-compose logs -f gateway

# Local development (logs to stdout)
tail -f services/agent-service/agent/logs/app.log
```

### Performance endpoint

```bash
curl http://localhost:8002/api/performance
```
Returns:
```json
{
  "latency": {"p50_s": 8.2, "p95_s": 24.1, "p99_s": 45.3, "sla_ok": true},
  "tokens": {"total": 1200000, "avg_per_query": 8400},
  "cache": {"hit_rate": 0.34},
  "concurrency": {"active_queries": 2, "max": 10}
}
```

---

## 14. Makefile Quick Reference

Run `make help` to see all targets.

```
make start               Start all services (gateway + backend + frontend)
make stop                Stop all services
make restart             Restart all services

make backend-run         Start Python agent (dev, with --reload)
make backend-install     Install Python dependencies
make backend-test        Run all Python tests
make backend-test-unit   Run unit tests only
make backend-lint        Lint Python source

make gateway-build       Compile Go gateway binary
make gateway-run         Run compiled Go gateway
make gateway-test        Run Go tests

make frontend-run        Start React dev server
make frontend-install    Install npm dependencies
make frontend-build      Build for production

make docker-up           Start all containers
make docker-down         Stop all containers
make docker-build        Build all Docker images
make docker-logs         Follow all container logs

make benchmark           Run BIRD/Spider2 benchmarks
make regression          Run prompt + validator regression
make backup              Backup learning database
make healthcheck         Check all service endpoints
make clean-runs          Trim run artifacts (keep last 50)
```

---

## 15. Troubleshooting

### Python agent fails to start

**Symptom:** `ModuleNotFoundError` or import errors on startup.

**Fix:**
```bash
cd services/agent-service
# Make sure you're in the venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```

---

### Go gateway fails to build

**Symptom:** `go build` fails with module errors.

**Fix:**
```bash
cd services/gateway
go clean -modcache
go mod download
go build ./cmd/server/...
```

---

### "Cannot connect to database"

**Symptom:** Python logs show `psycopg2.OperationalError: could not connect to server`

**Check:**
```bash
# Is Postgres running?
docker-compose ps postgres

# Test connection manually
docker exec -it $(docker-compose ps -q postgres) psql -U ttsql -d ttsql -c "SELECT 1"
```

**Fix:** Make sure `DATABASE_HOST` in `.env` is:
- `postgres` when running inside Docker
- `localhost` when running Python natively

---

### "Redis connection refused"

**Symptom:** Cache or session errors at startup.

**Fix:**
```bash
# Is Redis running?
docker-compose ps redis

# Start just the databases
docker-compose -f docker-compose.db.yml up -d

# Verify
redis-cli -h localhost ping
# Should respond: PONG
```

---

### LLM calls failing

**Symptom:** `botocore.exceptions.NoCredentialsError` or `AuthenticationError`

**Check:**
```bash
# Verify env vars are loaded
cd services/agent-service && python -c "
from dotenv import load_dotenv
load_dotenv(dotenv_path='../../.env', override=True)
import os
print('Key set:', bool(os.getenv('BEDROCK_ACCESS_KEY_ID')))
print('Provider:', os.getenv('LLM_PROVIDER'))
"
```

**Fix:** Make sure `.env` is at the repo root and all keys are filled.

---

### Frontend shows blank page

**Symptom:** `http://localhost:3000` loads but shows nothing.

**Check:**
```bash
# Is the API reachable?
curl http://localhost:8002/api/health

# Check browser console for errors (F12)
# Usually CORS or wrong API URL
```

**Fix:** Make sure `VITE_API_BASE_URL=/api` is in `apps/web/.env` and the Go gateway is running.

---

### Gold evaluation always shows 0%

**Symptom:** All runs show `gold_fail` even when SQL is correct.

**Check:**
```bash
# Is the gold data present?
ls data/knowledge/gold/exec_result/
# Should contain .csv files named by instance_id
```

**Fix:** Download the Spider2-Lite gold evaluation files and place them in `data/knowledge/gold/`.

---

### Run artifacts filling up disk

```bash
# Check size
du -sh data/runs/

# Trim to last 50 runs (keeps the newest)
make clean-runs
```

---

## 16. Contributing

### Branch strategy

```
main          <- production-ready, protected
develop       <- integration branch for features
feature/*     <- individual feature branches
fix/*         <- bug fix branches
```

### Development workflow

```bash
# 1. Create your branch
git checkout develop
git pull
git checkout -b feature/my-feature

# 2. Make changes, test locally
make backend-test
make backend-lint

# 3. Run regression before PR
make regression

# 4. Push and open PR against develop
git push origin feature/my-feature
```

### Adding a new agent

1. Create `services/agent-service/core/agents/my_agent.py`
2. Create the prompt YAML: `services/agent-service/agent/app/core/prompts/my_agent.yaml`
3. Register it in the orchestrator: `services/agent-service/agent/app/core/orchestrator.py`
4. Add unit tests: `services/agent-service/tests/unit/test_my_agent.py`

### Adding a new database dialect

1. Add dialect rules: `services/agent-service/agent/app/core/dialects/`
2. Add dialect config: `services/agent-service/config/system_params.yaml`
3. Add dialect to `DatabaseExecutor`: `services/agent-service/core/sql/db_executor.py`

### CI/CD

GitHub Actions runs on every push to `main` and `develop`:
- Python syntax check
- Unit tests
- Linting
- Gateway build

See `.github/workflows/ci.yml` for the full pipeline.

---

## Appendix: Quick Start Cheatsheet

```bash
# == ONE-TIME SETUP ===============================================
cp .env.example .env                    # Create config file
# Edit .env with your LLM credentials

cd services/agent-service
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cd ../..

cd services/gateway && go mod download && cd ../..
cd apps/web && npm install && cd ../..

# == DAILY DEV (native processes) ==================================
docker-compose -f docker-compose.db.yml up -d       # Start Postgres + Redis

# Terminal 2:
cd services/agent-service && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 3:
cd services/gateway && go run ./cmd/server/...

# Terminal 4:
cd apps/web && npm run dev

# == OR EVERYTHING VIA DOCKER =====================================
docker-compose up                                    # Dev mode (foreground)
docker-compose up -d                                 # Dev mode (background)
docker-compose -f docker-compose.yml \
               -f docker-compose.prod.yml up -d      # Production mode

# == TESTING ======================================================
make backend-test                                    # All Python tests
make backend-test-unit                               # Unit tests only
make gateway-test                                    # Go tests
make regression                                      # Prompt regression

# == HEALTH =======================================================
make healthcheck
curl http://localhost:8002/api/health

# == STOP =========================================================
docker-compose down                                  # Stop all containers
docker-compose down -v                               # Stop + wipe DB volumes
```

---

*Built with  by the nquire team. For issues, open a GitHub issue or check the [docs](docs/) folder.*
