from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from .scorer_v2 import combined_score, normalize, value_score
from src.schema.schema_enricher import enrich_schema_for_candidates, IMPORTANT_COLUMNS
from src.utils.logger import logger

class GroundingResolverV2:
    """
    Value-Aware Grounding Resolver (V2) with Hybrid Discovery and Strict Value-First Logic.
    """

    def __init__(self, schema: Dict[str, Dict[str, Any]], db_executor=None, db_name: str = "", indexer=None):
        self.schema = schema
        self.db_executor = db_executor
        self.db_name = db_name
        self.indexer = indexer
        self.model = SentenceTransformer("all-MiniLM-L6-v2")
        self.columns = []
        self.meta = {}

        # Pre-calculate embeddings for all columns (once)
        col_names = []
        for table, cols in schema.items():
            for col in cols.keys():
                self.columns.append((table, col))
                col_names.append(normalize(col))
        
        print(f"Grounding V2: Encoding {len(col_names)} columns...")
        embeddings = self.model.encode(col_names, show_progress_bar=False)
        
        for i, (table, col) in enumerate(self.columns):
            self.meta[f"{table}.{col}"] = {
                "embedding": embeddings[i]
            }

    def resolve_one(self, raw_field: str, value: Any) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Resolves a field using Hybrid Discovery and Value-First ranking."""
        from rapidfuzz import fuzz
        raw_norm = normalize(raw_field)
        term_vec = self.model.encode(raw_norm)
        
        # --- PASS 1: Hybrid Discovery ---
        discovery_pool = {} # (table, col) -> semantic_score
        
        # 1. Semantic Search
        semantic_scores = []
        for table, col in self.columns:
            col_vec = self.meta[f"{table}.{col}"]["embedding"]
            norm_term = np.linalg.norm(term_vec)
            norm_col = np.linalg.norm(col_vec)
            semantic = float(np.dot(term_vec, col_vec) / (norm_term * norm_col)) if norm_term > 0 and norm_col > 0 else 0.0
            semantic_scores.append((table, col, semantic))
            
        semantic_scores.sort(key=lambda x: x[2], reverse=True)
        for t, c, s in semantic_scores[:20]:
            discovery_pool[(t, c)] = s
            
        # 2. Value-Index Search (If indexer available)
        if self.indexer:
            # Search using both raw_field and the value itself if it's a string
            search_query = raw_field
            if value and isinstance(value, str):
                search_query += f" {value}"
            
            value_hits = self.indexer.search(search_query, top_k=15)
            for col_obj, index_score in value_hits:
                key = (col_obj.table, col_obj.column)
                if key not in discovery_pool:
                    # Give it a baseline semantic score for discovery
                    discovery_pool[key] = 0.5 
                else:
                    # Boost existing candidates found in index
                    discovery_pool[key] += 0.1
        
        top_discoveries = [(t, c, s) for (t, c), s in discovery_pool.items()]
        top_discoveries.sort(key=lambda x: x[2], reverse=True)
        top_discoveries = top_discoveries[:25] # Slightly larger final pool
        
        # --- PASS 2: Targeted Enrichment ---
        if self.db_executor:
            enrich_schema_for_candidates(
                self.db_executor, 
                self.schema, 
                self.db_name, 
                [(t, c) for t, c, _ in top_discoveries]
            )
            
        # --- PASS 3: Hard Value Filter ---
        valid_candidates = []
        for table, col, semantic_val in top_discoveries:
            samples = self.schema[table][col].get("sample_values", [])
            val_score_val = value_score(value, samples)
            
            if val_score_val > 0:
                valid_candidates.append({
                    "table": table, 
                    "column": col, 
                    "semantic_discovery": semantic_val, 
                    "value_score": val_score_val
                })

        debug_candidates = []
        used_fallback = False

        if valid_candidates:
            for cand in valid_candidates:
                table, col = cand["table"], cand["column"]
                samples = self.schema[table][col].get("sample_values", [])
                col_vec = self.meta[f"{table}.{col}"]["embedding"]
                
                score, semantic, fuzzy, val = combined_score(
                    raw_norm, value, normalize(col), term_vec, col_vec, samples
                )
                
                debug_candidates.append({
                    "table": table, 
                    "column": col, 
                    "semantic": float(semantic),
                    "fuzzy": float(fuzzy), 
                    "value": float(val), 
                    "final_score": float(score)
                })
        else:
            used_fallback = True
            for table, col, semantic_val in top_discoveries:
                fuzzy = fuzz.token_sort_ratio(raw_norm, normalize(col)) / 100
                score = semantic_val + fuzzy
                
                debug_candidates.append({
                    "table": table, 
                    "column": col, 
                    "semantic": float(semantic_val),
                    "fuzzy": float(fuzzy), 
                    "value": 0.0, 
                    "final_score": float(score)
                })
        
        debug_candidates.sort(key=lambda x: x["final_score"], reverse=True)
        
        # Disambiguation Logic
        if len(debug_candidates) >= 2:
            t1, t2 = debug_candidates[0], debug_candidates[1]
            if abs(t1["final_score"] - t2["final_score"]) < 0.15: # Slightly wider window
                # 1. Prefer higher value score
                if t2["value"] > t1["value"]:
                    debug_candidates[0], debug_candidates[1] = debug_candidates[1], debug_candidates[0]
                # 2. Prefer IMPORTANT_COLUMNS if value scores are equal
                elif t2["value"] == t1["value"] and t2["value"] > 0:
                    t2_is_important = any(k in t2["column"].lower() for k in IMPORTANT_COLUMNS)
                    t1_is_important = any(k in t1["column"].lower() for k in IMPORTANT_COLUMNS)
                    if t2_is_important and not t1_is_important:
                        debug_candidates[0], debug_candidates[1] = debug_candidates[1], debug_candidates[0]

        best = debug_candidates[0] if debug_candidates else None
        
        if best:
            score = best["final_score"]
            confidence = round(score, 3)
            if score < 0.7:
                confidence *= 0.8
            best["final_score"] = min(1.0, float(confidence))

        topk = debug_candidates[:5]
        threshold = 0.6 if used_fallback else 0.4
        
        if not best or best["final_score"] < threshold:
             return None, topk
             
        return best, topk

    def resolve_intent(self, intent: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Grounds intent using value-first signals and structured diagnostics."""
        mapped_mappings = []
        unresolved = []
        all_debug = []

        filters = intent.get("filters") or {}
        conditions = filters.get("conditions", []) if isinstance(filters, dict) else getattr(filters, 'conditions', [])

        for cond in conditions:
            is_dict = isinstance(cond, dict)
            raw_field = (cond.get("raw_field") if is_dict else getattr(cond, 'raw_field', '')) or ""
            value = cond.get("value") if is_dict else getattr(cond, 'value', None)
            
            best, topk = self.resolve_one(raw_field, value)

            all_debug.append({
                "raw_field": raw_field,
                "value": value,
                "candidates": topk
            })

            if best:
                table = best["table"]
                col = best["column"]
                score = best["final_score"]
                
                if is_dict:
                    cond["resolved_column"] = col
                    cond["resolved_table"] = table
                else:
                    cond.resolved_column = col
                    cond.resolved_table = table

                mapped_mappings.append({
                    "input": raw_field,
                    "column": f"{table}.{col}",
                    "confidence": float(score)
                })
            else:
                unresolved.append(raw_field)

        print("\n--- GROUNDING DEBUG (HYBRID DISCOVERY) ---")
        for d in all_debug:
            print(f"Raw Field: {d['raw_field']} (Value: {d['value']})")
            for c in d["candidates"][:3]:
                print(f"  -> {c['table']}.{c['column']} | Score: {c['final_score']:.3f} (V: {c['value']:.2f}, S: {c['semantic']:.2f}, F: {c['fuzzy']:.2f})")
        print("------------------------------------------\n")

        intent["schema_mapping"] = {
            "mapped_fields": mapped_mappings,
            "unresolved_fields": unresolved
        }
        intent["debug_candidates"] = all_debug

        return intent, mapped_mappings
