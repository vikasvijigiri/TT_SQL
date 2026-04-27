# TT_SQL: nQuiry Text2SQL Agent

nQuiry is an industry-grade Text-to-SQL engine that converts natural language questions into executable SQL queries with high precision. It uses a **layered multi-agent architecture** to analyze, plan, generate, critique, and refine SQL queries iteratively.

## ✨ Key Features

- **Layered Architecture**: 4-layer pipeline (Input → Planning → Generation → Execution) with structured agents.
- **Self-Correction Loop**: A Critic agent validates SQL logic and schema mapping; the Builder auto-refines on failure (up to 5 retries).
- **Schema-Agnostic Planning**: Uses bottom-up natural language reasoning for planning, independent of database schema context to prevent early filtering errors.
- **Sliding Window Selector**: Handles very large schemas by processing tables in iterative windows, bypassing LLM context limits.
- **Unified Batch Processing**: High-performance parallel batch runner (`run_batch.py`) replacing fragmented scripts, featuring powerful filtering by dialect, database name, and specific task IDs.
- **Dynamic Metadata Expansion**: The execution pipeline automatically requests missing metadata from the cache rather than failing out immediately.
- **Centralized Metadata Cache**: Employs a 'Read-Once' structural metadata cache scoped to the DB-level, dramatically reducing API calls across large multi-task datasets like Spider 2.0.
- **Flattened Output Structure**: Lean, DB-scoped hierarchy structure to maintain cleanly partitioned multi-database outputs.
- **Safe Execution**: Only executes `SELECT` statements by design.

---

## 🏗️ Architecture Overview

```text
User Query
    │
    ▼
┌──────────────────────────────────────────────┐
│  📥 INPUT LAYER (Context & Pruning)           │
│  ContextEnrichmentAgent (Centralized Cache)   │
│  └→ TableSelectorAgent (🤖 LLM Pruning)       │
│                                               │
│  Outputs: schema_info, relevant_tables,       │
│           query_intent, complexity            │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  📋 PLANNING LAYER (Strategy)                 │
│  StepByStepPlannerAgent (🤖 LLM Planning)     │
│  └→ Bottom-Up Reasoning (Schema-Agnostic)     │
│                                               │
│  Outputs: execution_roadmap, sub_tasks        │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  ⚡ GENERATION LAYER (RefinementLoop)         │
│                                               │
│  ┌────────────┐ feedback ┌────────────┐      │
│  │ SQLBuilder  │◄────────┤ SQLCritic  │      │
│  │    (🤖)     │────────►│    (🤖)     │      │
│  └────────────┘   SQL    └────────────┘      │
│        ▲                      │ ✅ PASS      │
│        └─── retry (max 5) ────┘              │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  🚀 EXECUTION LAYER (Dialect-Specific)        │
│  SQLite / BigQuery / Snowflake / Postgres     │
│  └→ .sql + .csv results                       │
└──────────────────────────────────────────────┘
```

> 🤖 = LLM call

### Agent Summary

| # | Agent Class | Layer | LLM? | Purpose |
|---|-------------|-------|------|---------|
| 1 | `ContextEnrichmentAgent` | Input | No | Leverages centralized metadata cache or dynamically fetches full schema for (SQLite/BQ/SF/Postgres). |
| 2 | `TableSelectorAgent` | Input | **Yes** | Uses **Sliding Window** LLM selection to safely prune massive database schemas into relevant active contexts. |
| 3 | `StepByStepPlannerAgent` | Planning | **Yes** | Generates a **Schema-Agnostic** step-by-step roadmap serving as a SQL generation strategy guide. |
| 4 | `RefinementLoopAgent` | Generation| No | Orchestrates the vital Builder-Critic retry cycle. Detects missing metadata triggers for schema fallback. |
| 5 | `SQLCriticAgent` | Generation | **Yes** | Validates generated SQL logic against the actual database schema via structural checks (no execution). |
| 6 | `ExecutorAgent` | Execution | No | Dialect-specific executions handling execution faults and generating final flat DB outputs. |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Git**
- An API key for **AWS Bedrock** (e.g., Claude 3.5 Sonnet or Custom Safeguard models)

### 2. Clone the Repository
```bash
git clone https://github.com/NG-VikasV/git
cd TT_SQL
```

