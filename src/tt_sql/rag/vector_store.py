import os
import sys
import json
import requests
import re
import string
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path

try:
    from langchain_aws import ChatBedrockConverse
    from langchain_core.messages import HumanMessage
except ImportError:
    pass

try:
    from ..core.logger import Logger
except ImportError:
    # Handle direct execution
    project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from src.tt_sql.core.logger import Logger

# --- Intent Extraction Rules ---
_OPERATION_PATTERNS = {
    "rank":      ["highest", "lowest", "top", "bottom", "rank", "most", "least", "best", "worst"],
    "filter":    ["failed", "not", "missing", "without", "exclude", "where", "which"],
    "aggregate": ["total", "sum", "average", "count", "how many", "overall", "monthly"],
    "lookup":    ["what is", "show", "list", "find", "get", "retrieve"],
}

@dataclass
class IntentResult:
    keywords: List[str] = field(default_factory=list)
    operation: str = "lookup"
    explicit_tables: List[str] = field(default_factory=list)
    explicit_columns: List[str] = field(default_factory=list)
    expanded_query: str = ""

def extract_intent(question: str, metadata: dict) -> IntentResult:
    q_lower = question.lower()
    tokens = q_lower.translate(str.maketrans('', '', string.punctuation)).split()

    all_table_names = list(metadata.get("tables", {}).keys())
    all_col_names = [
        c.get("column_name", "").lower()
        for t in metadata.get("tables", {}).values()
        for c in t.get("columns", [])
    ]
    
    keywords = [t for t in tokens if t in all_table_names or t in all_col_names or len(t) > 4]
    stop = {"which", "what", "where", "that", "have", "been", "with", "this", "from", "their", "they"}
    keywords = [k for k in keywords if k not in stop]

    operation = "lookup"
    for op, signals in _OPERATION_PATTERNS.items():
        if any(sig in q_lower for sig in signals):
            operation = op
            break

    explicit_tables = [t for t in all_table_names if t in tokens or t in q_lower]
    explicit_columns = [c for c in all_col_names if c.replace("_", " ") in q_lower or c in q_lower]
    
    return IntentResult(list(set(keywords)), operation, explicit_tables, explicit_columns, question)

def resolve_domain(intent: IntentResult, domain_map: Dict[str, List[str]]) -> List[str]:
    allowed_tables = []
    for domain, tables in domain_map.items():
        if domain.lower() in intent.keywords or any(t.lower() in intent.keywords for t in tables):
            allowed_tables.extend(tables)
    
    if intent.explicit_tables:
        allowed_tables.extend(intent.explicit_tables)
        
    return list(set(allowed_tables)) if allowed_tables else []

def filter_by_score_dropoff(items, score_key="score", threshold=0.03, min_keep=1):
    if not items: return []
    sorted_items = sorted(items, key=lambda x: x.get(score_key, 0), reverse=True)
    filtered = [sorted_items[0]]
    prev_gap = 0.0
    
    for i in range(1, len(sorted_items)):
        prev_val = sorted_items[i-1].get(score_key, 0)
        curr_val = sorted_items[i].get(score_key, 0)
        current_gap = prev_val - curr_val
        is_large_jump = (current_gap > threshold) and (current_gap > (prev_gap * 1.5))
        
        if i >= min_keep and is_large_jump:
            Logger.log(f"    [Drop-off] Truncated at index {i}. Gap: {current_gap:.4f}")
            break
            
        filtered.append(sorted_items[i])
        prev_gap = current_gap
    return filtered


