# 🤖 nQuire: Turbo-Accelerated Text-to-SQL Engine

nQuire is a premium, high-performance Text-to-SQL engine designed for the modern enterprise. It strictly follows a domain-driven **Controller-Service-Repository** pattern with **Strict Directory Segregation** (no mixed files and folders).

---

## 🏛️ Layered Architecture Mapping

- **🎮 Controller Layer (`app/controllers/`)**: API and CLI entry points.
    - Specialized controllers for queries and health checks.
- **🧠 Service Layer (`app/services/`)**: Core Business Logic and Intelligence.
    - **Engines (`app/services/engines/`)**: RAG, SQL, and Pipeline execution logic.
    - **Schemas (`app/services/schemas/`)**: Runtime state and data schemas.
    - **Agents (`app/services/agents/`)**: Specialized AI agent layers.
    - **Utils (`app/services/utils/`)**: Logging, Prompts, and health service.
- **🗄️ Repository Layer (`app/repositories/`)**: Data Management and Infrastructure.
    - **Persistence (`app/repositories/persistence/`)**: File coordination and orchestration state.
    - **Connectors (`app/repositories/connectors/`)**: Database and Vector Store drivers.
    - **Registry (`app/repositories/registry/`)**: Path resolution logic.
    - **Config (`app/repositories/config/`)**: Static YAML and JSON configurations.

---

## 🏗️ Project Structure

```text
backend/
├── app/
│   ├── controllers/            # Layer 1: Entry Points
│   ├── services/               # Layer 2: Business Logic
│   │   ├── engines/            # Processing Engines (RAG, SQL)
│   │   ├── schemas/            # State & Data Schemas
│   │   ├── agents/             # AI Agent Layers
│   │   └── utils/              # Shared Helpers (Prompts, Logging)
│   └── repositories/           # Layer 3: Data & Config
│       ├── persistence/        # File Management
│       ├── connectors/         # DB & Vector Drivers
│       ├── registry/           # Path Management
│       └── config/             # YAML/JSON Configs
├── scripts/                    # CLI Orchestration & Flow Scripts
├── tests/                      # Logic & Retrieval Verification
└── .env                        # Environment Setup
```

---

## 🚀 Execution Pipelines

### 🚀 Automated Workflows

#### Phase 1: Knowledge Preparation
Extracts schema, enriches with AI descriptions, and ingests into Qdrant.
```bash
python scripts/prep_knowledge.py
```

#### Phase 2: RAG Analysis Execution
Runs the natural language to SQL pipeline for a specific instance.
```bash
python scripts/run_rag_analysis.py --instance-id q011
```

### 3. Single Question Testing
```bash
python scripts/run_single.py --question "Show me total revenue" --use-rag
```

### 4. Batch Evaluation
```bash
python scripts/run_batch_rag.py --workers 5
```

---

## 🧪 Testing

```bash
# Run RAG Retrieval Test
python tests/test_rag.py --id q011 --turbo
```

---

## 🚀 Launching the API

```bash
python -m app.controllers.main
```

---

## 🔍 Troubleshooting & Logs

- **Results Hub**: `app/repositories/data/results/<model_name>/`
- **Metadata Cache**: `app/repositories/data/metadata_extracts/`
- **SQL Snippets**: `app/repositories/data/results/<model_name>/sql/`

---

## 📄 License
Internal proprietary engine. All rights reserved.
