import os
import json
import argparse
import sys
from pathlib import Path

# Ensure PYTHONPATH includes project root
sys.path.append(os.getcwd())

from app.repositories.registry.paths import METADATA_DIR, PROJECT_ROOT
from app.repositories.config import settings
from app.services.knowledge_service import KnowledgeService

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="Phase 1: Knowledge Preparation (Direct Service Implementation)")
    parser.add_argument("--no-enrich", action="store_true", help="Skip LLM-based description enrichment")
    parser.add_argument("--overwrite", action="store_true", help="Force extraction even if metadata exists")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers for enrichment")
    
    args = parser.parse_args()
    service = KnowledgeService()
    
    schema_name = settings.SCHEMA or "public"
    collection_name = settings.COLLECTION_NAME
    metadata_path = METADATA_DIR / f"{schema_name}.json"
    
    print(f"\n{'='*60}")
    print(f" 🚀 PHASE 1: KNOWLEDGE PREPARATION [Schema: {schema_name}]")
    print(f"{'='*60}\n")

    metadata = None

    # 1. Step 1: Extraction & Enrichment
    if args.overwrite or not metadata_path.exists() or metadata_path.stat().st_size == 0:
        print(f"[1/2] Extracting Schema: {schema_name}")
        metadata = service.extract_metadata(schema_name)
        
        if not args.no_enrich:
            print(f"      Enriching with {args.workers} workers...")
            metadata = service.enrich_metadata(metadata, args.workers)
        
        # Save metadata
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
        print(f"      [OK] Metadata successfully generated: {metadata_path}")
    else:
        print(f"[1/2] Skipping Extraction: metadata found at {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

    # 2. Step 2: Ingestion
    print(f"\n[2/2] Ingesting to Qdrant [Collection: {collection_name}]")
    try:
        service.ingest_to_vector_store(metadata, collection_name)
        print(f"      [OK] Knowledge ingestion complete.")
    except Exception as e:
        print(f"[Error] Knowledge ingestion failed: {e}")
        sys.exit(1)
        
    print(f"\n{'='*60}")
    print(f" ✅ KNOWLEDGE PREPARATION COMPLETE")
    print(f" Schema: {schema_name} | Collection: {collection_name}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
