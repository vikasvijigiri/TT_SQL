# nQuire CLI Documentation

This guide provides detailed instructions and examples for running the Text-to-SQL pipeline components using the Command Line Interface (CLI).

## Prerequisites

Ensure you are in the `backend/` directory and your virtual environment is activated.

```bash
cd backend
# Activate your venv, e.g.:
# .\venv\Scripts\activate
```

Ensure your `.env` file is configured with the necessary LLM and Qdrant credentials.

---

## 1. Knowledge Preparation (Setup)

Before running queries that use RAG (Retrieval Augmented Generation), you must ingest your database schema into the vector store.

### Full Preparation Pipeline
This script runs extraction, LLM-based metadata enrichment, and Qdrant ingestion in one go.

```bash
python -m scripts.prep_knowledge
```

**Options:**
- `--no-enrich`: Skip the LLM-based description enrichment (faster, but less accurate retrieval).
- `--overwrite`: Force re-extraction even if metadata exists.

---

## 2. Running a Single Query

Use `scripts/run_single.py` to process a specific question.

### Basic Query (Direct Input)
```bash
python -m scripts.run_single --question "How many batches had OTIF issues last month?" --use-rag
```

### Running by Instance ID
If you have a JSONL dataset, you can run a specific task by its ID.
```bash
python -m scripts.run_single --id q001 --dataset app/repositories/data/input_queries/sample.jsonl --use-rag
```

**Key Arguments:**
- `--question`: The text of your natural language question.
- `--use-rag`: Enables schema retrieval from Qdrant.
- `--model`: (Optional) Override the default model (e.g., `openai.gpt-4o`).
- `--quiet`: Minimal output to terminal.

---

## 3. Batch Processing

Use `scripts/run_batch.py` to process multiple questions from a JSONL file in parallel.

### Run Entire Dataset
```bash
python -m scripts.run_batch --dataset app/repositories/data/input_queries/sample.jsonl --workers 4 --use-rag
```

### Run Specific IDs in Batch
```bash
python -m scripts.run_batch --ids q001,q002,q005 --use-rag
```

**Key Arguments:**
- `--dataset`: Path to the JSONL file containing tasks.
- `--workers`: Number of parallel threads (default: 4).
- `--limit`: Limit the number of tasks to process (e.g., `--limit 10`).
- `--overwrite`: Re-run tasks even if a result file already exists.
- `--verbose`: Enable detailed log output for each task.

---

## 4. Evaluation (Advanced)

To evaluate the performance of your results against "gold" (ground truth) SQL, use the evaluation script.

```bash
python -m scripts.evaluate --model YourModelName
```

---

## Troubleshooting

- **Encoding Issues**: If you see strange characters on Windows, the scripts automatically attempt to set the terminal to UTF-8.
- **Connection Errors**: Ensure your `QDRANT_URL` and `QDRANT_API` are correct in `.env`.
- **Module Not Found**: Always run scripts from the `backend/` root using `python -m scripts.script_name`.
