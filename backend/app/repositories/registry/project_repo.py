import os
import json
import uuid
from typing import List, Dict, Any, Optional
from app.repositories.registry.paths import METADATA_DIR

PROJECTS_FILE = METADATA_DIR / "projects.json"

class ProjectRepository:
    """
    Repository to manage database connections as 'Projects'.
    Stores configurations in a JSON file.
    """
    @staticmethod
    def _ensure_file():
        if not os.path.exists(METADATA_DIR):
            os.makedirs(METADATA_DIR, exist_ok=True)
        if not os.path.exists(PROJECTS_FILE):
            with open(PROJECTS_FILE, 'w') as f:
                json.dump([], f)

    @staticmethod
    def get_all_projects() -> List[Dict[str, Any]]:
        ProjectRepository._ensure_file()
        try:
            with open(PROJECTS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return []

    @staticmethod
    def save_project(project_data: Dict[str, Any]) -> Dict[str, Any]:
        projects = ProjectRepository.get_all_projects()
        
        # Add ID and default connection structure if new
        is_new = False
        if "id" not in project_data or not project_data["id"]:
            project_data["id"] = str(uuid.uuid4())
            is_new = True
            
        if "connection" not in project_data:
            project_data["connection"] = None
            
        # Check for update vs insert
        for i, p in enumerate(projects):
            if p.get("id") == project_data["id"]:
                projects[i] = project_data
                break
        else:
            projects.append(project_data)
            
        with open(PROJECTS_FILE, 'w') as f:
            json.dump(projects, f, indent=2)
            
        return project_data

    @staticmethod
    def delete_project(project_id: str) -> bool:
        projects = ProjectRepository.get_all_projects()
        initial_len = len(projects)
        projects = [p for p in projects if p.get("id") != project_id]
        
        if len(projects) < initial_len:
            with open(PROJECTS_FILE, 'w') as f:
                json.dump(projects, f, indent=2)
            return True
        return False
        
    @staticmethod
    def get_project_by_id(project_id: str) -> Optional[Dict[str, Any]]:
        projects = ProjectRepository.get_all_projects()
        for p in projects:
            if p.get("id") == project_id:
                return p
        return None
