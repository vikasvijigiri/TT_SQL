import os
import json
from typing import Dict, Any, Optional

class UserRepository:
    """
    Repository to manage user-specific state and settings.
    Stores data in user_state.json within the user's registry directory.
    """
    
    @staticmethod
    def _get_paths(user_slug: str):
        from app.repositories.paths import get_user_registry_dir
        registry_dir = get_user_registry_dir(user_slug)
        state_file = registry_dir / "user_state.json"
        return registry_dir, state_file

    @staticmethod
    def get_state(user_slug: str) -> Dict[str, Any]:
        """Fetch the last known state for a specific user."""
        if not user_slug:
            return {}
            
        _, state_file = UserRepository._get_paths(user_slug)
        if not os.path.exists(state_file):
            return {}
            
        try:
            with open(state_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def save_state(user_slug: str, state_data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist the current state for a specific user."""
        if not user_slug:
            return state_data
            
        registry_dir, state_file = UserRepository._get_paths(user_slug)
        os.makedirs(registry_dir, exist_ok=True)
        
        try:
            # Merge with existing state to preserve fields
            current_state = UserRepository.get_state(user_slug)
            current_state.update(state_data)
            
            # Add timestamp
            from datetime import datetime
            current_state["last_updated"] = datetime.now().isoformat()
            
            with open(state_file, 'w') as f:
                json.dump(current_state, f, indent=2)
            return current_state
        except Exception as e:
            print(f"Error saving user state: {e}")
            return state_data
