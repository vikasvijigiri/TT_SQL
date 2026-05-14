# Semantic DIN-SQL: Deterministic, Reasoning-First Text2SQL

Semantic DIN-SQL is a high-precision, domain-agnostic Text2SQL pipeline designed for Snowflake. It replaces fragile, hardcoded heuristics with a "Reasoning-First" architecture that prioritizes data fidelity, relational depth, and automated quality validation.

## 🏗️ Core Architecture

The pipeline follows a modular, iterative flow designed to eliminate hallucinations and ensure execution success:

```mermaid
graph TD
    User([User Query]) --> Orchestrator[Semantic DIN Orchestrator]
    Orchestrator --> Engine[Governed Semantic Engine]
    Engine --> Context[(Governed Semantic Context)]
    
    Orchestrator --> Classifier[Strategic Query Classifier]
    Classifier --> Strategy{Strategy Selection}
    
    Orchestrator --> Linker[Reasoning-Based Schema Linker]
    Linker --> LinkedSchema[Linked Schema & Value Mappings]
    
    Orchestrator --> Generator[Adaptive SQL Generator]
    Generator --> SQL[Snowflake SQL]
    
    SQL --> Executor[Database Executor]
    Executor --> Results[(CSV Results)]
    
    Results --> Validator[Data IQ Auditor]
    Validator --> Feedback{Plausible?}
    
    Feedback -- No --> Corrector[Self-Correction Loop]
    Corrector --> Generator
    
    Feedback -- Yes --> Done([Final Result])
```

1.  **Governed Semantic Engine**: Automatically extracts and builds a "Semantic Context" from database metadata, including descriptions and actual data samples.
2.  **Reasoning-Based Schema Linker**:
    *   **Discrete Value Priority**: Maps terms to columns based on exact sample matches.
    *   **Relational Depth**: Automatically identifies and joins specialized metadata tables (e.g., biospecimen, classification) for complex categorical filters.
3.  **Strategic Query Classifier**: Classifies query complexity (`easy`, `non_nested_complex`, `nested_complex`) to select the optimal generation strategy.
4.  **Adaptive SQL Generator**:
    *   **Snowflake-Native**: Hardened for `VARIANT`/`JSON` handling using `LATERAL FLATTEN`.
    *   **Entity Preference**: Prioritizes "harmonized" or "canonical" name columns for reliable aggregation.
    *   **FQN Compliance**: Ensures all identifiers are fully qualified and correctly quoted.
5.  **Data IQ Layer (EDA Validation)**:
    *   **Result Plausibility**: Analyzes execution results using mini-EDA (duplicate counts, null percentages, empty-string detection).
    *   **Zero-Row Repair**: Triggers self-correction for queries that execute but return no data or nonsensical placeholders (e.g., `[]`).
6.  **Self-Correction Loop**: An iterative feedback loop that repairs both **Compilation Errors** (syntax) and **Data Quality Failures** (logic/quality).

## 🚀 Getting Started

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
Create a `.env` file at the root with your Bedrock credentials:
```env
BEDROCK_REGION=us-east-1
BEDROCK_SECRET_ACCESS_KEY=your_key
LLM_MODEL=bedrock/openai.gpt-oss-safeguard-120b
```

### Running Batch Evaluations
Run scripts from the project root using the `backend/scripts` path:
```bash
# Set PYTHONPATH to root for imports
export PYTHONPATH=$PYTHONPATH:.

# Run a single instance
python backend/scripts/run_batch.py --instance sf_bq070

# Run all instances for a specific database
python backend/scripts/run_batch.py --db IDC --workers 4
```

### Random Evaluation Framework
Verify performance parity across datasets using random sampling:
```bash
python backend/scripts/run_random_eval.py --n 5
```

## 💎 Design Philosophy: "NO Hardcoding"
Every prompt and module in this repository is strictly decoupled from domain-specific terminology. Whether processing Clinical (IDC), Intellectual Property (Patents), or Financial data, the system relies on:
- **Evidence-Based Grounding**: Using actual database samples to justify mapping.
- **Architectural Principles**: Using structural rules (e.g., "join metadata tables for categories") rather than hardcoded column lists.
- **Automated IQ**: Using the Data IQ layer to "feel" if a result is correct, mimicking human data validation.

---
*Built for high-precision Snowflake benchmarks (Spider2.0).*
