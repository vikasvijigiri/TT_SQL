# TT_SQL: nQuiry Text2SQL Agent

nQuiry is an industry-grade Text-to-SQL engine that converts natural language questions into executable SQL queries with high precision. It uses a **layered multi-agent architecture** to analyze, plan, generate, critique, and refine SQL queries iteratively.

## ✨ Key Features

- **Layered Architecture**: 4-layer pipeline (Input → Planning → Generation → Execution) with 7 specialized agents.
- **Self-Correction Loop**: A Critic agent validates SQL logic; the Builder auto-refines on failure (up to 5 retries).
- **Schema-Aware**: Extracts full database schema, selects only relevant tables, and builds FK relationship graphs.
- **Intent Classification**: Automatically detects query type (AGGREGATION, RANKING, etc.) and complexity.
- **RAG-Augmented**: Optional vector search (Qdrant) or Amazon Bedrock Knowledge Bases for few-shot learning.
- **Batch Processing**: High-performance parallel batch runner with progress tracking.
- **Safe Execution**: Only executes `SELECT` statements by design.

---

## 🏗️ Architecture Overview

```
User Query
    │
    ▼
┌──────────────────────────────────────────────┐
│  📥 INPUT LAYER                               │
│  SQLiteFileLoader → SchemaAnalyzer            │
│                   → TableSelector (🤖 LLM)    │
│                                               │
│  Outputs: schema_info, relevant_tables,       │
│           query_intent, complexity             │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  📋 PLANNING LAYER                            │
│  RelationshipGraphBuilder → QueryPlanner (🤖) │
│                                               │
│  Outputs: FK relationship_graph,              │
│           step_by_step_plan                    │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  ⚡ GENERATION LAYER (RefinementLoop)         │
│                                               │
│  ┌───────────┐  feedback  ┌──────────┐       │
│  │SQLBuilder │◄───────────│SQLCritic │       │
│  │   (🤖)    │───────────►│   (🤖)   │       │
│  └───────────┘  SQL       └──────────┘       │
│       ▲                       │ ✅ PASS       │
│       └── retry (max 5) ─────┘               │
└────────────────────┬─────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│  🚀 EXECUTION LAYER                          │
│  SQLiteExecutor → .sql + .csv output files    │
└──────────────────────────────────────────────┘
```

> 🤖 = LLM call

### Agent Summary

| # | Agent | Layer | LLM? | Purpose |
|---|-------|-------|------|---------|
| 1 | `SQLiteFileLoader` | Input | No | Locates the `.sqlite` database file |
| 2 | `SchemaAnalyzer` | Input | No | Extracts full schema (tables, columns, types, FKs) |
| 3 | `TableSelector` | Input | **Yes** | Picks relevant tables + classifies intent & complexity |
| 4 | `RelationshipGraphBuilder` | Planning | No | Builds FK relationship graph between selected tables |
| 5 | `QueryPlanner` | Planning | **Yes** | Breaks query into a step-by-step action plan |
| 6 | `SQLBuilder` | Generation | **Yes** | Generates SQL from plan + schema + critic feedback |
| 7 | `SQLCritic` | Generation | **Yes** | Validates SQL logic (no execution, pure analysis) |
| 8 | `SQLiteExecutor` | Execution | No | Executes final SQL, saves `.sql` + `.csv` |
| 9 | `RefinementLoop` | Generation | No | Orchestrates Builder→Critic loop (max 5 retries) |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Git**
- An API key for **OpenAI** (GPT-4o) or **AWS Bedrock** (Claude 3.5 Sonnet)

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

---

## ⚙️ Configuration (.env)

Create a `.env` file in the project root:

### 🔒 LLM Provider (Choose One)

**Option A — OpenAI (GPT-4o):**
```ini
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o
```

**Option B — AWS Bedrock (Claude 3.5 Sonnet):**
```ini
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_DEFAULT_REGION=us-east-1
LLM_MODEL=bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0
```

### 🔓 Optional Variables

```ini
# RAG — Qdrant vector store (few-shot learning)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key-if-cloud-hosted

# RAG — Amazon Bedrock Knowledge Base
BEDROCK_KB_ID=your-knowledge-base-id

# Model overrides per agent
PLANNER_MODEL=gpt-4o
GENERATOR_MODEL=gpt-4o
```

