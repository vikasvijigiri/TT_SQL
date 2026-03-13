"""
Full RAG Pipeline (New Architecture):
  1. Schema Metadata       â€” Enriched JSON in root metadata/
  2. Chunking              â€” table-level + column-level Qdrant vectors
  3. Embeddings            â€” sentence-transformers (local)
  4. Vector Database       â€” Qdrant Cloud
  5. Intent Extraction     â€” rule-based (extract_intent)
  6. Column-First Retrieval â€” Retrieves global column candidates
  7. Table Resolution      â€” Resolves tables from columns
  8. Join Path Discovery   â€” Heuristic discovery of potential joins
  9. Self-Healing          â€” Missing bridge table detection via LLM
  10. Multi-Set Synthesis  â€” 3 alternative sets + Variants
"""
import json
import os
import re
import string
import requests
import logging
from pathlib import Path
import argparse
import functools
import time
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from dataclasses import dataclass, field

import sys
sys.path.append(str(Path(__file__).resolve().parents[3]))

from pydantic import BaseModel, Field

# TT_SQL Imports
from app.services.engines.llm_service import LLMService
from app.repositories.registry.paths import PROJECT_ROOT, METADATA_DIR, get_results_base_dir, REPO_DIR, InstancePaths
from app.services.utils.logger import Logger
from app.repositories.config import settings
from app.repositories.connectors.rag_repo import (
    raw_socket_request
)

# Default logs directory is now managed dynamically via setup_logging

load_dotenv()

@dataclass
class IntentResult:
    keywords: List[str] = field(default_factory=list)
    explicit_tables: List[str] = field(default_factory=list)
    expanded_query: str = ""

# --- Hybrid RAG Components ---

# --- Logging Setup ---
logger = logging.getLogger(__name__)

class ColoredFormatter(logging.Formatter):
    """Custom formatter to add ANSI colors to terminal logs."""
    COLORS = {
        'DEBUG': '\033[94m',    # blue
        'INFO': '\033[92m',     # green
        'WARNING': '\033[93m',  # yellow
        'ERROR': '\033[91m',    # red
        'CRITICAL': '\033[95m', # magenta
        'RESET': '\033[0m'
    }

    def format(self, record):
        level_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        log_fmt = f"%(asctime)s - {level_color}%(levelname)s{reset} - %(message)s"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

@functools.lru_cache(maxsize=4)
def _load_metadata(metadata_path: Path):
    """Cached loading of the large schema metadata JSON."""
    with open(metadata_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def setup_logging(collection_name: str = None, instance_id: str = None, logs_dir: Path = None, model_name: str = None):
    """Dynamically set up logging to {model_results}/retrievals/{instance_id}_retrieval_process.log"""
    # Use a named logger to avoid hijacking the root logger unnecessarily
    logger = logging.getLogger("rag_retrieval")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    # Resolve base directory for retrievals
    from app.repositories.registry.paths import get_model_results_dir
    m_name = model_name or settings.LLM_MODEL or "default_model"
    base_retrieval_dir = get_model_results_dir(m_name) / "retrievals"
    
    prefix = instance_id if instance_id else collection_name
    log_name = f"{prefix}_retrieval_process.log" if prefix else "retrieval_process.log"
    
    # Ensure directory exists
    target_dir = logs_dir if logs_dir else base_retrieval_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = target_dir / log_name
    
    file_handler = logging.FileHandler(str(log_file), encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt="%Y-%m-%d %H:%M:%S"))
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(ColoredFormatter())
    
    logger.setLevel(logging.INFO)
    logger.addHandler(stream_handler)
    return logger

logger = logging.getLogger("rag_retrieval")

_MODEL = None
def get_model():
    """Lazy load the sentence-transformers model."""
    global _MODEL
    if _MODEL is None:
        model_name = settings.EMBEDDING_MODEL
        Logger.log(f"Loading local embedding model: {model_name}...", level="INFO")
        try:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer(model_name)
        except ImportError:
            raise ImportError("Please install sentence-transformers: pip install sentence-transformers")
    return _MODEL

_LLM = None
def _get_llm():
    """Get the centralized LLMService."""
    global _LLM
    if _LLM is None:
        _LLM = LLMService()
    return _LLM

# B5: Cache SparseRanker per collection so BM25 corpus is built only once
_SPARSE_RANKER_CACHE: dict = {}

