import os
import re
from pathlib import Path

def is_valid_results_path(path: Path):
    # Must be results/{username}/{project_name}/{model_name}
    rel = path.relative_to(path.parents[2])
    parts = rel.parts
    return (
        len(parts) == 3 and
        re.match(r'^[a-z0-9_]+$', parts[0]) and
        re.match(r'^[a-z0-9_]+$', parts[1]) and
        re.match(r'^[a-zA-Z0-9_\-\.]+$', parts[2])
    )

def remove_junk_results_folders(results_root=None, dry_run=True):
    """
    Removes folders in results/ that do not match results/{username}/{project_name}/{model_name}
    Set dry_run=False to actually delete.
    """
    # Hardcoded path for this environment
    if results_root is None:
        results_root = Path(r"C:/Users/VikasVijigiri/Documents/TT_SQL/backend/app/repositories/data/results")
    else:
        results_root = Path(results_root)

    removed = []
    for user_dir in results_root.iterdir():
        if not user_dir.is_dir():
            continue
        for project_dir in user_dir.iterdir():
            if not project_dir.is_dir():
                continue
            for model_dir in project_dir.iterdir():
                if not model_dir.is_dir():
                    continue
                # Only keep if valid
                if not is_valid_results_path(model_dir):
                    if not dry_run:
                        import shutil
                        shutil.rmtree(model_dir)
                    removed.append(str(model_dir))
    return removed

if __name__ == "__main__":
    removed = remove_junk_results_folders(dry_run=False)
    print("Removed folders:", removed)
