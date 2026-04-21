import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(os.getcwd())))

from app.repositories.registry.paths import get_metadata_dir, get_active_project_slug

def verify_paths():
    user_slug = "vikas"
    print(f"Verifying paths for user: {user_slug}")
    
    project_slug = get_active_project_slug(user_slug)
    print(f"Resolved project_slug: {project_slug}")
    
    metadata_dir = get_metadata_dir(user_slug, project_slug)
    print(f"Metadata directory: {metadata_dir}")
    
    collection_name = "IPL"
    metadata_path = metadata_dir / f"{collection_name}.json"
    print(f"Expected metadata path: {metadata_path}")
    print(f"Metadata file exists: {metadata_path.exists()}")

if __name__ == "__main__":
    verify_paths()