def _get_sparse_ranker(metadata: dict, collection_name: str) -> "SparseRanker":
    """Returns a cached SparseRanker for the given collection, building once."""
    if collection_name not in _SPARSE_RANKER_CACHE:
        _SPARSE_RANKER_CACHE[collection_name] = SparseRanker(metadata)
    return _SPARSE_RANKER_CACHE[collection_name]


def _robust_json_extract(text: str) -> dict:
    """Extract JSON from text even if it's wrapped in Markdown or noisy."""
    if not text:
        return {}
    try:
        trimmed = text.strip()
        trimmed = re.sub(r'^```json\s*|\s*```$', '', trimmed, flags=re.IGNORECASE).strip()
        return json.loads(trimmed)
    except Exception:
        start = text.find('{')
        if start != -1:
            end = text.rfind('}')
            if end != -1:
                try:
                    return json.loads(text[start:end+1])
                except Exception:
                    pass
            candidate = text[start:]
            candidate = re.sub(r'[^}\]"0-9a-zA-Z._ \-,]+$', '', candidate)
            for suffix in ["}", '"}', '"]}', '"}]}']:
                try:
                    return json.loads(candidate + suffix)
                except Exception:
                    continue
    return {}

def consolidated_retrieval_expert(question, column_candidates, metadata, top_tables=[]):
    """
    ONE LLM call to handle: Intent, Anchors, and 3-Set Synthesis.
    """
    llm = _get_llm()
    if not llm:
        return [], {"Set A": column_candidates[:10]}

    top_tables_str = ", ".join(top_tables) if top_tables else "None identified"
    cand_list = []
    for c in column_candidates[:50]:
        d = c.get('description', '')
        # Simple local sanitization to avoid importing re if not needed, 
        # but re is already used in this file for json extraction.
        d_clean = re.sub(r'\s+', ' ', d).strip()
        cand_list.append(f"- {c['table_name']}.{c['column_name']} (Type: {c['type']}, Desc: {d_clean})")
    cand_list_str = "\n".join(cand_list)
    
    from app.services.schemas.agent_state import AgentState
    from app.services.utils.prompt_loader import PromptLoader
    loader = PromptLoader()
    try:
        messages = loader.load_prompt("expert_retrieval", question=question, cand_list=cand_list_str, top_tables=top_tables_str)
        resp = llm.get_completion(messages)
        raw = _robust_json_extract(resp)
        final_sets = {}
        
        # Map back to full column objects
        all_pool = {f"{c['table_name']}.{c['column_name']}".lower(): c for c in column_candidates}
        # Also add ALL columns from metadata as a fallback if LLM invents a column name
        tables_meta = metadata.get("tables", {})
        
        for s_name, cols_str in raw.get("sets", {}).items():
            names = [n.strip().lower() for n in cols_str.split(",") if "." in n]
            current_set = []
            seen = set()
            for n in names:
                if n in seen: continue
                if n in all_pool:
                    current_set.append(all_pool[n])
                else:
                    # Fallback lookup in full metadata
                    t, c = n.split(".", 1)
                    if t in tables_meta:
                        for col_obj in tables_meta[t].get("columns", []):
                            if col_obj["column_name"].lower() == c:
                                current_set.append({
                                    "table_name": t, "column_name": col_obj["column_name"],
                                    "type": col_obj["type"], "description": col_obj.get("description", "")
                                })
                seen.add(n)
            final_sets[s_name] = current_set
        return raw.get("anchors", []), final_sets
    except Exception as e:
        Logger.log(f"Expert Retrieval Adaptation: {str(e)}", level="WARNING")
        return [], {"Set A": column_candidates[:10]}

