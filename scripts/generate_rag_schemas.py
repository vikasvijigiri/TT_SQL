"""
generate_rag_schemas.py
────────────────────────
Pre-generates RAG schema files for every question in sample.jsonl using the
new Anchor-Driven Sliding Window VectorStoreAgent.

Output: results/{model}/schema/{instance_id}.json
        (same format that SQLBuilder / SQLCritic read at runtime)

Usage:
    python scripts/generate_rag_schemas.py
    python scripts/generate_rag_schemas.py --dataset data/sample.jsonl --model bedrock/my-model
"""
import sys
import os
import json
import argparse

# Ensure src/ is importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from dotenv import load_dotenv
load_dotenv()

from tt_sql.rag.vector_store import VectorStoreAgent
from tt_sql.core.paths import InstancePaths, initialize_directories, SPIDER_DATASET
from tt_sql.core.logger import Logger


def build_schema(retrieved_columns: list) -> dict:
    """
    Convert the flat List[Dict] from retrieve_relevant_columns() into the
    grouped schema format expected by agents:

        { "table_name": { "columns": [...], "foreign_keys": [] } }
    """
    schema = {}
    for col in retrieved_columns:
        tname = col.get("table_name", "unknown")
        if tname not in schema:
            schema[tname] = {"columns": [], "foreign_keys": []}
        schema[tname]["columns"].append({
            "column_name":   col.get("column_name", "unknown"),
            "type":          col.get("type", "unknown"),
            "description":   col.get("description", ""),
            "sample_values": col.get("sample_values") or [],
            "pk":            col.get("pk", False),
        })
    return schema


def main():
    parser = argparse.ArgumentParser(description="Pre-generate RAG schemas for all questions.")
    parser.add_argument("--dataset", type=str, default=str(SPIDER_DATASET),
                        help="JSONL file with questions (default: data/sample.jsonl)")
    parser.add_argument("--model", type=str,
                        default=os.getenv("LLM_MODEL", "bedrock/openai.gpt-oss-safeguard-120b"),
                        help="Model name (used to determine results/ subfolder)")
    args = parser.parse_args()

    Logger._verbose = True
    model_name = args.model
    initialize_directories(model_name)

    # Load questions
    questions = []
    with open(args.dataset, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    if not questions:
        print(f"No questions found in {args.dataset}")
        return

    print(f"\n{'='*60}")
    print(f"  Anchor-Driven RAG Schema Generator")
    print(f"  Dataset : {args.dataset}")
    print(f"  Model   : {model_name}")
    print(f"  Questions: {len(questions)}")
    print(f"{'='*60}\n")

    # Single VectorStoreAgent — model is cached, reused across all questions
    agent = VectorStoreAgent()

    results_summary = []

    for task in questions:
        instance_id = task.get("instance_id", "unknown")
        question = task.get("question", "")

        print(f"\n[{instance_id}] {question[:70]}...")

        try:
            retrieved_columns = agent.retrieve_relevant_columns(question)

            if not retrieved_columns:
                print(f"  ⚠️  No columns retrieved — skipping schema save.")
                results_summary.append({"instance_id": instance_id, "status": "empty", "cols": 0})
                continue

            schema = build_schema(retrieved_columns)
            total_cols = sum(len(v["columns"]) for v in schema.values())

            # Save to results/{model}/schema/{instance_id}.json
            schema_path = InstancePaths.schema(instance_id, model_name)
            os.makedirs(os.path.dirname(schema_path), exist_ok=True)
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)

            print(f"  ✅ Saved {total_cols} columns across {len(schema)} table(s) → {schema_path}")
            results_summary.append({
                "instance_id": instance_id,
                "status": "ok",
                "cols": total_cols,
                "tables": list(schema.keys()),
                "path": str(schema_path)
            })

        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results_summary.append({"instance_id": instance_id, "status": "error", "error": str(e)})

    # Summary
    print(f"\n{'='*60}")
    print(f"  Done. {len([r for r in results_summary if r['status']=='ok'])}/{len(questions)} schemas generated.")
    for r in results_summary:
        status_icon = "✅" if r["status"] == "ok" else ("⚠️" if r["status"] == "empty" else "❌")
        detail = f"{r.get('cols', 0)} cols in {r.get('tables', [])}" if r["status"] == "ok" else r.get("error", "")
        print(f"  {status_icon} [{r['instance_id']}] {detail}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
