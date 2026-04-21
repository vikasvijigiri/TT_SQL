import os
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any

class CleanupService:
    """
    Service to manage selective purging of analytical results as requested by users.
    
    IMPORTANT: This service MUST ONLY be used for manual, user-initiated deletions.
    Automatic or periodic cleanup is strictly prohibited to ensure project 
    persistence as per the "Forever Saved" policy.
    """
    
    @staticmethod
    def get_project_dir(project_slug: str, user_slug: str = None) -> Path:
        from app.repositories.registry.paths import DATA_DIR
        user_slug = user_slug or "default_user"
        return DATA_DIR / "results" / user_slug / project_slug

    @staticmethod
    def purge_project(project_slug: str, user_slug: str = None) -> Dict[str, Any]:
        """Completely removes the results directory for a project."""
        target_dir = CleanupService.get_project_dir(project_slug, user_slug)
        if not target_dir.exists():
            return {"status": "skipped", "message": "Project directory not found"}
            
        try:
            shutil.rmtree(target_dir)
            return {"status": "success", "message": f"Successfully purged results for {project_slug}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def purge_by_time(project_slug: str, seconds_limit: int, user_slug: str = None) -> Dict[str, Any]:
        """Deletes files in a project results directory modified within the last N seconds."""
        target_dir = CleanupService.get_project_dir(project_slug, user_slug)
        if not target_dir.exists():
            return {"status": "skipped", "message": "Project directory not found"}

        now = time.time()
        deleted_count = 0
        errors = []
        
        # Threshold: we delete files NEWER than (now - seconds_limit)
        # Wait, usually "Session cleanup" means "Clear everything I just did" 
        # or "Clear everything OLDER than". 
        # User said "last one hour, today, yesterday". 
        # This implies CLEARING data from those periods.
        
        # If period is "Last Hour", threshold is (now - 3600). 
        # We delete files where mtime > (now - 3600).
        threshold = now - seconds_limit
        
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                file_path = Path(root) / file
                try:
                    mtime = os.path.getmtime(file_path)
                    if mtime > threshold:
                        os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    errors.append(str(e))
                    
        return {
            "status": "success" if not errors else "partial_success",
            "deleted_files": deleted_count,
            "errors": errors
        }

    @staticmethod
    def purge_date_range(project_slug: str, start_ts: float, end_ts: float, user_slug: str = None) -> Dict[str, Any]:
        """Purge files modified between two timestamps."""
        target_dir = CleanupService.get_project_dir(project_slug, user_slug)
        if not target_dir.exists():
            return {"status": "skipped", "message": "Project directory not found"}

        deleted_count = 0
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                file_path = Path(root) / file
                mtime = os.path.getmtime(file_path)
                if start_ts <= mtime <= end_ts:
                    os.remove(file_path)
                    deleted_count += 1
                    
        return {"status": "success", "deleted_files": deleted_count}
