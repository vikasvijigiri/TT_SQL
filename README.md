# TT_SQL: nQuiry Text2SQL Agent

nQuiry is an industry-grade Text-to-SQL engine that converts natural language questions into executable SQL queries with high precision. It uses a **layered multi-agent architecture** to analyze, plan, generate, critique, and refine SQL queries iteratively.

## ✨ Key Features

- **Layered Architecture**: 4-layer pipeline (Input → Planning → Generation → Execution) with 7 specialized agents.
- **Self-Correction Loop**: A Critic agent validates SQL logic; the Builder auto-refines on failure (up to 5 retries).
- **Schema-Aware**: Extracts full database schema, selects only relevant tables, and builds FK relationship graphs.
- **Intent Classification**: Automatically detects query type (AGGREGATION, RANKING, etc.) and complexity.
- **RAG-Augmented**: Optional vector search (Qdrant) or Amazon Bedrock KB for few-shot learning AND fast vector semantic table retrieval (bypassing LLM when `--use-rag` is set).
- **Batch Processing**: High-performance parallel batch runner with progress tracking.
- **Safe Execution**: Only executes `SELECT` statements by design.

Read the [Detailed Architecture Guide](docs/ARCHITECTURE.md) for more depth.

---

## 🏗️ Architecture Overview

```
User Query
    │
    ▼
┌──────────────────────────────────────────────┐
│  📥 INPUT LAYER (Context & Pruning)           │
│  ContextEnrichmentAgent (RAG / Schema API)    │
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

#### Core Pipeline Agents

| # | Agent Class | Layer | LLM? | Purpose |
|---|-------------|-------|------|---------|
| 1 | `ContextEnrichmentAgent` | Input | No | Fetches full schema (SQLite/BQ/SF) and performs RAG column retrieval. |
| 2 | `TableSelectorAgent` | Input | **Yes** | Uses LLM to prune irrelevant tables and detect query intent/complexity. |
| 3 | `StepByStepPlannerAgent` | Planning | **Yes** | Generates a high-level execution roadmap for the query. |
| 4 | `MultiCandidateGeneratorAgent`| Generation| **Yes** | Generates SQL candidates (CTE, Joins, etc.) based on the plan. |
| 5 | `CriticAgent` | Generation | **Yes** | Validates SQL logic against a checklist (no execution). |
| 6 | `RefinementLoopAgent` | Generation | No | Orchestrates the Builder-Critic retry cycle. |
| 7 | `ExecutorAgent` | Execution | No | Dialect-specific execution (SQLite, BigQuery, Snowflake, Postgres). |

#### Post-Processing & Analysis Agents

| Agent Class | Purpose |
|-------------|---------|
| `SuccessAnalysisAgent` | Identifies success patterns in generated SQL for future few-shot learning. |
| `FailureAnalysisAgent` | Performs post-mortem analysis on failed queries to classify error types (hallucination, logic, etc.). |
| `DatasetFormatterAgent` | Intelligent utility that uses LLM to convert unstructured text/CSV into JSONL pipeline format. |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Git**
- An API key for **AWS Bedrock** (e.g., Claude 3.5 Sonnet or Custom Safeguard models)

### 2. Clone the Repository
```bash
git clone https://github.com/NG-VikasV/TT_SQL.git
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
To ensure the `tt_sql` package is recognized, set your `PYTHONPATH` to the `src` directory:

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH="src"
```

**Mac/Linux:**
```bash
export PYTHONPATH=src
```

Alternatively, install the project in editable mode:
```bash
pip install -e .
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
LLM_API_BASE=http://... # Optional if using proxy
```

### 🔓 Optional Variables

```ini
# RAG — Qdrant vector store (few-shot learning)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key-if-cloud-hosted

# RAG — Amazon Bedrock Knowledge Base
BEDROCK_KB_ID=your-knowledge-base-id

# Model overrides per agent
PLANNER_MODEL=bedrock/openai.gpt-oss-safeguard-120b
GENERATOR_MODEL=bedrock/openai.gpt-oss-safeguard-120b
```

---

## 🏃‍♂️ Running the Application

### Single Question (CLI)
```bash
python -m tt_sql.cli.run_single --id local020 --model gpt-4o
```

### Batch Processing (CLI)
We provide dedicated batch runners optimized for each database dialect.

#### 1. SQLite Batch Runner
Best for local testing with the Spider 2.0 dataset.
```bash
python -m tt_sql.cli.run_batch_sqlite --dataset data/spider2-lite-sqlite.jsonl --model gpt-4o --workers 4
```

#### 2. BigQuery (GCP) Batch Runner
Connects to Google BigQuery datasets.
```bash
python -m tt_sql.cli.run_batch_gcp --dataset data/spider2-lite-bigquery.jsonl --model gpt-4o --workers 4
```

#### 3. Snowflake Batch Runner
Connects to Snowflake cloud data warehouses.
```bash
python -m tt_sql.cli.run_batch_snowflake --dataset data/spider2-lite-snowflake.jsonl --model gpt-4o --workers 4
```

**Batch Runner Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--dataset` | `data/spider2-lite1.jsonl` | Path to JSONL dataset |
| `--model` | `.env` LLM_MODEL | LLM model name |
| `--workers` | `4` | Parallel worker threads |
| `--limit` | `0` (all) | Limit number of tasks |
| `--rag` | `none` | RAG source (`none`, `qdrant`, `bedrock`) |
| `--use-rag` | `false` | Bypass LLM and use vector store semantic similarity for table selection |
| `--overwrite` | `false` | Re-run even if results exist |

