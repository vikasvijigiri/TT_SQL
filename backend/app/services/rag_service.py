"""
Full RAG Pipeline:
  1. Schema Metadata       — metadata_injestion_files.json
  2. Chunking              — table-level + column-level Qdrant vectors
  3. Embeddings            — sentence-transformers/all-MiniLM-L6-v2 (cloud inference)
  4. Vector Database       — Qdrant Cloud
  5. Synonym Expansion     — synonyms.json (expand_query)
  6. Intent Extraction     — rule-based (extract_intent)             [NEW]
  7. Table Retrieval       — Stage 1 (table + query_pattern chunks)
  8. Column Retrieval      — Stage 2 (column chunks filtered by table)
  9. Schema Pruning        — keyword-overlap scoring (prune_schema)  [NEW]
"""
import json
import os
import re
import string
import requests
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import sys
sys.path.append(str(Path(__file__).resolve().parents[3]))

# TT_SQL Imports
from app.services.llm_service import LLMService
from app.repositories.paths import get_metadata_dir, get_model_results_dir, get_active_project_slug
from app.core.settings import settings

# load_dotenv() - Removed to fulfill "NO .env" requirement

# --- Logging Setup ---
class ColoredFormatter(logging.Formatter):
    COLORS = {'DEBUG': '\033[94m', 'INFO': '\033[92m', 'WARNING': '\033[93m', 'ERROR': '\033[91m', 'RESET': '\033[0m'}
    def format(self, record):
        level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        log_fmt = f"%(asctime)s - {level_color}%(levelname)s{self.COLORS['RESET']} - %(message)s"
        return logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S").format(record)

def setup_logging(instance_id: str = None, logs_dir: Path = None, user_slug: str = None):
    logger = logging.getLogger("rag_retrieval")
    if logger.handlers:
        return logger
    
    from app.repositories.paths import get_active_project_slug
    project_slug = get_active_project_slug(user_slug=user_slug)
    target_dir = logs_dir or struct.get_logs_dir(user_slug, project_slug)
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

from app.utils.prompt_loader import PromptLoader

# --- Core RAG Components ---

_MODEL = None
_PROMPT_LOADER = PromptLoader()

def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _MODEL

