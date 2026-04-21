#!/usr/bin/env python
"""
Lightweight Qdrant HTTP Server
Provides REST API compatibility for local Qdrant client
Runs on http://localhost:6333
"""
import json
import sys
from pathlib import Path
from flask import Flask, request, jsonify, Response
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)

# Initialize Qdrant with file-based storage
STORAGE_PATH = Path(__file__).parent / "qdrant_storage"
STORAGE_PATH.mkdir(exist_ok=True)

try:
    client = QdrantClient(path=str(STORAGE_PATH))
    logger.info(f"✓ Qdrant client initialized with storage at {STORAGE_PATH}")
except Exception as e:
    logger.error(f"Failed to initialize Qdrant client: {e}")
    sys.exit(1)

# ============ REST API ENDPOINTS ============

@app.route('/', methods=['GET'])
def root():
    """Health check"""
    return jsonify({"status": "ok", "version": "1.0"})

@app.route('/health', methods=['GET'])
def health():
    """Health endpoint"""
    return jsonify({"status": "ok"})

@app.route('/collections', methods=['GET'])
def list_collections():
    """List all collections"""
    try:
        collections = client.get_collections()
        return jsonify({
            "collections": [{"name": c.name} for c in collections.collections] if collections.collections else []
        })
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/collections/<collection_name>', methods=['GET'])
def get_collection(collection_name):
    """Get collection info"""
    try:
        collection_info = client.get_collection(collection_name)
        return jsonify(collection_info.dict())
    except Exception as e:
        logger.error(f"Error getting collection {collection_name}: {e}")
        return jsonify({"error": str(e)}), 404

@app.route('/collections/<collection_name>', methods=['PUT'])
def create_collection(collection_name):
    """Create collection"""
    try:
        data = request.json
        vectors = data.get("vectors", {})
        
        # Get vector size from the first vector config
        vector_size = None
        for vec_name, vec_config in vectors.items():
            vector_size = vec_config.get("size", 768)
            break
        
        if vector_size is None:
            return jsonify({"error": "No vector size specified"}), 400
        
        # Create collection
        client.recreate_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
        )
        logger.info(f"✓ Created collection '{collection_name}' with vector size {vector_size}")
        return jsonify({"status": "created"}), 201
    except Exception as e:
        logger.error(f"Error creating collection {collection_name}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/collections/<collection_name>/index', methods=['PUT'])
def create_index(collection_name):
    """Create field index (dummy - not used in qdrant-client)"""
    try:
        data = request.json
        # Qdrant client handles indexing automatically
        logger.info(f"Index requested for collection '{collection_name}': {data.get('field_name')}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error creating index: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/collections/<collection_name>/points', methods=['PUT'])
def upsert_points(collection_name):
    """Upsert points into collection"""
    try:
        data = request.json
        points = data.get("points", [])
        
        # Convert points format
        qdrant_points = []
        for p in points:
            vectors = p.get("vector", {})
            # Handle both {text_embedding: [...]} and simple [...] formats
            if isinstance(vectors, dict):
                vector_data = vectors.get("text_embedding", [])
            else:
                vector_data = vectors
            
            qdrant_points.append(PointStruct(
                id=p["id"],
                vector=vector_data,
                payload=p.get("payload", {})
            ))
        
        client.upsert(
            collection_name=collection_name,
            points=qdrant_points
        )
        logger.info(f"✓ Upserted {len(qdrant_points)} points to '{collection_name}'")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"Error upserting points: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/collections/<collection_name>/points/search', methods=['POST'])
def search_points(collection_name):
    """Search points in collection"""
    try:
        data = request.json
        
        vector_spec = data.get("vector", {})
        vector = vector_spec.get("vector", []) if isinstance(vector_spec, dict) else vector_spec
        
        results = client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=data.get("limit", 10),
            offset=data.get("offset", 0),
            with_payload=data.get("with_payload", True),
            query_filter=data.get("filter")
        )
        
        return jsonify({
            "result": [
                {
                    "id": r.id,
                    "score": r.score,
                    "payload": r.payload,
                    "vector": r.vector
                }
                for r in results
            ]
        }), 200
    except Exception as e:
        logger.error(f"Error searching points: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/collections/<collection_name>', methods=['DELETE'])
def delete_collection(collection_name):
    """Delete collection"""
    try:
        client.delete_collection(collection_name)
        logger.info(f"✓ Deleted collection '{collection_name}'")
        return jsonify({"status": "deleted"}), 200
    except Exception as e:
        if "not found" in str(e).lower():
            return jsonify({"status": "deleted"}), 200
        logger.error(f"Error deleting collection: {e}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    """Handle 404"""
    return jsonify({"error": "endpoint not found"}), 404

# ============ STARTUP ============

if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("Starting Qdrant HTTP Server on http://localhost:6333")
    logger.info("Storage: " + str(STORAGE_PATH))
    logger.info("=" * 70)
    
    try:
        app.run(host="0.0.0.0", port=6333, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
