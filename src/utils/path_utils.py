import os

BASE_DB_DIR = "resources/databases/snowflake"

def get_db_path(db_name: str) -> str:
    """Finds the deepest directory containing JSON metadata files for a given DB."""
    db_root = os.path.join(BASE_DB_DIR, db_name)
    if not os.path.exists(db_root):
        raise ValueError(f"Database directory not found: {db_root}")
    for root, dirs, files in os.walk(db_root):
        if any(f.endswith('.json') for f in files):
            return root
    raise ValueError(f"No JSON metadata files found in {db_root}")
