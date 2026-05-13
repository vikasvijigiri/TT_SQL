from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
from .schema_index import SchemaIndex
from .scorer import score_column, cosine_similarity
from src.utils.logger import logger
from src.core.config import get_settings

settings = get_settings()

GENERIC_VALUES = set(settings.GENERIC_VALUES)

def is_generic(value: Any) -> bool:
    """Checks if a value is generic/weak."""
    if value is None:
        return False
    return str(value).lower().strip() in GENERIC_VALUES

def is_valid_candidate(c: dict, value: Any) -> bool:
    """Strict validation rules for grounding candidates."""
    val = c.get("value_score", 0)
    score = c.get("score", 0)
    sem = c.get("semantic_score", 0)
    conf = c.get("confidence", score)

    # Rule 1: strong value match required (unless value is generic)
    if not is_generic(value):
        if val < settings.GROUNDING_MIN_VALUE_SCORE:
            return False

    # Rule 2: avoid semantic mismatch
    if val <= settings.GROUNDING_STRONG_VALUE_SCORE and sem < settings.GROUNDING_MIN_SEMANTIC_SCORE:
        return False

    # Rule 3: minimum confidence
    if conf < settings.GROUNDING_MIN_CONFIDENCE:
        return False

    return True

def semantic_fallback(raw_field: str, index: SchemaIndex) -> dict:
    """
    Fallback mechanism when no value match is found.
    Assigns column based on pure semantic similarity with a confidence penalty.
    """
    term_vec = index.model.encode(raw_field)

    best_col = None
    best_score = -1.0
    best_table = None

    for table_col, col_info in index.column_info.items():
        col_vec = col_info["embedding"]
        score = cosine_similarity(term_vec, col_vec)

        if score > best_score:
            best_score = score
            best_col = col_info["column"]
            best_table = col_info["table"]

    return {
        "table": best_table,
        "column": best_col,
        "confidence": round(best_score * 0.4, 3), # Heavier penalty for fallback
        "fallback": True
    }

def select_best_candidate(candidates: List[dict], raw_field: str, value: Any = None) -> dict:
    """
    Global Validation Function.
    Ensures candidate validation is enforced before returning results.
    """
    if not candidates:
        return {"unresolved": True, "reason": "no candidates found"}

    # ✅ STEP 2: MODIFY FINAL SELECTION (STRICT FILTER)
    valid_candidates = [c for c in candidates if is_valid_candidate(c, value)]

    # 🧠 STEP 5: DEBUG LOG (MANDATORY)
    best_candidate = None
    if valid_candidates:
        valid_candidates.sort(key=lambda x: x["score"], reverse=True)
        # Optional quality swap for near ties
        if len(valid_candidates) > 1:
            if abs(valid_candidates[0]["score"] - valid_candidates[1]["score"]) < 0.1:
                if valid_candidates[1]["value_score"] > valid_candidates[0]["value_score"]:
                    valid_candidates[0], valid_candidates[1] = valid_candidates[1], valid_candidates[0]
        best_candidate = valid_candidates[0]

    print({
        "field": raw_field,
        "candidates": candidates,
        "valid_candidates": valid_candidates,
        "selected": best_candidate if valid_candidates else "UNRESOLVED"
    })

    # NO VALID → UNRESOLVED
    if not valid_candidates:
        return {
            "unresolved": True,
            "field": raw_field,
            "reason": "no valid candidate"
        }

    return best_candidate

