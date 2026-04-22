import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.infrastructure.storage.path_manager import StorageManager

class ProjectRepository:
    """
    Handles persistence and retrieval of project configurations.
    Stored as project.json at the root of each project directory.
    """

    @staticmethod
    def get_project_path(project_slug: str, user_slug: str) -> Path:
        return StorageManager.get_project_dir(user_slug, project_slug) / "project.json"

    def get_all_projects(self, user_slug: str) -> List[Dict[str, Any]]:
        user_dir = StorageManager.get_results_root() / user_slug
        if not user_dir.exists(): return []
        
        projects = []
        for p_dir in user_dir.iterdir():
            if p_dir.is_dir():
                reg_file = p_dir / "project.json"
                if reg_file.exists():
                    try:
                        with open(reg_file, 'r') as f:
                            projects.append(json.load(f))
                    except Exception: pass
        return projects

    def get_project_by_id(self, project_id: str, user_slug: str) -> Optional[Dict[str, Any]]:
        for p in self.get_all_projects(user_slug):
            if p.get("id") == project_id: return p
        return None

    def save_project(self, project: Dict[str, Any], user_slug: str):
        slug = project.get("_slug") or StorageManager.get_safe_slug(project.get("name"))
        project["_slug"] = slug
        
        StorageManager.initialize_project(user_slug, slug)
        path = self.get_project_path(slug, user_slug)
        with open(path, 'w') as f:
            json.dump(project, f, indent=2)

    def delete_project(self, project_slug: str, user_slug: str) -> bool:
        path = StorageManager.get_project_dir(user_slug, project_slug)
        if path.exists():
            shutil.rmtree(path)
            return True
        return False
