import os
import stat
import shutil
from pathlib import Path
from typing import List

def remove_readonly(func, path, _):
    """Error handler for shutil.rmtree on Windows to remove readonly attributes."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def force_delete_dir(dir_path: Path):
    """Force deletes a directory, bypassing Windows readonly locks."""
    if dir_path.exists():
        shutil.rmtree(dir_path, onerror=remove_readonly)

def force_delete_file(file_path: Path):
    if file_path.exists():
        os.chmod(file_path, stat.S_IWRITE)
        file_path.unlink()

def get_target_dirs_for_date(base_dir: Path, date: str) -> List[Path]:
    """
    Returns a list of run directories to scan based on the date filter.
    Structure: base_dir/run_{run_id}/{dataset}/
    """
    if not base_dir.exists():
        return []

    if date == "all":
        return [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]

    # Specific date: match run folders whose embedded date matches YYYY-MM-DD
    dirs = []
    for d in base_dir.iterdir():
        if not d.is_dir() or not d.name.startswith("run_"):
            continue
        parts = d.name.split("_")
        if len(parts) >= 2:
            try:
                date_str = parts[1]
                run_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                if run_date == date:
                    dirs.append(d)
            except Exception:
                pass
    return dirs
