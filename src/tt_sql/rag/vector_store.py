import os
import uuid
from typing import List, Dict, Optional
from ..core.logger import Logger

class VectorStoreAgent:
    """
    Agent responsible for storing and retrieving successful query-SQL pairs
    using Qdrant and local embeddings.
    """
    
    def __init__(self):
        self.url = os.getenv("QDRANT_URL", "http://localhost:6333")
        # Support both naming conventions
        self.api_key = os.getenv("QDRANT_API_KEY") or os.getenv("QDRANT_API")
        self.collection_name = os.getenv("QDRANT_COLLECTION", "spider2_metadata")
        
        # Lazy imports to speed up initial app load
        try:
            from sentence_transformers import SentenceTransformer
            from qdrant_client import QdrantClient
            
            # Initialize embedding model (local)
            # This might take a few seconds, but only when this Agent is instantiated
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.vector_size = 384 
            
            self.client = QdrantClient(url=self.url, api_key=self.api_key)
            self._ensure_collection()
            
        except ImportError:
            Logger.log("Missing dependencies: pip install qdrant-client sentence-transformers", level="ERROR")
            self.client = None
            self.model = None
        except Exception as e:
            Logger.log(f"Failed to initialize VectorStoreAgent: {e}", level="ERROR")
            self.client = None
            self.model = None

    def _ensure_collection(self):
        """Ensures the collection exists in Qdrant."""
        if not self.client:
            return
            
        try:
            from qdrant_client.http import models
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                Logger.log(f"Creating Qdrant collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size,
                        distance=models.Distance.COSINE
                    )
                )
        except Exception as e:
            Logger.log(f"Error checking/creating collection: {e}", level="ERROR")

    def upsert_correct_pair(self, query: str, sql: str, instance_id: str = ""):
        """Stores a successful query-SQL pair in the vector store."""
        if not self.client or not self.model:
            return
            
        try:
            from qdrant_client.http import models
            
            vector = self.model.encode(query).tolist()
            point_id = str(uuid.uuid4())
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "doc_type": "example",
                            "query": query,
                            "sql": sql,
                            "instance_id": instance_id
                        }
                    )
                ]
            )
            Logger.log(f"Successfully stored RAG example for: {instance_id}")
        except Exception as e:
            Logger.log(f"Failed to upsert RAG example: {e}", level="ERROR")

    def upsert_table_metadata(self, table_name: str, schema_text: str, metadata: Dict = None):
        """Stores table schema/metadata in the vector store."""
        if not self.client or not self.model:
            return

        try:
            from qdrant_client.http import models
            
            # Embed the schema description (table name + columns + descriptions)
            vector = self.model.encode(schema_text).tolist()
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, table_name)) # Consistent ID for updates
            
            payload = {
                "doc_type": "table",
                "table_name": table_name,
                "content": schema_text
            }
            if metadata:
                payload.update(metadata)

            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    )
                ]
            )
            Logger.log(f"Successfully upserted RAG metadata for table: {table_name}")
        except Exception as e:
            Logger.log(f"Failed to upsert RAG table metadata: {e}", level="ERROR")


    def retrieve_similar_examples(self, query: str, limit: int = 3) -> List[Dict]:
        """Retrieves similar past successes for a given query."""
        if not self.client or not self.model: return []
            
        try:
            from qdrant_client.http import models
            vector = self.model.encode(query).tolist()
            
            # Filter for doc_type="example"
            search_filter = models.Filter(
                must=[models.FieldCondition(key="doc_type", match=models.MatchValue(value="example"))]
            )

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=search_filter
            )
            
            examples = []
            for hit in search_result:
                examples.append({
                    "query": hit.payload.get("query"),
                    "sql": hit.payload.get("sql")
                })
            return examples
        except Exception as e:
            Logger.log(f"Failed to retrieve RAG examples: {e}", level="ERROR")
            return []

    def retrieve_relevant_tables(self, query: str, limit: int = 5) -> List[Dict]:
        """Retrieves relevant table schemas for a given query."""
        if not self.client or not self.model: return []

        try:
            from qdrant_client.http import models
            vector = self.model.encode(query).tolist()

            # Filter for doc_type="table"
            search_filter = models.Filter(
                must=[models.FieldCondition(key="doc_type", match=models.MatchValue(value="table"))]
            )

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=search_filter
            )

            tables = []
            for hit in search_result:
                tables.append({
                    "table_name": hit.payload.get("table_name"),
                    "content": hit.payload.get("content"),
                    "score": hit.score
                })
            return tables
        except Exception as e:
            Logger.log(f"Failed to retrieve RAG tables: {e}", level="ERROR")
            return []

