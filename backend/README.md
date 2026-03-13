# 🤖 nQuire: Turbo-Accelerated Text-to-SQL Engine

nQuire is a premium, high-performance Text-to-SQL engine designed for the modern enterprise. It strictly follows a layered architecture (Controller-Service-Repository) encapsulated within the `app/` directory.

---

## 🏛️ Layered Architecture Mapping

- **🎮 Controller Layer (`app/controllers/`)**: API handling logic. Manages HTTP requests/responses.
- **🧠 Service Layer (`app/services/`)**: Business logic. Orchestrates agents and pipelines.
- **🗄️ Repository Layer (`app/repos/`)**: Data management.
    - **Fundamental Logic**: Core data access (`sql_repo.py`, `rag_repo.py`).
    - **Data Hub (`app/repos/data/`)**: All metadata, results, and gold datasets.
    - **Execution Hub (`app/repos/scripts/`)**: All pipeline runs and batch scripts.
    - **Test Hub (`app/repos/tests/`)**: All validation and unit tests.

---

## 🏗️ Project Structure

```text
backend/
├── app/
│   ├── main.py             # FastAPI Entry Point
│   ├── controllers/        # Layer 1: API Handling
│   ├── services/           # Layer 2: Business Logic
│   ├── repos/              # Layer 3: Repository & Orchestration
│   │   ├── data/           # Metadata, Results, Gold
│   │   ├── scripts/        # Primary Execution Pipelines (Runs)
│   │   ├── tests/          # Validation & Unit Tests
│   │   └── tools/          # Maintenance Utilities
│   └── models/             # Layer 4: Config & Paths
└── .env                    # Environment Setup
```

---

## 🚀 Execution Pipelines

### 0. Master Automated Flow (Recommended)
### 🚀 Automated Workflows

The system is designed with a two-phase architecture for production readiness:

#### Phase 1: Knowledge Preparation
Extracts schema from RDS, enriches it with LLM descriptions, and ingests it into the vector store.
```bash
python app/repos/scripts/prep_knowledge.py --schema acme-chatbot --collection acme_chatbot
```
*   **Flags**:
    *   `--no-enrich`: Skip LLM description step.
    *   `--overwrite`: Force extraction even if cache exists.

#### Phase 2: RAG Analysis Execution
Runs the actual natural language to SQL pipeline using the prepared knowledge.
```bash
python app/repos/scripts/run_rag_analysis.py --instance-id q001 --db acme-chatbot
```
*   **Result Tracking**: Results are automatically saved with sequential IDs (e.g., `q035`) in `app/repos/data/results/`.

### 3. Single Question Testing
Execute the Text-to-SQL pipeline for a one-off question.

**Command:**
```bash
# Must provide --db (schema) and --question
python app/repos/scripts/run_single.py --question "Show me total revenue for 2024" --db acme-chatbot --use-rag
```

### 4. Batch Evaluation
Processes multiple questions in parallel using the default input defined in `.env`.

**Command:**
```bash
python app/repos/scripts/run_batch_rag.py --workers 5
```

---

## 🧪 Testing

All specialized tests are located in `app/repos/tests`.

**Run RAG Retrieval Test:**
Verifies that the semantic retrieval correctly identifies relevant tables and columns.

```bash
python app/repos/tests/test_rag.py --input-jsonl app/repos/data/input_queries/sample.jsonl --id q001
```

---

## 🚀 Launching the API

Start the FastAPI server for production-ready integration.

```bash
python -m app.main
```

---

## 🔍 Troubleshooting & Logs

If a process feels "stuck," it is likely the LLM enrichment or RAG retrieval processing a large schema.

- **Master Flow Metadata**: `app/repos/data/metadata_extracts/`
- **Execution Logs**: `app/repos/data/results/<model_name>/log/`
- **SQL Outputs**: `app/repos/data/results/<model_name>/sql/`
- **Data Results (CSV)**: `app/repos/data/results/<model_name>/csv/`

> [!TIP]
> **Performance**: The flow automatically skips extraction if the metadata file exists in `metadata_extracts/`. Use `--overwrite` to force a refresh.
> Use the `--no-enrich` flag for much faster extraction if AI-generated column descriptions aren't required.

---

## 📄 License
Internal proprietary engine. All rights reserved.
