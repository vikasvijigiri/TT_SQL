import os
import json
import argparse
import sys
import subprocess
from pathlib import Path

# Ensure PYTHONPATH includes project root
sys.path.append(os.getcwd())

from app.repositories.registry.paths import METADATA_DIR, PROJECT_ROOT
from app.repositories.config import settings

# Fix encoding for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run_command(cmd_list):
    """Run a subprocess command and stream output."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    try:
        process = subprocess.Popen(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            cwd=str(PROJECT_ROOT),
            env=env
        )
        for line in process.stdout:
            print(line, end='', flush=True)
        process.wait()
        return process.returncode == 0
    except Exception as e:
        print(f"[Error] Command execution failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Phase 1: Knowledge Preparation (Extract -> Enrich -> Ingest)")
    parser.add_argument("--no-enrich", action="store_true", help="Skip LLM-based description enrichment")
    parser.add_argument("--overwrite", action="store_true", help="Force extraction even if metadata exists")
    parser.add_argument("--workers", type=int, default=5, help="Parallel workers for enrichment")
    
    args = parser.parse_args()
    
    schema_name = settings.SCHEMA
    collection_name = settings.COLLECTION_NAME
    metadata_path = METADATA_DIR / f"{schema_name}.json"
    
    print(f"\n{'='*60}")
    print(f" ðŸš€ PHASE 1: KNOWLEDGE PREPARATION [Schema: {schema_name}]")
    print(f"{'='*60}\n")

    # 1. Step 1: Extraction & Enrichment
    if args.overwrite or not metadata_path.exists() or metadata_path.stat().st_size == 0:
        print(f"[1/2] Processing Schema: {schema_name}")
        extract_cmd = [
            sys.executable, "app/services/scripts/run_extract_enrich.py",
        ]
        if not args.no_enrich:
            extract_cmd.append("--enrich")
            extract_cmd.extend(["--workers", str(args.workers)])
            
        if not run_command(extract_cmd):
            print("[Error] Extraction & Enrichment phase failed.")
            sys.exit(1)
        print(f"\n[OK] Metadata successfully generated: {metadata_path}")
    else:
        print(f"[1/2] Skipping Extraction: metadata found at {metadata_path}")

    # 2. Step 2: Ingestion
    print(f"\n[2/2] Ingesting to Qdrant [Collection: {collection_name}]")
    ingest_cmd = [
        sys.executable, "app/services/scripts/populate_vector_store.py",
        "--metadata-file", str(metadata_path),
    ]
    
    if not run_command(ingest_cmd):
        print("[Error] Knowledge ingestion failed.")
        sys.exit(1)
        
    print(f"\n{'='*60}")
    print(f" âœ… KNOWLEDGE PREPARATION COMPLETE")
    print(f" Schema: {schema_name} | Collection: {collection_name}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