def get_global_candidates(query_text, collection_name, qdrant_url, qdrant_api, metadata, limit=40):
    """
    ARCHITECTURE: Parallel Retrieval -> RRF Fusion -> Diversity Sampling
    1. Table Discovery (Dense)
    2. Hybrid Column Search (Dense + Sparse/BM25)
    3. RRF Result Fusion
    4. Per-Table Targeted Sampling & PK Injection
    """
    from app.services.utils.logger import Logger
    model = get_model()
    query_vector = model.encode(query_text).tolist()
    headers = {"api-key": qdrant_api, "Content-Type": "application/json"}
    base_url = f"{qdrant_url.rstrip('/')}/collections/{collection_name}/points/search"

    candidates = []
    seen_keys = set()
    top_tables = []
    
    candidate_logic_start = time.time()
    
    # ---------------------------------------------------------
    # Parallel Stage: Table & Column Discovery
    # ---------------------------------------------------------
    def fetch_tables():
        table_payload = {
            "vector": {"name": "text_embedding", "vector": query_vector},
            "limit": 5,
            "with_payload": True,
            "filter": {"must": [{"key": "chunk_type", "match": {"value": "table"}}]}
        }
        try:
            resp = requests.post(base_url, headers=headers, json=table_payload, timeout=15)
            resp.raise_for_status()
            return [r.get("payload", {}).get("table_name") for r in resp.json().get("result", []) if r.get("payload", {}).get("table_name")]
        except Exception as e:
            Logger.log(f"Table Discovery Thread Failure: {str(e)}", level="DEBUG")
            return []

    def fetch_dense_columns():
        column_payload = {
            "vector": {"name": "text_embedding", "vector": query_vector},
            "limit": 30,
            "with_payload": True,
            "filter": {"must": [{"key": "chunk_type", "match": {"value": "column"}}]}
        }
        try:
            resp = requests.post(base_url, headers=headers, json=column_payload, timeout=15)
            resp.raise_for_status()
            results = []
            for r in resp.json().get("result", []):
                p = r.get("payload", {})
                key = f"{p['table_name']}.{p['column_name']}".lower()
                results.append({"key": key, "payload": p})
            return results
        except Exception as e:
            Logger.log(f"Dense Column Thread Failure: {str(e)}", level="DEBUG")
            return []

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_tables = executor.submit(fetch_tables)
        future_dense = executor.submit(fetch_dense_columns)
        
        top_tables = future_tables.result()
        dense_results = future_dense.result()

    # Rely only on Dense retrieval (Remove Fusion)
    # dense_results is list of {"key": key, "payload": p}
    candidates_pool = dense_results
    pass

    # ---------------------------------------------------------
    # 3. ASSEMBLY: Candidate Pool Construction
    # ---------------------------------------------------------
    
    # Map for easy lookup of full objects
    obj_pool = {res["key"]: res["payload"] for res in dense_results}
    
    # For sparse candidates not in dense results, we need to fetch from metadata
    meta_tables = metadata.get("tables", {})

    for res in dense_results[:limit]:
        p = res["payload"]
        tname = p["table_name"]
        cname = p["column_name"]
        key = f"{tname}.{cname}".lower()
        if key in seen_keys: continue
        
        # Enrichment: Fallback to metadata for description if missing in payload
        desc = p.get("description", "")
        if not desc and tname in meta_tables:
            for col_obj in meta_tables[tname].get("columns", []):
                if col_obj["column_name"].lower() == cname.lower():
                    desc = col_obj.get("description", "")
                    break

        candidates.append({
            "table_name": tname, "column_name": cname,
            "type": p.get("type"), "description": desc,
            "sample_values": p.get("sample_values", [])
        })
        seen_keys.add(key)

    # ---------------------------------------------------------
    # 4. BATCHED STAGE: Per-Table Targeted Retrieval (Top 5 columns) [R2]
    # ---------------------------------------------------------
    if top_tables:
        table_col_payload = {
            "vector": {"name": "text_embedding", "vector": query_vector},
            "limit": 5 * len(top_tables), # Bulk limit
            "with_payload": True,
            "filter": {"must": [
                {"key": "chunk_type", "match": {"value": "column"}},
                {"key": "table_name", "match": {"any": list(top_tables)}}
            ]}
        }
        try:
            resp = requests.post(base_url, headers=headers, json=table_col_payload, timeout=30)
            if resp.status_code == 200:
                for r in resp.json().get("result", []):
                    p = r.get("payload", {})
                    tname = p.get("table_name")
                    cname = p.get("column_name")
                    key = f"{tname}.{cname}".lower()
                    if key not in seen_keys:
                        candidates.append({
                            "table_name": tname, "column_name": cname,
                            "type": p.get("type"), "description": p.get("description", ""),
                            "sample_values": p.get("sample_values", [])
                        })
                        seen_keys.add(key)
        except Exception:
            pass


    # 5. FINAL STAGE: Inject PKs for the discovery tables
    # This addresses the issue where otif dominated the top 40 results
    tables_meta = metadata.get("tables", {})
    for tname in top_tables:
        if tname in tables_meta:
            for col_obj in tables_meta[tname].get("columns", []):
                if col_obj.get("pk") or any(k in col_obj["column_name"].lower() for k in ["id", "key", "no", "number", "code"]):
                    key = f"{tname}.{col_obj['column_name']}".lower()
                    if key not in seen_keys:
                        # Append the PK as a candidate
                        candidates.append({
                            "table_name": tname,
                            "column_name": col_obj["column_name"],
                            "type": col_obj["type"],
                            "description": col_obj.get("description", "") + " (INJECTED JOIN KEY)",
                            "sample_values": col_obj.get("sample_values", [])
                        })
                        seen_keys.add(key)
                        pass

    Logger.log(f"Final pool: {len(candidates)} candidates ({len(top_tables)} discovery tables).")
    pass
    return top_tables, candidates

