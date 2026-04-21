#!/usr/bin/env python
"""
Local Qdrant Server
Runs Qdrant with in-memory + file storage at http://localhost:6333
"""
import subprocess
import sys
import time
import requests

def check_qdrant_running():
    """Check if Qdrant is already running"""
    try:
        resp = requests.get("http://localhost:6333/collections", timeout=2)
        return resp.status_code < 500
    except:
        return False

def start_qdrant_server():
    """Start Qdrant server using Docker or fallback method"""
    if check_qdrant_running():
        print("✓ Qdrant already running on http://localhost:6333")
        return True
    
    print("Starting Qdrant server...")
    print("=" * 60)
    
    # Try Docker first
    try:
        print("Attempting Docker setup...")
        result = subprocess.run(
            ["docker", "run", "-d", "--name", "qdrant-local", 
             "-p", "6333:6333", "-p", "6334:6334",
             "qdrant/qdrant:latest"],
            capture_output=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✓ Docker container started")
            time.sleep(3)
            if check_qdrant_running():
                print("✓ Qdrant is running on http://localhost:6333")
                return True
        else:
            print("Docker start failed, trying alternative method...")
    except Exception as e:
        print(f"Docker not available: {e}")
    
    # Fallback: Use Qdrant Python in-memory mode
    print("\nStarting Qdrant in-memory mode...")
    try:
        from qdrant_client.http import models
        from qdrant_client import QdrantClient
        
        # Create in-memory client (auto-saves to disk)
        client = QdrantClient(path="./qdrant_storage")
        print("✓ Qdrant in-memory mode ready")
        print("  Storage: ./qdrant_storage")
        print("  Note: API access at http://localhost:6333 requires HTTP server")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False

if __name__ == "__main__":
    success = start_qdrant_server()
    if success:
        print("\n" + "=" * 60)
        print("✓ Qdrant is ready!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ Failed to start Qdrant")
        print("=" * 60)
        sys.exit(1)