def _extract_anchors(query_text: str, llm: LLMService) -> List[str]:
    """Uses LLM to identify core entities (anchors) from the question."""
    messages = _PROMPT_LOADER.load_prompt("rag_refinement", sub_key="extract_anchors", question=query_text)
    res = llm.get_completion(messages, agent_name="RAG_Anchor_Extractor")
    try:
        # Simple extraction from JSON-like output
        match = re.search(r'\[.*\]', res.replace('\n', ''), re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return []

def _check_sufficiency(query_text: str, anchors: List[str], retrieved_cols: List[Dict], llm: LLMService) -> Dict:
    """Uses LLM to check if the retrieved context is sufficient."""
    context_str = "\n".join([f"{c['table_name']}.{c['column_name']}" for c in retrieved_cols])
    messages = _PROMPT_LOADER.load_prompt(
        "rag_refinement", 
        sub_key="check_sufficiency", 
        question=query_text, 
        anchors=", ".join(anchors),
        retrieved_context=context_str
    )
    res = llm.get_completion(messages, agent_name="RAG_Sufficiency_Checker")
    try:
        match = re.search(r'\{.*\}', res.replace('\n', ' '), re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass
    return {"sufficient": False, "reasoning": "Failed to parse sufficiency check."}

# 1. Main Retrieval Flow
def query_qdrant(query_text, collection_name=None, instance_id=None, results_dir=None, logs_dir=None, metadata_dir=None, user_slug=None, qdrant_url=None, qdrant_api_key=None):
    """
    Executes an Anchor-Driven Iterative RAG retrieval.
    Returns: Dict with top_3_sets (table -> [columns])
    """
    if not collection_name: raise ValueError("collection_name is required for RAG retrieval")
    if not qdrant_url: qdrant_url = settings.QDRANT_URL
    if not qdrant_api_key: qdrant_api_key = settings.QDRANT_API_KEY
    setup_logging(instance_id, logs_dir, user_slug=user_slug)
    logger.info(f"--- ⚓ Anchor-Driven Iterative Retrieval Started ---")
    logger.info(f"Question: {query_text}")

    llm = LLMService()
    anchors = _extract_anchors(query_text, llm)
    logger.info(f"📍 Extracted Anchors: {anchors}")

    all_candidates = []    
    seen_cols = set()
    window_size = 25
    
    model = get_model()
    query_vector = model.encode(query_text).tolist()

    logger.info(f"🔍 Multi-Stage Retrieval: Stage 1 (Table Discovery)")
    
    top_tables = []
    try:
        # 1. Discover Top Tables
        table_payload = {
            "vector": {"name": "text_embedding", "vector": query_vector},
            "limit": 5,
            "with_payload": True,
            "filter": {"must": [{"key": "chunk_type", "match": {"value": "table"}}]}
        }
        t_res = requests.post(f"{qdrant_url.rstrip('/')}/collections/{collection_name}/points/search", 
                             headers={"api-key": qdrant_api_key, "Content-Type": "application/json"},
                             json=table_payload, timeout=10).json()
        top_tables = [r["payload"]["table_name"] for r in t_res.get("result", [])]
        logger.info(f"Top 5 Candidate Tables: {top_tables}")
    except Exception as e:
        logger.warning(f"Table Discovery failed, falling back: {e}")

    logger.info(f"🔍 Multi-Stage Retrieval: Stage 2 (Column Scanning)")
    
    all_candidates = []
    try:
        # 2. Scan Columns
        column_payload = {
            "vector": {"name": "text_embedding", "vector": query_vector},
            "limit": 30,
            "with_payload": True,
            "filter": {"must": [{"key": "chunk_type", "match": {"value": "column"}}]}
        }
        c_res = requests.post(f"{qdrant_url.rstrip('/')}/collections/{collection_name}/points/search", 
                             headers={"api-key": qdrant_api_key, "Content-Type": "application/json"},
                             json=column_payload, timeout=10).json()
        
        column_candidates = []
        for r in c_res.get("result", []):
            p = r["payload"]
            column_candidates.append({
                "table_name": p["table_name"],
                "column_name": p["column_name"],
                "score": r["score"]
            })
        
        # 3. Rerank and Post-Process
        def rerank(candidates, table_anchors, query_anchors):
            scored = []
            for c in candidates:
                s = c["score"]
                t = c["table_name"].lower()
                col = c["column_name"].lower()
                
                # Table context boost
                if t in [ta.lower() for ta in table_anchors]:
                    s += 0.2
                
                # Anchor keyword boost
                for qa in query_anchors:
                    qa_low = qa.lower()
                    if qa_low in col or qa_low in t:
                        s += 0.3
                        break
                c["rerank_score"] = s
                scored.append(c)
            scored.sort(key=lambda x: x["rerank_score"], reverse=True)
            return scored[:15] # Return top 15 high-confidence hits

        all_candidates = rerank(column_candidates, top_tables, anchors)
        logger.info(f"Refined {len(all_candidates)} schema candidates after reranking.")

        # Single-pass sufficiency check
        check = _check_sufficiency(query_text, anchors, all_candidates, llm)
        is_sufficient = check.get("sufficient", False)
        logger.info(f"Sufficiency Check: {is_sufficient} | Reasoning: {check.get('reasoning')}")
        
        if not is_sufficient:
            logger.info("⚠️ Context is partially sufficient. Proceeding with best-available candidates.")

    except Exception as e:
        logger.error(f"RAG multi-stage retrieval failed: {e}")
        is_sufficient = False

    def partition_to_sets(cols):
        sets = {"Set A": {}, "Set B": {}, "Set C": {}}
        # Set A: Top 1/3
        chunk = len(cols) // 3 if len(cols) > 9 else 4
        for c in cols[:chunk]:
            t, col = c["table_name"], c["column_name"]
            if t not in sets["Set A"]: sets["Set A"][t] = []
            sets["Set A"][t].append(col)
        
        # Set B: Next 1/3
        for c in cols[chunk:chunk*2]:
            t, col = c["table_name"], c["column_name"]
            if t not in sets["Set B"]: sets["Set B"][t] = []
            sets["Set B"][t].append(col)

        # Set C: Last 1/3
        for c in cols[chunk*2:chunk*3 if chunk*3 < len(cols) else len(cols)]:
            t, col = c["table_name"], c["column_name"]
            if t not in sets["Set C"]: sets["Set C"][t] = []
            sets["Set C"][t].append(col)
            
        return sets

    top_sets = partition_to_sets(all_candidates)

    # Resolve metadata path with correct project slug
    project_slug = get_active_project_slug(user_slug=user_slug)
    output = {
        "question": query_text,
        "collection": collection_name,
        "anchors": anchors,
        "top_3_sets": top_sets,
        "final_sets": top_sets,
        "metadata_path": str(get_metadata_dir(user_slug, project_slug) / f"{collection_name}.json"),
        "count": len(all_candidates),
        "iterations": 1,
        "sufficient": is_sufficient
    }

    # Post-retrieval cleanup: NO CACHE (Strictly removed JSON storage)
    return output

    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", type=str, required=True)
    parser.add_argument("--instance-id", type=str)
    args = parser.parse_args()
    query_qdrant(args.question, instance_id=args.instance_id)