### 3. Set Up Virtual Environment
**Windows:**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Environment Setup (Critical)
To ensure the code runs reliably from the project root, configure your `PYTHONPATH` to the `src` directory:

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH="src"
```

**Mac/Linux:**
```bash
export PYTHONPATH=src
```

---

## ⚙️ Configuration (.env)

Create a `.env` file in the project root:

### 🔒 LLM Configuration (Bedrock)

```ini
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_DEFAULT_REGION=us-east-1
LLM_MODEL=bedrock/openai.gpt-oss-safeguard-120b
# No LLM_API_BASE needed for serverless
```

### 🔓 Database Path Targets
By default, the pipeline searches for DB files like `.sqlite` in the `resources` directory unless otherwise specified:
```ini
SQLITE_DB_PATH=resources/
```

---

## 🏃‍♂️ Running the Application


### Unified Batch Processing (CLI)
Unlike legacy implementations with fragmented shell scripts, `run_batch.py` handles all execution workflows across BigQuery, Snowflake, and SQLite while intelligently skipping cached results.

```bash
# 1. Run All SQLite tasks (Implicitly selects spider2-lite-sqlite dataset)
python src/cli/run_batch.py --type sqlite --workers 4

# 2. Filter Batch by Database (Runs only task blocks targeting 'IPL')
python src/cli/run_batch.py --type sqlite --db IPL --workers 2

# 3. Target Specific IDs (Great for re-trying failures)
python src/cli/run_batch.py --type sqlite --ids local023 local088

# 4. Snowflake execution
python src/cli/run_batch.py --type snowflake --workers 4

# 5. BigQuery execution targeting specific domains
python src/cli/run_batch.py --type bigquery --db google_analytics
```

**Batch Runner Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--type` | `sqlite` | Targeted backend connection (`sqlite`, `snowflake`, `bigquery`) |
| `--db` | `None` | Filters batch to only process tasks interacting with this Database. |
| `--ids` | `None` | Restricts batch execution strictly to this space-separated list of IDs. |
| `--dataset` | *Auto-detected*| Explicit string target to a specific JSONL Dataset path. |
| `--model` | `.env LLM_MODEL` | Specific LLM proxy model block. |
| `--workers` | `4` | Parallelized batch threads limit. |
| `--limit` | `0` (all) | Constrain total batch queries to cap runtimes. |
| `--overwrite` | `false` | Ignore occupancy caches and overwrite existing output payload. |

---

## 📂 Project Output Structure

The application natively generates a flattened configuration logic nested solely by the target Database. Metadata is isolated strictly into the global resource pool preventing redundant generation overheads.

```text
old_txt_sql_spider2.0/
├── config/                 # External configuration (secrets, global configs)
├── input_data/             # Dataset management (raw and processed)
├── docs/                   # Documentation and Architecture
├── resources/              
│   ├── metadata/           # Cached schemas loaded via Context Enrichment
│   └── spider2-localdb/    # Target databases
├── results/                # Organized analytical payload structure
│   └── <db_name>/          # Flattened output hierarchy avoids subfolder drift
│       ├── <id>.csv        # Generated data
│       ├── <id>.md         # Agent reasoning log
│       ├── <id>_plan.md    # Agent plan log
│       └── <id>.sql        # Validated query
├── src/                    # Source code
│   └── agents/             # Agent logic layers
│   ├── cli/                # Consolidated CLI workflows
│   ├── core/               # Infrastructure, Paths, Logger, Coordinators
│   └── prompts/            # Centralized YAML Dialect templates
├── .env                    
└── requirements.txt         
```

---

## 📊 Result Analysis / Evaluation

After running a batch, you can evaluate the accuracy of the generated queries against the gold truth using the official Spider 2.0 evaluation script:

```bash
# Evaluate SQL execution accuracy for a specific database using exec_result mode
python gold/evaluate.py --mode exec_result --result_dir results/IPL --gold_dir gold
```

*This compares generated `.csv` outputs directly against the gold evaluations and will print out line-by-line validation states (PASS/FAIL) and an accuracy summary.*

---

## 📊 LLM Call Count Overview

The architecture maximizes strict validation by sacrificing 1-shot API savings for high-precision accuracy. RAG elements have been fully decoupled to streamline context resolution directly derived from source schemas.

| Pipeline Stage | LLM Calls |
|---|---|
| `TableSelectorAgent` (Sliding Window Config) | Variable dependent on Schema Scope |
| `StepByStepPlannerAgent` (Strategy Roadmap) | 1 |
| `SQLBuilderAgent` (SQL Syntax Synthesis) | 1 per attempt |
| `SQLCriticAgent` (Analysis / Validation) | 1 per attempt |
| **Minimum (1 attempt)** | ~4 |
| **Maximum (5 retries)** | ~12+ |

---

## 📄 License

This project is developed for continuous analytical reporting research purposes.
