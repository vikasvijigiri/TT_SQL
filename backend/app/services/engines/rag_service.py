"""
Simple Dense RAG Pipeline:
  1. Query Embedding - Convert question to vector
  2. Dense Retrieval - Search Qdrant for top matches
  3. Result Partitioning - Split into Sets A, B, and C
"""
import json
import os
import requests
import logging
import functools
import argparse
from pathlib import Path
from dotenv import load_dotenv

import sys
sys.path.append(str(Path(__file__).resolve().parents[3]))

# TT_SQL Imports
from app.services.engines.llm_service import LLMService
from app.repositories.registry.paths import get_metadata_dir, get_model_results_dir
from app.repositories.config import settings

load_dotenv()

# --- Logging Setup ---
class ColoredFormatter(logging.Formatter):
    COLORS = {'DEBUG': '\033[94m', 'INFO': '\033[92m', 'WARNING': '\033[93m', 'ERROR': '\033[91m', 'RESET': '\033[0m'}
    def format(self, record):
        level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        log_fmt = f"%(asctime)s - {level_color}%(levelname)s{self.COLORS['RESET']} - %(message)s"
        return logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S").format(record)

def setup_logging(instance_id: str = None, logs_dir: Path = None):
    logger = logging.getLogger("rag_retrieval")
    logger.handlers = []
    
    model_name = settings.LLM_MODEL or "default"
    target_dir = logs_dir or (get_model_results_dir(model_name) / "retrievals")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = target_dir / f"{instance_id or 'global'}_retrieval.log"
    file_h = logging.FileHandler(str(log_file), encoding='utf-8')
    file_h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    stream_h = logging.StreamHandler()
    stream_h.setFormatter(ColoredFormatter())
    
    logger.setLevel(logging.INFO)
    logger.addHandler(file_h); logger.addHandler(stream_h)
    return logger

logger = logging.getLogger("rag_retrieval")

# --- Core RAG Components ---

_MODEL = None
def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _MODEL

# 1. Main Retrieval Flow
def query_qdrant(query_text, collection_name=None, instance_id=None, results_dir=None, logs_dir=None):
    if not collection_name: collection_name = settings.COLLECTION_NAME
    setup_logging(instance_id, logs_dir)
    logger.info(f"--- Simple Dense RAG Started ---")
    logger.info(f"Question: {query_text}")

    # Dense Retrieval
    try:
        model = get_model()
        vec = model.encode(query_text).tolist()
        dense_payload = {
            "vector": {"name": "text_embedding", "vector": vec},
            "limit": 36, "with_payload": True,
            "filter": {"must": [{"key": "chunk_type", "match": {"value": "column"}}]}
        }
        res = requests.post(f"{settings.QDRANT_URL.rstrip('/')}/collections/{collection_name}/points/search", 
                            headers={"api-key": settings.QDRANT_API_KEY, "Content-Type": "application/json"},
                            json=dense_payload, timeout=15).json()
        
        candidates = []
        for r in res.get("result", []):
            p = r["payload"]
            candidates.append({
                "table_name": p["table_name"],
                "column_name": p["column_name"],
                "type": p.get("type"),
                "description": p.get("description", ""),
                "score": r["score"]
            })
            
        logger.info(f"Retrieved {len(candidates)} columns.")
    except Exception as e:
        logger.error(f"Retrieval Failed: {e}")
        candidates = []

    # Partitioning
    output = {
        "question": query_text,
        "collection": collection_name,
        "final_sets": {
            "Set A": candidates[:12],
            "Set B": candidates[12:24],
            "Set C": candidates[24:36]
        },
        "retrieved_columns": [f"{c['table_name']}.{c['column_name']}" for c in candidates[:15]],
        "count": len(candidates)
    }

    if instance_id:
        model_name = settings.LLM_MODEL or "default"
        out_root = Path(results_dir or get_model_results_dir(model_name)) / "retrievals"
        out_root.mkdir(parents=True, exist_ok=True)
        out_path = out_root / f"{instance_id}.json"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)
        logger.info(f"Results saved to: {out_path}")

    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", type=str, required=True)
    parser.add_argument("--instance-id", type=str)
    args = parser.parse_args()
    query_qdrant(args.question, instance_id=args.instance_id)