class GroundingResolver:
    """
    Deterministic Value-First Grounding Resolver with Table Coherence.
    Enforces strict value matching and penalizes cross-table drift.
    """

    def __init__(self, schema: Dict[str, Dict[str, Dict[str, Any]]], llm_service: Optional[Any] = None):
        self.index = SchemaIndex(schema)
        self.llm = llm_service

    def reasoning_score(self, raw_field: str, value: Any, column: str, samples: List[Any]) -> dict:
        """
        Evaluates a column match using LLM reasoning as requested.
        """
        if not self.llm:
            return {"decision": "reject", "final_score": 0.0}

        prompt = f"""
        You are evaluating a database column match.

        Field from user query:
        "{raw_field}"

        Desired value:
        "{value}"

        Candidate column:
        "{column}"

        Sample values from this column:
        {samples[:10]}

        Evaluate:

        1. Does this column represent the SAME concept as the field?
        2. Is the value compatible with this column?
        3. Is the value informative or generic (e.g., "other")?
        4. Would this be a correct mapping in SQL?

        Output JSON:
        {{
            "relevance": 0.0 to 1.0,
            "value_match": 0.0 to 1.0,
            "is_generic_value": true/false,
            "final_score": 0.0 to 1.0,
            "decision": "accept" or "reject"
        }}
        """
        
        messages = [{"role": "user", "content": prompt}]
        res = self.llm.get_json_completion(messages, agent_name="ReasoningScorer")
        
        if not res:
            return {"decision": "reject", "final_score": 0.0}
        return res

    def consistency_score(self, table: str, selected_columns: List[str]) -> float:
        """
        Calculates consistency based on table prefix (table name in FQN).
        """
        if not selected_columns:
            return 1.0
            
        try:
            # Assuming FQN: DATABASE.SCHEMA.TABLE
            prefix = table.split(".")[2] if len(table.split(".")) > 2 else table
            matches = sum(
                1 for c in selected_columns
                if (c.split(".")[2] if len(c.split(".")) > 2 else c) == prefix
            )
            return matches / max(len(selected_columns), 1)
        except Exception:
            return 0.0

    def resolve_term(self, raw_field: str, value: Any = None, selected_columns: List[str] = None) -> dict:
        """
        Resolves a raw field and its value to a schema column using reasoning-based scoring.
        """
        # STEP 1: Pruning (Upgraded with Embedding-Based Retrieval)
        from src.schema.embedding_retriever import EmbeddingRetriever
        from src.schema.schema_graph_builder import SchemaGraphBuilder
        
        # Singleton-like access to retriever for performance
        if not hasattr(self, "retriever"):
            self.builder = SchemaGraphBuilder(self.index.schema, "IDC")
            self.builder.build_or_load()
            self.retriever = EmbeddingRetriever(self.builder, "IDC")
            
        top_nodes = self.retriever.retrieve_candidates(raw_field, value, top_k=15)
        
        # Domain-tag boost: if raw_field contains domain keywords
        domain_keywords = ["embedding", "tissue", "specimen", "pathology", "clinical", "collection"]
        if any(x in raw_field.lower() for x in domain_keywords):
            # The retriever already handles domain tags, but we ensure they are included
            pass

        heuristic_candidates = []
        for node in top_nodes:
            # Convert node back to candidate dict format
            heuristic_candidates.append({
                "table": node.table,
                "column": node.column,
                "sem_score": 0.8, # Placeholder for backward compatibility
                "samples": node.sample_values
            })

        # STEP 2: Reasoning Score (LLM-driven) - [STOPGAP] Parallelized
        import concurrent.futures
        candidates = []
        
        def score_cand(cand):
            table_dot_col = f"{cand['table']}.{cand['column']}"
            r = self.reasoning_score(raw_field, value, table_dot_col, cand["samples"])
            return (cand, r)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(score_cand, heuristic_candidates))

        for cand, r in results:
            
            if r.get("decision") == "accept":
                final_score = r.get("final_score", 0.0)
                
                # Rule 1: HARD REJECTION (value mismatch)
                if r.get("value_match", 1.0) < 0.3:
                    continue
                
                # Rule 2: GENERIC VALUE PENALTY
                if r.get("is_generic_value"):
                    final_score *= 0.6
                
                # Rule 3: EMPTY SAMPLE PENALTY
                if len(cand["samples"]) == 0:
                    final_score *= 0.5
                
                # Rule 4: CROSS-FIELD CONSISTENCY
                c_score = self.consistency_score(cand["table"], selected_columns or [])
                final_score *= (0.7 + 0.3 * c_score)
                
                # Rule 5: FINAL SELECTION RULE
                if final_score < 0.5:
                    continue

                candidates.append({
                    "table": cand["table"],
                    "column": cand["column"],
                    "confidence": final_score,
                    "reasoning": r
                })

        # STEP 3: SELECTION LOGIC
        if not candidates:
            return {"unresolved": True, "field": raw_field, "reason": "no candidates accepted by reasoning"}

        best = max(candidates, key=lambda x: x["confidence"])
        
        logger.info(f"Grounding (Reasoning): Resolved '{raw_field}' to {best['table']}.{best['column']} (conf: {best['confidence']})")

        return {
            "table": best["table"],
            "column": best["column"],
            "confidence": best["confidence"],
            "fallback": False
        }

    def resolve_intent(self, intent: dict) -> Tuple[dict, List[dict]]:
        """
        Walks the intent tree and resolves columns using strict value-aware scoring and table coherence.
        """
        mapped = []
        unresolved = []
        selected_columns = []
        selected_tables = []

        def walk(node):
            if not node:
                return

            if node.get("type") == "condition":
                raw = node.get("raw_field")
                value = node.get("value")
                if not raw:
                    return

                res = self.resolve_term(raw, value, selected_columns)
                
                if res.get("unresolved") or not res.get("column"):
                    unresolved.append(raw)
                else:
                    table = res["table"]
                    col = res["column"]
                    node["resolved_column"] = col
                    node["resolved_table"] = table
                    node["grounding_confidence"] = res["confidence"]

                    # Register table and column for coherence
                    full_col = f"{table}.{col}"
                    if full_col not in selected_columns:
                        selected_columns.append(full_col)
                    if table not in selected_tables:
                        selected_tables.append(table)

                    mapped.append({
                        "input": raw,
                        "column": f"{table}.{col}",
                        "confidence": res.get("confidence", res.get("score", 0))
                    })

            elif node.get("type") == "group":
                for c in node.get("conditions", []):
                    walk(c)

        if "filters" in intent:
            walk(intent["filters"])

        if "schema_mapping" not in intent:
            intent["schema_mapping"] = {}
            
        intent["schema_mapping"].update({
            "mapped_fields": mapped,
            "unresolved_fields": unresolved,
            "selected_tables": selected_tables
        })

        return intent, mapped