### Dataset Formatter — Convert Any File to JSONL

Use `scripts/format_dataset.py` to convert a file of questions (in **any format**) into the `spider2-lite.jsonl` schema the pipeline expects.

**Supported input formats:** `.csv`, `.xlsx`, `.xls`, `.json`, `.jsonl`, `.txt`, `.md`

```bash
# From a CSV/Excel (no LLM needed)
python scripts/format_dataset.py --input my_questions.csv --db IPL

# From a free-form text or Markdown file (uses LLM to extract questions)
python scripts/format_dataset.py --input questions.txt --db bank_sales_trading

# Custom output path and ID prefix
python scripts/format_dataset.py --input file.csv --output data/my_dataset.jsonl --id-prefix local_custom
```

### Gold Standard Result Generation

Use `scripts/generate_gold_results.py` to execute ground-truth SQL queries and save the results as individual CSV files.

```bash
python scripts/generate_gold_results.py
```

### Executing Gold SQL Files

Use `python -m tt_sql.cli.execute_sql` to run isolated SQL files.

```bash
# Execute all SQL files in the default directory (data/gold/sql/)
python -m tt_sql.cli.execute_sql

# Execute SQL files from a specific directory
python -m tt_sql.cli.execute_sql --dir data/gold/sql/
```

**Formatter Options:**

| Flag | Description |
|------|-------------|
| `--input` / `-i` | Path to the input file (**required**) |
| `--output` / `-o` | Output JSONL path (default: `data/<input_stem>_formatted.jsonl`) |
| `--db` | Default database name when not supplied by the file |
| `--id-prefix` | Prefix for auto-generated `instance_id`s (default: `custom`) |
| `--model` | LLM model for unstructured text parsing (default: `LLM_MODEL` from `.env`) |

**Column mapping for CSV/Excel:**

The agent intelligently detects columns by name aliases — no strict column naming required:

| Field | Detected aliases |
|-------|-----------------|
| `question` | `question`, `query`, `q`, `text`, `prompt`, `input`, `nl` |
| `db` | `db`, `database`, `db_name`, `database_name` |
| `instance_id` | `instance_id`, `id`, `instance`, `idx` |
| `external_knowledge` | `external_knowledge`, `knowledge`, `context`, `kb` |

---

### Output
For each processed question, results are saved under `results/<model>/`:
- `sql/<instance_id>.sql` — Final validated SQL query
- `csv/<instance_id>.csv` — Execution result data
- `log/<instance_id>.md` — Detailed execution log

---

## 📂 Project Structure

```text
old_txt_sql_spider2.0/
├── config/                 # External configuration (secrets, global configs)
├── data/                   # Dataset management (raw and processed)
├── docs/                   # Documentation and Architecture
├── results/                # Analytical outputs (SQL, CSVs, logs)
├── scripts/                # Internal utility and analysis scripts
│   └── analysis/           # Result analysis and post-mortems
├── src/                    # Source code
│   └── tt_sql/             # Core package
│       ├── agents/         # Agent logic layers
│       ├── cli/            # CLI entry points (run_single, run_batch, etc.)
│       ├── core/           # Infrastructure and orchestrators
│       ├── prompts/        # YAML templates
│       ├── rag/            # Vector store/RAG logic
│       └── utils/          # Shared utilities
├── .env                    # Environment variables
├── pyproject.toml           # Package metadata
└── requirements.txt         # Dependencies
```

---

## 📊 Result Analysis

After running a batch, you can analyze the results using the specialized scripts in `scripts/analysis/`:

### 1. Success/Failure Identification
```bash
python scripts/analysis/identify_successes.py --model bedrock_openai.gpt-oss-safeguard-120b
```

### 2. Post-Mortem Failure Analysis (LLM-based)
```bash
python scripts/analysis/failure_analysis.py --csv failed_ids.csv --model gpt-4o
```

### 3. Consolidated Report Generation
```bash
python scripts/analysis/analyze_results.py --model gpt-4o
```

---

## 🧠 RAG Implementation

nQuiry supports **Retrieval-Augmented Generation (RAG)** to improve accuracy via few-shot learning:

1. **Vector Store**: Maintains a database of `(Question, Correct SQL)` pairs.
2. **Retrieval**: Finds top semantically similar past questions for a new query.
3. **Context Injection**: Injects retrieved examples into the prompt as few-shot examples.
4. **Continuous Learning**: Successfully executed queries (score=100%) can be upserted back.

**Supported Backends:**
- **Qdrant** — Local development or Docker deployment
- **Amazon Bedrock Knowledge Base** — Managed AWS solution

---

## 📊 LLM Call Count

| Pipeline Stage | LLM Calls |
|---|---|
| `TableSelectorAgent` (Pruning + Intent) | 1 *(0 if RAG matches precisely)* |
| `StepByStepPlannerAgent` (Roadmap) | 1 |
| `MultiCandidateGeneratorAgent` (Builder) | 1 per attempt |
| `CriticAgent` (Analysis) | 1 per attempt |
| **Minimum (1 attempt)** | **4** |
| **Maximum (5 retries)** | **12** |

---

## 📄 License

This project is developed for research and educational purposes.