def query_qdrant(query_text, top_k=10, top_n_tables=3, collection_name=None, instance_id=None, results_dir=None, logs_dir=None, metadata_dir=None, model_name=None, turbo=False):
    if not collection_name: collection_name = settings.COLLECTION_NAME
    
    # Use model-specific logs if possible
    if not logs_dir and model_name:
        from app.repositories.registry.paths import get_model_results_dir
        logs_dir = get_model_results_dir(model_name) / "log"
    
    setup_logging(collection_name, instance_id, logs_dir=logs_dir)
    qdrant_url, qdrant_api = settings.QDRANT_URL, settings.QDRANT_API_KEY
    
    m_dir = Path(metadata_dir or METADATA_DIR)
    metadata_path = m_dir / f"{collection_name}.json"
    if not metadata_path.exists(): 
        metadata_path = m_dir / "metadata_injestion_files.json"
    
    # R4: Use cached metadata loader
    metadata = _load_metadata(metadata_path)

    
    logger.info(f"--- Starting {'Turbo ' if turbo else ''}Optimized Retrieval for: '{query_text}' ---")
    
    # 1. Global Multi-Stage Search (Stage 1-4) - Table + Column Sampling + PK Injection
    top_tables, all_candidates = get_global_candidates(query_text, collection_name, qdrant_url, qdrant_api, metadata, limit=40)
    
    if turbo:
        # Bypassing slow LLM Expert synthesis for instant retrieval
        Logger.log("Turbo Mode: Bypassing LLM Expert Synthesis.", level="INFO")
        anchors = [] # No anchors in turbo mode yet
        # Simple synthesis: Set A = top 15, Set B = next 15, Set C = rest
        final_sets = {
            "Set A": all_candidates[:15],
            "Set B": all_candidates[15:30],
            "Set C": all_candidates[30:40]
        }
    else:
        # 2. Consolidated Expert LLM Call - Diversity-aware decision making
        anchors, final_sets = consolidated_retrieval_expert(query_text, all_candidates, metadata, top_tables=top_tables)
    
    output = {
        "question": query_text,
        "anchors": anchors,
        "final_sets": final_sets,
        "top_3_sets": {k: v for i, (k, v) in enumerate(final_sets.items()) if i < 3},
        "retrieved_columns": [c['column_name'] for c in final_sets.get("Set A", [])]
    }
    
    if instance_id:
        # Avoid storage directory - use results_dir or fall back to model-specific results
        if not results_dir and model_name:
            from app.repositories.registry.paths import get_model_results_dir
            results_dir = get_model_results_dir(model_name)
        
        # If still no results_dir, use the central one provided by paths
        from app.repositories.registry.paths import get_results_base_dir
        out_root = Path(results_dir or get_results_base_dir())
        out_dir = out_root / "retrievals"
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / f"{instance_id}.json", 'w', encoding='utf-8') as f: json.dump(output, f, indent=2)
        
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--question", type=str)
    parser.add_argument("--instance-id", type=str)
    parser.add_argument("--collection-name", type=str, default=settings.COLLECTION_NAME, help=f"Qdrant collection name (default: {settings.COLLECTION_NAME})")
    args = parser.parse_args()
    query_qdrant(args.question, collection_name=args.collection_name, instance_id=args.instance_id)