class VectorStoreAgent:
    """
    Agent responsible for an Anchor-Driven Sliding Window RAG Retrieval.
    Uses Bedrock to evaluate schema sets and identify the key anchors.
    """
    # Class-level cache for heavy resources
    _MODEL_CACHE = None
    _CLIENT_CACHE = {}  # URL -> Client
    _LLM_CACHE = None

    def __init__(self, collection_override: Optional[str] = None):
        self.url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = os.getenv("QDRANT_API_KEY") or os.getenv("QDRANT_API")
        self.collection_name = collection_override or os.getenv("QDRANT_COLLECTION")
        if not self.collection_name:
            Logger.log("QDRANT_COLLECTION not set in .env — VectorStoreAgent will be disabled.", level="ERROR")
        
        self.vector_size = 768
        self.model = None

        # Load Metadata for expansions
        self.metadata = self._load_json_resource("metadata_injestion_files.json")
        self.domain_map = self._load_json_resource("domain_map.json")

        # Load Embedding Model
        try:
            if VectorStoreAgent._MODEL_CACHE is None:
                from sentence_transformers import SentenceTransformer
                embed_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
                Logger.log(f"Loading SentenceTransformer model ('{embed_model}')...")
                VectorStoreAgent._MODEL_CACHE = SentenceTransformer(embed_model)
            self.model = VectorStoreAgent._MODEL_CACHE
        except ImportError:
            Logger.log("Missing dependency: pip install sentence-transformers", level="ERROR")
        except Exception as e:
            Logger.log(f"Failed to load embedding model: {e}", level="ERROR")

    def _ensure_collection(self):
        """No-op: collections are managed during ingestion, not at query time."""
        pass

    # --- Utils ---
    def _load_json_resource(self, filename: str) -> dict:
        path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', filename)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                Logger.log(f"Failed to load {filename}: {e}", level="WARN")
        return {}

    def _get_llm(self):
        if VectorStoreAgent._LLM_CACHE is None:
            try:
                model_id = os.getenv("LLM_MODEL", "amazon.titan-text-lite-v1").replace("bedrock/", "")
                API_KEY = os.getenv("BEDROCK_SECRET_ACCESS_KEY")
                region = os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "us-east-1"
                VectorStoreAgent._LLM_CACHE = ChatBedrockConverse(
                    model_id=model_id,
                    region_name=region,
                    default_headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else None,
                    max_tokens=500,
                    temperature=0.0,
                )
            except Exception as e:
                Logger.log(f"Failed to initialize Bedrock LLM: {e}", level="WARN")
        return VectorStoreAgent._LLM_CACHE

    def _extract_llm_text(self, resp) -> str:
        if not resp: return ""
        if hasattr(resp, 'content'):
            if isinstance(resp.content, str):
                return resp.content
            elif isinstance(resp.content, list):
                text = ""
                for segment in resp.content:
                    if isinstance(segment, dict) and "text" in segment:
                        text += segment["text"]
                    elif isinstance(segment, str):
                        text += segment
                return text
            return str(resp.content)
        return str(resp)

    # --- HTTP Helper (matches manual_https_post in reference script) ---
    def _qdrant_post(self, path: str, payload: dict) -> dict:
        full_url = self.url.rstrip('/') + path
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        try:
            response = requests.post(full_url, headers=headers, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    # --- Stage 1 & 2 Qdrant queries (HTTP REST, matching reference script) ---
    def stage1_get_tables(self, query_text: str, top_n_tables: int) -> List[str]:
        query_vector = self.model.encode(query_text).tolist()
        payload = {
            "query": query_vector,
            "using": "text_embedding",
            "limit": 10,
            "with_payload": True,
            "filter": {
                "must": [{"key": "chunk_type", "match": {"value": "table"}}]
            }
        }
        results = self._qdrant_post(f"/collections/{self.collection_name}/points/query", payload)
        
        if "error" in results or results.get("status") == "error":
            Logger.log(f"[Stage1] Qdrant query failed: {results}", level="ERROR")
            return []
        
        pts = results.get("result", {}).get("points", []) if isinstance(results.get("result"), dict) else results.get("result", [])
        
        Logger.log(f"  > Stage 1: Scoring {len(pts)} table chunks...")
        scored_tables = []
        seen = set()
        for res in pts:
            tname = res.get("payload", {}).get("table_name")
            score = res.get("score", 0)
            if tname and tname not in seen:
                scored_tables.append({"table_name": tname, "score": score})
                seen.add(tname)
                
        scored_tables = filter_by_score_dropoff(scored_tables, score_key="score", threshold=0.03, min_keep=1)
        top = [t["table_name"] for t in scored_tables][:top_n_tables]
        for t in scored_tables[:top_n_tables]:
            Logger.log(f"    - {t['table_name']}: {t['score']:.4f}")
        return top

    def stage2_get_columns(self, query_text: str, top_tables: List[str], top_k: int, offset: int = 0) -> List[Dict]:
        query_vector = self.model.encode(query_text).tolist()
        all_col_pts = []
        
        if not top_tables:
            # Fallback: search all columns without table filter
            payload = {
                "query": query_vector,
                "using": "text_embedding",
                "limit": top_k,
                "offset": offset,
                "with_payload": True,
                "filter": {"must": [{"key": "chunk_type", "match": {"value": "column"}}]}
            }
            results = self._qdrant_post(f"/collections/{self.collection_name}/points/query", payload)
            if "error" in results or results.get("status") == "error":
                Logger.log(f"[Stage2] Fallback query failed: {results}", level="ERROR")
            else:
                pts = results.get("result", {}).get("points", []) if isinstance(results.get("result"), dict) else results.get("result", [])
                all_col_pts.extend(pts)
        else:
            for table_name in top_tables:
                payload = {
                    "query": query_vector,
                    "using": "text_embedding",
                    "limit": top_k,
                    "offset": offset,
                    "with_payload": True,
                    "filter": {
                        "must": [
                            {"key": "chunk_type", "match": {"value": "column"}},
                            {"key": "table_name", "match": {"value": table_name}}
                        ]
                    }
                }
                results = self._qdrant_post(f"/collections/{self.collection_name}/points/query", payload)
                if "error" in results or results.get("status") == "error":
                    Logger.log(f"[Stage2] Query failed for '{table_name}': {results}", level="ERROR")
                else:
                    pts = results.get("result", {}).get("points", []) if isinstance(results.get("result"), dict) else results.get("result", [])
                    all_col_pts.extend(pts)
                    Logger.log(f"    [Stage2] offset={offset}: {len(pts)} cols in '{table_name}'")
        return all_col_pts

    # --- LLM Components ---
    def get_llm_anchor_columns(self, question: str, candidates: List[Dict]) -> List[str]:
        llm = self._get_llm()
        if not llm: return []
        
        cand_list = "\n".join([f"- {c.get('table_name')}.{c.get('column_name')} (Type: {c.get('type')})" for c in candidates])
        prompt = (
            f"User Question: {question}\n\n"
            f"Candidate Columns from Vector Search:\n{cand_list}\n\n"
            f"Identify the 'anchor' columns that are primary filters or metrics or date or etc for this question. "
            f"You MUST select at least ONE column that is most relevant. "
            f"Return ONLY a comma-separated list of table.column names. Do not include any other text.\n"
        )
        try:
            resp = llm.invoke([HumanMessage(content=prompt)])
            text = self._extract_llm_text(resp).strip()
            return [a.strip() for a in text.split(",") if "." in a]
        except Exception as e:
            Logger.log(f"Anchor selection failed: {e}", level="WARN")
            return []

    def expand_with_siblings(self, anchor_identifiers: List[str]) -> List[Dict]:
        if not anchor_identifiers or not self.metadata: return []
        table_names = {ident.split(".")[0] for ident in anchor_identifiers if "." in ident}
        expanded_set = []
        tables_meta = self.metadata.get("tables", {})
        
        for t_name in table_names:
            if t_name in tables_meta:
                for col in tables_meta[t_name].get("columns", []):
                    expanded_set.append({
                        "table_name": t_name,
                        "column_name": col.get("column_name"),
                        "type": col.get("type"),
                        "description": col.get("description", ""),
                        "sample_values": col.get("sample_values", [])
                    })
        return expanded_set

    def finalize_columns_with_llm_multi(self, question: str, expanded_pool: List[Dict], anchor_names: List[str]) -> Dict[str, List[Dict]]:
        llm = self._get_llm()
        normalized_anchors = [a.strip().lower() for a in anchor_names if "." in a]
        
        # Fallback if no LLM
        if not llm:
            return {"Set A": [c for c in expanded_pool if f"{c.get('table_name')}.{c.get('column_name')}".lower() in normalized_anchors]}
        
        pool_list = "\n".join([f"- {c.get('table_name')}.{c.get('column_name')} (Type: {c.get('type')})" for c in expanded_pool])
        prompt = (
            f"User Question: {question}\n\n"
            f"MANDATORY Anchor Columns (must be in all sets):\n{', '.join(anchor_names)}\n\n"
            f"Pool of Potential Columns (including siblings):\n{pool_list}\n\n"
            f"Provide 3 DIFFERENT sets of columns to answer the question. "
            f"Each set MUST include the MANDATORY anchor columns. "
            f"Set A: Optimal. Set B/C: Alternatives.\n"
            f"Return ONLY a JSON object: {{\"Set A\": \"table.col1, table.col2\", \"Set B\": \"...\", \"Set C\": \"...\"}}"
        )
        try:
            resp = llm.invoke([HumanMessage(content=prompt)])
            text = self._extract_llm_text(resp).strip()
            text = re.sub(r'^```json\s*|\s*```$', '', text, flags=re.IGNORECASE).strip()
            raw_sets = json.loads(text)
            
            final_results = {}
            for set_name, names_str in raw_sets.items():
                selected_names = [a.strip().lower() for a in names_str.split(",") if "." in a]
                combined_target_names = list(set(selected_names + normalized_anchors))
                
                current_set = []
                seen_ident = set()
                for c in expanded_pool:
                    ident = f"{c.get('table_name')}.{c.get('column_name')}".lower()
                    if ident in combined_target_names and ident not in seen_ident:
                        current_set.append(c)
                        seen_ident.add(ident)
                
                if not current_set:
                    for c in expanded_pool:
                        ident = f"{c.get('table_name')}.{c.get('column_name')}".lower()
                        if ident in normalized_anchors and ident not in seen_ident:
                            current_set.append(c)
                            seen_ident.add(ident)
                final_results[set_name] = current_set
            return final_results
        except Exception as e:
            Logger.log(f"Final multi-set refinement failed: {e}", level="WARN")
            return {"Set A": [c for c in expanded_pool if f"{c.get('table_name')}.{c.get('column_name')}".lower() in normalized_anchors]}

    def check_schema_sufficiency(self, question: str, current_candidates: List[Dict]) -> bool:
        llm = self._get_llm()
        if not llm: return True
        
        cand_list = "\n".join([f"- {c.get('table_name')}.{c.get('column_name')}" for c in current_candidates])
        prompt = (
            f"User Question: {question}\n\n"
            f"Current Schema Context:\n{cand_list}\n\n"
            f"Is this schema context sufficient to write a SQL query to answer the user question? "
            f"Consider if essential metrics, dimensions, and filters are present. "
            f"Return ONLY 'YES' or 'NO'."
        )
        try:
            resp = llm.invoke([HumanMessage(content=prompt)])
            text = self._extract_llm_text(resp).strip().upper()
            return "YES" in text
        except Exception as e:
            Logger.log(f"Sufficiency check failed: {e}", level="WARN")
            return True

    def retrieve_relevant_columns(self, query: str, limit: int = 3) -> List[Dict]:
        """
        Anchor-Driven RAG retrieval using Sliding Windows.
        Returns Set A (Optimal Columns) back to the system.
        """
        if not self.collection_name or not self.model:
            return []
            
        try:
            Logger.log(f"[RAG] Querying with sliding window anchors: '{query[:50]}'")
            
            # Step 1: Detect intent and narrow scope
            if self.metadata and self.domain_map:
                intent = extract_intent(query, self.metadata)
                resolve_domain(intent, self.domain_map)
                
            # Stage 1: Get top Tables
            Logger.log(f"  > Stage 1: Retrieving relevant tables...")
            top_tables = self.stage1_get_tables(query, top_n_tables=3)
            
            # Stage 2: Initial Pool & Anchors
            Logger.log(f"  > Stage 2: Fetching candidate columns and identifying anchors...")
            window_size = 10
            all_candidates = []
            pts = self.stage2_get_columns(query, top_tables, window_size, offset=0)
            
            for res in pts:
                cand = res.get("payload", {})
                cand["score"] = res.get("score", 0)
                all_candidates.append(cand)
            
            anchors = self.get_llm_anchor_columns(query, all_candidates)
            if not anchors and all_candidates:
                top_cand = all_candidates[0]
                anchors = [f"{top_cand.get('table_name')}.{top_cand.get('column_name')}"]
                
            Logger.log(f"  > Final Anchors: {anchors}")

            # Stage 3: Sliding Windows
            max_windows = 4
            for w in range(1, max_windows):
                is_sufficient = self.check_schema_sufficiency(query, all_candidates)
                if is_sufficient:
                    Logger.log(f"  > Stage 3: LLM confirmed schema context is SUFFICIENT. (Window {w})")
                    break
                else:
                    Logger.log(f"  > Stage 3: Schema context NOT sufficient, sliding window... (Window {w})")
                
                offset = w * window_size
                pts = self.stage2_get_columns(query, top_tables, window_size, offset=offset)
                new_cands = []
                for res in pts:
                    cand = res.get("payload", {})
                    cand["score"] = res.get("score", 0)
                    new_cands.append(cand)
                    
                filtered_cands = filter_by_score_dropoff(new_cands, score_key="score", threshold=0.04, min_keep=2)
                for cand in filtered_cands:
                    all_candidates.append(cand)
            
            # Stage 4: Expansion & Synthesis (Requires metadata)
            if self.metadata:
                Logger.log(f"  > Stage 4: Sibling Expansion for Anchors...")
                expanded_pool = self.expand_with_siblings(anchors)
                
                Logger.log(f"  > Stage 4: Synthesizing multiple query sets via LLM...")
                final_multi_sets = self.finalize_columns_with_llm_multi(query, expanded_pool, anchors)
                
                # 'Set A' is the optimal set 
                final_set = final_multi_sets.get("Set A", [])
            else:
                # Graceful fallback: Just return the raw deduplicated RAG set if no metadata
                final_set = all_candidates
                
            # Deduplicate final output to prevent errors in Input Layer (grouping by table/col)
            dedup_set = []
            seen = set()
            for col in final_set:
                key = (col.get('table_name'), col.get('column_name'))
                if key not in seen:
                    dedup_set.append(col)
                    seen.add(key)
                    
            Logger.log(f"[RAG] Pipeline Complete. Returning {len(dedup_set)} refined columns.")
            return dedup_set

        except Exception as e:
            Logger.log(f"Anchor-Driven RAG failed: {e}", level="ERROR")
            return []

if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path
    
    # Add project root to sys.path so relative imports (like ..core.logger) work 
    project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    # We still need to configure the module structure properly if it's executed as __main__
    # So we'll run it as a module instead of a script if we hit this locally.
    # Actually, simpler: replace the relative import if run directly:
    try:
        from src.tt_sql.core.logger import Logger
        from src.tt_sql.rag.vector_store import VectorStoreAgent
    except ImportError:
        pass
    parser = argparse.ArgumentParser(description="Test RAG Vector Store independently.")
    parser.add_argument("--question", type=str, default="What is the overall OTIF performance for this month?", help="Query to test against Qdrant.")
    parser.add_argument("--limit", type=int, default=3, help="Top K results per data type.")
    
    # Load .env to ensure credentials and collections are correctly populated
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
        
    default_collection = os.getenv("QDRANT_COLLECTION", "acme-chatbot")
    parser.add_argument("--collection", type=str, default=default_collection, help=f"Qdrant collection to query against (default: {default_collection}).")
    args = parser.parse_args()
    
    # Initialize the Logger for console output
    Logger._verbose = True
    
    print(f"\n[Test] Querying VectorStore Agent...")
    print(f"[Test] Question: '{args.question}'")
    print(f"[Test] Collection: {args.collection}, Limit per type: {args.limit}\n")
    
    agent = VectorStoreAgent(collection_override=args.collection)
    results = agent.retrieve_relevant_columns(args.question, limit=args.limit)
    
    print("\n--- RETRIEVED COLUMNS ---")
    if not results:
        print("No results returned.")
    else:
        for idx, col in enumerate(results, 1):
            print(f"{idx}. {col.get('table_name', '??')}.{col.get('column_name', '??')} "
                  f"({col.get('type', '??')}) "
                  f"- Score: {col.get('score', 0):.4f}")
            if "sample_values" in col:
                print(f"   Samples: {col['sample_values']}")
            print()
    print("--- DONE ---")