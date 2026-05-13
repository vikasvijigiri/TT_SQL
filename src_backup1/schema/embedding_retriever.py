import os
import numpy as np
from typing import List, Optional
from src.utils.logger import logger
from src.schema.schema_graph_builder import ColumnNode

try:
    import faiss
    from sentence_transformers import SentenceTransformer
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS or SentenceTransformers not installed. EmbeddingRetriever will fall back to keyword matching.")

class EmbeddingRetriever:
    """
    Fast pre-filtering layer using semantic similarity (FAISS) and keyword matching.
    """
    
    def __init__(self, builder, db_name: str, model_name: str = "all-MiniLM-L6-v2"):
        self.builder = builder
        self.schema_graph = builder.graph
        self.db_name = db_name
        self.model_name = model_name
        self.index_path = f"schema_cache/embeddings_{db_name}.faiss"
        self.metadata_path = f"schema_cache/metadata_{db_name}.pkl"
        self.model = None
        self.index = None
        self.node_ids = [] # Maps index to ColumnNode full_path
        
        if FAISS_AVAILABLE:
            self.model = SentenceTransformer(model_name)
            self.warm_cache()

    def warm_cache(self):
        """Pre-builds or loads the FAISS index at startup."""
        self._load_or_build_index()

    def _load_or_build_index(self):
        """Loads index from disk or builds it if missing or schema changed."""
        import hashlib
        schema_hash = hashlib.md5(str(self.builder.schema).encode()).hexdigest()
        cache_dir = os.path.dirname(self.index_path)
        hash_path = os.path.join(cache_dir, f"embeddings_{self.db_name}.hash")
        
        rebuild = True
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path) and os.path.exists(hash_path):
            try:
                with open(hash_path, "r") as f:
                    if f.read().strip() == schema_hash:
                        rebuild = False
            except Exception: pass
            
        if not rebuild:
            try:
                self.index = faiss.read_index(self.index_path)
                import pickle
                with open(self.metadata_path, "rb") as f:
                    self.node_ids = pickle.load(f)
                logger.info(f"Loaded FAISS index for {self.db_name} (version {schema_hash[:8]})")
                return
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}. Rebuilding...")

        self.rebuild_index()
        try:
            with open(hash_path, "w") as f:
                f.write(schema_hash)
        except Exception: pass

    def rebuild_index(self):
        """Builds a new FAISS index from all column nodes in the graph."""
        if not FAISS_AVAILABLE:
            return

        logger.info(f"Building FAISS index for {self.db_name}...")
        nodes = []
        texts = []
        
        for node_id, data in self.schema_graph.nodes(data=True):
            node: ColumnNode = data["data"]
            nodes.append(node.full_path)
            # Embedding content: "{table}.{column}: {description}. Samples: {sample_values}"
            text = f"{node.table}.{node.column}: {node.description}. Samples: {', '.join(map(str, node.sample_values))}"
            texts.append(text)

        if not texts:
            logger.warning("No columns found to embed.")
            return

        embeddings = self.model.encode(texts, show_progress_bar=True)
        embeddings = np.array(embeddings).astype('float32')
        
        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension) # Inner Product on normalized vectors = Cosine Similarity
        self.index.add(embeddings)
        self.node_ids = nodes
        
        # Save to disk
        faiss.write_index(self.index, self.index_path)
        import pickle
        with open(self.metadata_path, "wb") as f:
            pickle.dump(self.node_ids, f)
            
        logger.info(f"FAISS index built and saved to {self.index_path}")

    def retrieve_candidates(self, raw_field: str, value: str = "", top_k: int = 15) -> List[ColumnNode]:
        """
        Retrieves top_k candidates using semantic search and keyword match.
        """
        candidate_ids = set()
        
        # 1. Semantic Search
        if FAISS_AVAILABLE and self.index is not None:
            query_text = f"{raw_field}: {value}"
            query_embedding = self.model.encode([query_text]).astype('float32')
            faiss.normalize_L2(query_embedding)
            
            distances, indices = self.index.search(query_embedding, top_k)
            for idx in indices[0]:
                if idx != -1:
                    candidate_ids.add(self.node_ids[idx])
        
        # 2. Keyword/Fuzzy fallback and union
        graph_candidates = self.builder.get_candidates(raw_field, value, top_k=top_k)
        for cand in graph_candidates:
            candidate_ids.add(cand.full_path)
            
        # 3. Value-based matching (High precision boost)
        value_matches = []
        if value:
            val_lower = str(value).lower()
            for node_id, data in self.schema_graph.nodes(data=True):
                node = data["data"]
                if any(val_lower == str(v).lower() for v in node.sample_values):
                    value_matches.append(node_id)
                    candidate_ids.add(node_id)
                    
        # 4. Resolve IDs back to ColumnNodes
        logger.debug(f"Retrieved {len(candidate_ids)} candidate IDs for {raw_field}")
        
        # Build results, putting value matches first
        results = []
        # First, value matches
        for node_id in value_matches:
            if node_id in self.schema_graph:
                results.append(self.schema_graph.nodes[node_id]["data"])
        
        # Then, others from candidate_ids
        for node_id in candidate_ids:
            if node_id not in value_matches:
                if node_id in self.schema_graph:
                    results.append(self.schema_graph.nodes[node_id]["data"])
                
        return results[:top_k]

    def __repr__(self):
        status = "Active" if self.index else "Inactive"
        size = len(self.node_ids) if self.node_ids else 0
        return f"<EmbeddingRetriever status={status} size={size} model={self.model_name}>"