---

## 🏃‍♂️ Running the Application

### Single Question (CLI)
```bash
python scripts/run_single.py
```
Edit `target_id` and `model_name` in `scripts/run_single.py` to configure which task to run.

### Batch Processing (CLI) — Recommended
```bash
python scripts/run_batch.py --dataset data/spider2-lite.jsonl --model gpt-4o --workers 4
```

**Batch Runner Options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--dataset` | `data/spider2-lite1.jsonl` | Path to JSONL dataset |
| `--model` | `.env` LLM_MODEL | LLM model name |
| `--workers` | `4` | Parallel worker threads |
| `--limit` | `0` (all) | Limit number of tasks |
| `--rag` | `none` | RAG source (`none`, `qdrant`) |
| `--overwrite` | `false` | Re-run even if results exist |

### Output
For each processed question, results are saved under `results/<model>/`:
- `sql/<instance_id>.sql` — Final validated SQL query
- `csv/<instance_id>.csv` — Execution result data
- `log/<instance_id>.md` — Detailed execution log

---

## 📂 Project Structure

```text
TT_SQL/
├── README.md                   # This file
├── ARCHITECTURE.md             # Detailed architecture documentation
├── pyproject.toml              # Package metadata
├── requirements.txt            # Python dependencies
├── .env                        # API keys (git-ignored)
│
├── scripts/                    # 🔥 CLI entry points
│   ├── run_batch.py            # High-performance batch runner
│   ├── run_single.py           # Single-question runner
│   ├── run_failure_analysis.py # Post-mortem failure analysis
│   ├── batch_runner.py         # Batch runner helper
│   └── debug_single.py         # Debug utility
│
├── data/                       # Datasets
│   ├── spider2-lite.jsonl      # Spider2-Lite benchmark (full)
│   └── spider2-lite1.jsonl     # Small subset for testing
│
├── tools/                      # One-off utilities
│   ├── clean_gold.py           # Clean gold CSV files
│   └── collect_failures.py     # Collect failed instance IDs
│
├── docs/                       # Extra documentation
│   └── arch.md                 # Architecture deep-dive notes
│
├── src/tt_sql/                 # Core package
│   ├── agents/
│   │   ├── input_layer.py          # SQLiteFileLoader, SchemaAnalyzer, TableSelector
│   │   ├── planning_layer.py       # RelationshipGraphBuilder, QueryPlanner
│   │   ├── generation_layer.py     # SQLBuilder (MultiCandidateGenerator)
│   │   ├── critic_layer.py         # SQLCritic
│   │   ├── execution_layer.py      # SQLiteExecutor
│   │   ├── loop_layer.py           # RefinementLoop orchestrator
│   │   └── failure_analysis_agent.py  # Post-mortem analysis
│   │
│   ├── core/
│   │   ├── pipeline_runner.py      # Main pipeline orchestrator
│   │   ├── orchestrator.py         # Agent sequencing engine
│   │   ├── agent_base.py           # BaseAgent class + AgentState
│   │   ├── llm_service.py          # LLM API wrapper (Bedrock/OpenAI)
│   │   ├── state.py                # Pipeline state definitions
│   │   ├── prompt_loader.py        # YAML prompt loader
│   │   ├── paths.py                # Centralized path constants
│   │   ├── logger.py               # Markdown log writer
│   │   ├── evaluator.py            # Result evaluation against gold SQL
│   │   └── metrics.py              # Pipeline metrics tracking
│   │
│   ├── prompts/                    # YAML prompt templates
│   ├── config/                     # Pipeline configuration
│   ├── rag/                        # Optional RAG / vector store
│   └── utils/                      # Shared utilities
│
├── gold/                           # Gold-standard SQL for evaluation
├── tests/                          # Unit and integration tests
└── results/                        # Output (git-ignored)
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
| TableSelector (tables + intent + complexity) | 1 |
| QueryPlanner (step-by-step plan) | 1 |
| SQLBuilder (per attempt) | 1 |
| SQLCritic (per attempt) | 1 |
| **Minimum (1 attempt)** | **4** |
| **Maximum (5 retries)** | **12** |

---

## 📄 License

This project is developed for research and educational purposes.
