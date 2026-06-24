import json
import math
import re
from pathlib import Path
from typing import List, Dict, Any
from agent.app.core.config import MEMORY_DIR
from agent.app.utils.logger import logger
from agent.app.core.observability.retrieval_analytics import record_retrieval

class DynamicRAGService:
    """
    World-Class SOTA: Zero-dependency BM25 Dynamic Few-Shot Retriever.
    Stores and retrieves past successful (Query -> SQL) pairs to inject into prompts.
    """
    def __init__(self):
        self.memory_file = MEMORY_DIR / "few_shot_memory.json"
        self.documents: List[Dict[str, Any]] = []
        self.doc_tokens: List[List[str]] = []
        self.idf: Dict[str, float] = {}
        self.avg_dl: float = 0.0
        self._load_memory()

    def _tokenize(self, text: str) -> List[str]:
        # Simple alphanumeric tokenization
        return [w for w in re.split(r'\W+', text.lower()) if w]

    def _load_memory(self):
        if not self.memory_file.exists():
            # Initialize with an empty structure if it doesn't exist
            self.memory_file.parent.mkdir(parents=True, exist_ok=True)
            self.memory_file.write_text('[]', encoding='utf-8')
            return

        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                self.documents = json.load(f)
            
            if not self.documents:
                return

            self.doc_tokens = [self._tokenize(doc['query']) for doc in self.documents]
            self.avg_dl = sum(len(t) for t in self.doc_tokens) / len(self.documents)

            # Compute IDF
            df: Dict[str, int] = {}
            for tokens in self.doc_tokens:
                for token in set(tokens):
                    df[token] = df.get(token, 0) + 1
            
            N = len(self.documents)
            for token, freq in df.items():
                self.idf[token] = math.log(1 + (N - freq + 0.5) / (freq + 0.5))

        except Exception as e:
            logger.warning(f"[RAGService] Failed to load memory: {e}")

    @staticmethod
    def _is_valid_sql(text: str) -> bool:
        """Return True only if text looks like a real SQL query, not a plain-text answer."""
        SQL_KEYWORDS = ("select", "with", "show", "explain", "pragma", "describe", "insert", "update", "delete")
        return text.strip().lower().startswith(SQL_KEYWORDS)

    def save_success(self, query: str, sql: str, db_name: str):
        """Called after a successful query execution to build the RAG memory.
        Only SQL queries are stored — plain-text answers are never saved so that
        the few-shot context never leaks actual answer values to the LLM."""
        if not self._is_valid_sql(sql):
            logger.warning(
                "[RAGService] save_success called with non-SQL text — skipping to prevent answer leakage."
            )
            return
        try:
            # Check if exactly identical query exists to avoid bloat
            if any(doc['query'] == query for doc in self.documents):
                return

            new_entry = {"query": query, "sql": sql, "db_name": db_name}
            self.documents.append(new_entry)
            
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.documents, f, indent=2)
                
            self._load_memory() # Recompute BM25 weights
            logger.info(f"[RAGService] Saved successful query to Few-Shot memory.")
        except Exception as e:
            logger.warning(f"[RAGService] Failed to save to memory: {e}")

    def retrieve_few_shot(self, query: str, db_name: str, top_k: int = 3) -> str:
        """Scores the memory bank via BM25 and returns the top K formatted examples."""
        if not self.documents:
            return ""

        query_tokens = self._tokenize(query)
        scores = []
        k1 = 1.5
        b = 0.75

        for idx, doc_tokens in enumerate(self.doc_tokens):
            score = 0.0
            doc_len = len(doc_tokens)
            # Exact database match gets a massive boost
            db_boost = 2.0 if self.documents[idx].get('db_name') == db_name else 1.0

            for q_token in query_tokens:
                if q_token not in doc_tokens:
                    continue
                tf = doc_tokens.count(q_token)
                idf_val = self.idf.get(q_token, 0.0)
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_len / self.avg_dl))
                score += idf_val * (numerator / denominator)

            scores.append((score * db_boost, self.documents[idx]))

        # Sort descending
        scores.sort(key=lambda x: x[0], reverse=True)
        top_results = [doc for s, doc in scores[:top_k] if s > 0]

        record_retrieval(db_name, len(top_results))

        if not top_results:
            return ""

        output = "\n\n=== DYNAMIC FEW-SHOT EXAMPLES (RAG) ===\n"
        output += "These are highly relevant, verified past queries. Study their structural logic:\n\n"
        for i, res in enumerate(top_results):
            output += f"Example {i+1}:\n"
            output += f"User Question: {res['query']}\n"
            output += f"Verified SQL:\n```sql\n{res['sql']}\n```\n\n"

        logger.info(f"[RAGService] Injected {len(top_results)} Dynamic Few-Shot examples into context.")
        return output
