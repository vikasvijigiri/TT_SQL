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
    Returns a list of directories to scan based on the date filter.
    Always includes the live `base_dir`, but also appends specific `_archive` folders.
    """
    dirs = []
    
    if date == "all":
        # Scan live dir
        dirs.append(base_dir)
        # Scan all archives
        archive_base = base_dir / "_archive"
        if archive_base.exists():
            for d in archive_base.iterdir():
                if d.is_dir():
                    dirs.append(d)
        return dirs
    
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    
    if date == today:
        dirs.append(base_dir)
    
    # Also look in archive folders matching the date (in case of multiple runs per day)
    archive_base = base_dir / "_archive"
    if archive_base.exists():
        for d in archive_base.iterdir():
            if d.is_dir():
                try:
                    date_str = d.name.split('_')[1]
                    run_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                    if run_date == date:
                        dirs.append(d)
                except Exception:
                    pass
    return dirs
