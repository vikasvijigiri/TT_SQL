import json
import socket
import ssl
from urllib.parse import urlparse

from core.config import get_settings
from core.logger import Logger


class VectorStoreAgent:
    """
    Agent responsible for storing and retrieving successful query-SQL pairs
    using Qdrant and local embeddings.
    """

    # Class-level cache for heavy resources
    _MODEL_CACHE = None
    _CLIENT_CACHE = {}  # URL_APIKEY -> Client
    _COLLECTION_VERIFIED = set()  # (url, collection)
    _SSL_CONTEXT = None

    @classmethod
    def clear_caches(cls, include_models: bool = False):
        """Clears the Qdrant client cache and optionally the heavy embedding model."""
        cls._CLIENT_CACHE = {}
        cls._COLLECTION_VERIFIED = set()
        if include_models:
            cls._MODEL_CACHE = None
        Logger.log("VectorStoreAgent caches cleared.", level="DEBUG")

    def __init__(self, collection_override: str | None = None):
        settings = get_settings()
        self.url = settings.QDRANT_URL or "http://localhost:6333"
        self.api_key = settings.QDRANT_API_KEY
        self.collection_name = collection_override or settings.QDRANT_COLLECTION

        self.vector_size = 384
        self._ensure_initialized()

    def _ensure_initialized(self):
        """Lazy load heavy model and client on first use."""
        if not self.collection_name:
            return

        try:
            # 1. Reuse or Load Model
            if VectorStoreAgent._MODEL_CACHE is None:
                from sentence_transformers import SentenceTransformer

                Logger.log("Loading SentenceTransformer model ('all-MiniLM-L6-v2')...")
                VectorStoreAgent._MODEL_CACHE = SentenceTransformer("all-MiniLM-L6-v2")

            # 2. Reuse or Load Client
            cache_key = f"{self.url}_{self.api_key}"
            if cache_key not in VectorStoreAgent._CLIENT_CACHE:
                from qdrant_client import QdrantClient

                VectorStoreAgent._CLIENT_CACHE[cache_key] = QdrantClient(
                    url=self.url, api_key=self.api_key
                )

            # 3. Reuse SSL Context for raw sockets
            if VectorStoreAgent._SSL_CONTEXT is None:
                VectorStoreAgent._SSL_CONTEXT = ssl.create_default_context()

            # 4. Verified collection status
            verify_key = (self.url, self.collection_name)
            if verify_key not in VectorStoreAgent._COLLECTION_VERIFIED:
                self._ensure_collection_exists()
                VectorStoreAgent._COLLECTION_VERIFIED.add(verify_key)

        except Exception as e:
            Logger.log(f"Failed to initialize VectorStoreAgent: {e}", level="ERROR")

    def _ensure_collection_exists(self):
        """Internal check to ensure collection exists in Qdrant."""
        client = VectorStoreAgent._CLIENT_CACHE.get(f"{self.url}_{self.api_key}")
        if not client:
            return

        try:
            from qdrant_client.http import models

            collections = client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                Logger.log(f"Creating Qdrant collection: {self.collection_name}")
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.vector_size, distance=models.Distance.COSINE
                    ),
                )
        except Exception as e:
            Logger.log(f"Error checking/creating collection: {e}", level="ERROR")

    VECTOR_NAME = "text_embedding"
    EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def _raw_https_post(self, path: str, payload: dict) -> dict:
        """Send a POST via raw SSL socket to Qdrant (Persistent Context Reuse)."""
        parsed = urlparse(self.url)
        host = parsed.hostname
        port = parsed.port or 443
        body = json.dumps(payload).encode("utf-8")
        request = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"api-key: {self.api_key}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode() + body

        ctx = VectorStoreAgent._SSL_CONTEXT or ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=20) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    ssock.sendall(request)
                    raw = b""
                    while True:
                        chunk = ssock.recv(4096)
                        if not chunk:
                            break
                        raw += chunk

            resp_str = raw.decode("utf-8", errors="replace")
            body_start = resp_str.find("\r\n\r\n")
            if body_start != -1:
                body = resp_str[body_start + 4 :]
                first_brace = body.find("{")
                last_brace = body.rfind("}")
                if first_brace != -1 and last_brace != -1:
                    body = body[first_brace : last_brace + 1]
                return json.loads(body)
            return {"error": "No body found in response"}
        except Exception as e:
            return {"error": str(e)}

    def retrieve_relevant_columns(self, query: str, limit: int = 10) -> list[dict]:
        """Retrieve top-N most relevant columns using Qdrant Cloud Inference."""
        if not self.collection_name:
            return []

        search_payload = {
            "prefetch": {
                "query": {"text": query, "model": self.EMBED_MODEL},
                "using": self.VECTOR_NAME,
            },
            "query": {"text": query, "model": self.EMBED_MODEL},
            "using": self.VECTOR_NAME,
            "limit": 50,
            "with_payload": True,
        }

        try:
            result = self._raw_https_post(
                f"/collections/{self.collection_name}/points/query", search_payload
            )
            if "result" not in result:
                return []

            pts = (
                result["result"].get("points", [])
                if isinstance(result["result"], dict)
                else result["result"]
            )
            retrieved_columns = []
            type_counts = {}
            seen = set()

            for res in pts:
                meta = res.get("payload", {})
                tname = meta.get("table_name") or meta.get("table")
                cname = meta.get("column_name") or meta.get("name")
                dtype = meta.get("type") or meta.get("data_type")

                if not tname or not cname or not dtype:
                    continue

                if data_type := dtype:
                    if data_type not in type_counts:
                        type_counts[data_type] = 0
                    if type_counts[data_type] >= limit:
                        continue
                    key = (tname, cname)
                    if key in seen:
                        continue
                    type_counts[data_type] += 1
                    seen.add(key)
                    retrieved_columns.append(
                        {
                            "table_name": tname,
                            "column_name": cname,
                            "type": data_type,
                            "description": meta.get("description", ""),
                            "sample_values": meta.get("sample_values")
                            or meta.get("samples"),
                            "score": res.get("score", 0.0),
                        }
                    )
            Logger.log(
                f"[RAG] Column Retrieval: returned {len(retrieved_columns)} columns across {len({c['table_name'] for c in retrieved_columns})} table(s)."
            )
            return retrieved_columns
        except Exception as e:
            Logger.log(f"retrieve_relevant_columns failed: {e}", level="ERROR")
            return []


# sample comment
