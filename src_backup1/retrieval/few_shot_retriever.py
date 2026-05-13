import os
import json
import numpy as np
from typing import List, Dict, Any, Optional
from src.utils.logger import logger

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False

class FewShotRetriever:
    """
    Retrieves similar past (question, SQL) pairs to include in the SQL generation prompt.
    """
    
    def __init__(self, examples_path: str = "data/few_shot_examples.json", model_name: str = "all-MiniLM-L6-v2"):
        self.examples_path = examples_path
        self.embeddings_path = "data/few_shot_embeddings.npy"
        os.makedirs("data", exist_ok=True)
        
        self.examples = []
        self.embeddings = None
        self.model = None
        
        if EMBEDDER_AVAILABLE:
            self.model = SentenceTransformer(model_name)
            self._load_examples()

    def _load_examples(self):
        if os.path.exists(self.examples_path):
            with open(self.examples_path, "r") as f:
                self.examples = json.load(f)
            
            if os.path.exists(self.embeddings_path):
                self.embeddings = np.load(self.embeddings_path)
            else:
                self._rebuild_embeddings()
        else:
            # Seed with empty list
            self.examples = []
            with open(self.examples_path, "w") as f:
                json.dump([], f)

    def _rebuild_embeddings(self):
        if not self.examples:
            return
        logger.info("Rebuilding few-shot embeddings...")
        questions = [ex["question"] for ex in self.examples]
        self.embeddings = self.model.encode(questions)
        np.save(self.embeddings_path, self.embeddings)

    def retrieve(self, question: str, intent: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieves top_k similar examples based on semantic similarity and table overlap.
        """
        if not self.examples or self.embeddings is None:
            return []
            
        # 1. Semantic Similarity
        query_emb = self.model.encode([question])
        # Simple cosine similarity
        similarities = np.dot(self.embeddings, query_emb.T).flatten() / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_emb)
        )
        
        # 2. Boosting
        boosted_scores = []
        target_tables = set(intent.get("source", {}).get("candidate_tables", []))
        
        for i, ex in enumerate(self.examples):
            score = similarities[i]
            
            # Table overlap boost
            ex_tables = set(ex.get("tables", []))
            if target_tables & ex_tables:
                score += 0.2
                
            # Complexity boost
            if ex.get("complexity") == intent.get("complexity"):
                score += 0.1
                
            boosted_scores.append((ex, score))
            
        # 3. Sort and filter
        boosted_scores.sort(key=lambda x: x[1], reverse=True)
        return [b[0] for b in boosted_scores[:top_k]]

    def format_for_prompt(self, examples: List[Dict[str, Any]]) -> str:
        if not examples:
            return ""
            
        formatted = "\n-- Similar past examples for reference:\n"
        for i, ex in enumerate(examples):
            formatted += f"-- Example {i+1}\n-- Question: {ex['question']}\n{ex['sql']}\n\n"
        return formatted

    def add_example(self, question: str, sql: str, tables: List[str], conditions: List[str], complexity: str):
        """Learning loop: adds a validated query to the few-shot store."""
        new_ex = {
            "question": question,
            "sql": sql,
            "tables": tables,
            "conditions": conditions,
            "complexity": complexity
        }
        self.examples.append(new_ex)
        with open(self.examples_path, "w") as f:
            json.dump(self.examples, f, indent=2)
            
        self._rebuild_embeddings()
        logger.info(f"Added new few-shot example for question: {question[:50]}...")
