import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from src.utils.logger import logger

@dataclass
class ScoredCandidate:
    column: str
    relevance: float
    value_match: float
    final_score: float
    decision: str
    reason: str

class ReasoningScorer:
    """
    Upgraded ReasoningScorer agent with BATCH and PARALLEL scoring capabilities.
    """
    
    def __init__(self, llm, max_concurrent: int = 5):
        self.llm = llm
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.metrics = {
            "fields_total": 0,
            "fields_resolved": 0,
            "total_llm_calls": 0,
            "wall_time_ms": 0
        }

    async def score_field_batch(self, raw_field: str, value: Any, candidates: List[Any]) -> List[Dict[str, Any]]:
        """
        Scores ALL candidates for ONE field in a single LLM call.
        """
        if not candidates:
            return []

        async with self.semaphore:
            candidates_json = []
            for c in candidates:
                # Handle both ColumnNode and dict for backward compatibility
                col_path = c.full_path if hasattr(c, "full_path") else c.get("full_path", str(c))
                samples = c.sample_values if hasattr(c, "sample_values") else c.get("samples", [])
                candidates_json.append({
                    "column": col_path,
                    "samples": samples[:5]
                })

            prompt = f"""
            You are scoring column candidates for a Text2SQL grounding task.
            
            Field from user query: "{raw_field}"
            Target value: "{value}"
            
            Rate each candidate column below. For each, output a JSON object with:
            - column: the full column path
            - relevance: 0.0-1.0 (does this column represent the same concept?)
            - value_match: 0.0-1.0 (is the value compatible with this column's data/samples?)
            - final_score: 0.0-1.0 (overall match quality)
            - decision: "accept" | "reject"
            - reason: one sentence
            
            Candidates:
            {candidates_json}
            
            Output ONLY a JSON array. No preamble.
            """
            
            self.metrics["total_llm_calls"] += 1
            messages = [{"role": "user", "content": prompt}]
            
            # Use LLM with retry logic
            try:
                res = await self._get_llm_json_with_retry(messages)
                return res if isinstance(res, list) else []
            except Exception as e:
                logger.error(f"ReasoningScorer failed for field {raw_field}: {e}")
                return []

    async def _get_llm_json_with_retry(self, messages: List[Dict[str, str]]) -> Any:
        """Retrieves JSON from LLM with max 2 retries if invalid."""
        attempts = 0
        while attempts < 3:
            try:
                return self.llm.get_json_completion(messages, agent_name="ReasoningScorer")
            except Exception as e:
                attempts += 1
                if attempts == 3: raise e
                logger.warning(f"Retry {attempts}/2 for ReasoningScorer JSON...")
                messages = messages + [{"role": "user", "content": "The last output was invalid JSON. Please return ONLY a valid JSON array."}]
        return []

    async def score_intent(self, intent: Dict[str, Any], field_candidates: Dict[str, List[Any]]) -> Dict[str, Any]:
        """
        Scores all fields in the intent in parallel.
        """
        start_time = time.time()
        tasks = []
        fields = []
        
        for field, candidates in field_candidates.items():
            value = self._get_field_value(intent, field)
            tasks.append(self.score_field_batch(field, value, candidates))
            fields.append(field)
            
        self.metrics["fields_total"] = len(fields)
        results = await asyncio.gather(*tasks)
        
        # Process results
        intent["schema_mapping"] = intent.get("schema_mapping", {})
        mapped = []
        unresolved = []
        
        for i, field_results in enumerate(results):
            raw_field = fields[i]
            if not field_results:
                unresolved.append(raw_field)
                continue
                
            # Filter accepted candidates
            valid = [r for r in field_results if r.get("decision") == "accept"]
            if not valid:
                unresolved.append(raw_field)
                continue
                
            # Pick best
            best = max(valid, key=lambda x: x.get("final_score", 0.0))
            score = best.get("final_score", 0.0)
            
            if score >= 0.7:
                status = "RESOLVED"
                self.metrics["fields_resolved"] += 1
            elif score >= 0.5:
                status = "LOW_CONFIDENCE"
                self.metrics["fields_resolved"] += 1 # Still counted as resolved but flagged
            else:
                unresolved.append(raw_field)
                continue
                
            mapped.append({
                "input": raw_field,
                "column": best["column"],
                "confidence": score,
                "status": status,
                "reasoning": best
            })
            
        intent["schema_mapping"]["mapped_fields"] = mapped
        intent["schema_mapping"]["unresolved_fields"] = unresolved
        
        if unresolved:
            intent["ambiguity"] = intent.get("ambiguity", {})
            intent["ambiguity"]["present"] = True
            intent["ambiguity"]["fields"] = unresolved
            if len(unresolved) > 2:
                intent["needs_clarification"] = True
                
        self.metrics["wall_time_ms"] = int((time.time() - start_time) * 1000)
        self._log_metrics()
        
        return intent

    def _get_field_value(self, intent: Dict[str, Any], field: str) -> Any:
        """Helper to find the value associated with a field in the intent."""
        # Simple walk for now, can be optimized
        def walk(node):
            if node.get("type") == "condition" and node.get("raw_field") == field:
                return node.get("value")
            if node.get("type") == "group":
                for c in node.get("conditions", []):
                    v = walk(c)
                    if v is not None: return v
            return None
        return walk(intent.get("filters", {}))

    def _log_metrics(self):
        logger.info(f"ReasoningScorer Metrics: {self.metrics}")
