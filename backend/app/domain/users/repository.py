import json
import os
from typing import Dict, Any
from app.infrastructure.storage.path_manager import StorageManager

class UserRepository:
    """
    Handles user state persistence (e.g., active project ID).
    Stored as project.json in the user's root directory.
    """

    @staticmethod
    def get_state_path(user_slug: str) -> str:
        base = StorageManager.get_results_root() / user_slug
        base.mkdir(parents=True, exist_ok=True)
        return str(base / "project.json")

    def get_state(self, user_slug: str) -> Dict[str, Any]:
        path = self.get_state_path(user_slug)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception: pass
        return {}

    def save_state(self, user_slug: str, state: Dict[str, Any]):
        path = self.get_state_path(user_slug)
        current = self.get_state(user_slug)
        current.update(state)
        with open(path, 'w') as f:
            json.dump(current, f, indent=2)

    def set_active_project(self, user_slug: str, project_id: str):
        self.save_state(user_slug, {"activeProjectId": project_id})
