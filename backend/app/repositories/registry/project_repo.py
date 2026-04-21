import os
import json
import uuid
import re
from typing import List, Dict, Any, Optional


class ProjectRepository:
    """
    Repository to manage database connections as 'Projects'.
    Stores configurations in a JSON file.
    """
    @staticmethod
    def _get_paths(user_slug: str = None):
        """
        Resolved paths for a specific project. 
        """
        from app.repositories.registry.paths import get_project_registry_dir, get_user_slug
        user_slug = user_slug or get_user_slug()
        registry_dir = get_project_registry_dir(user_slug, "default") # Placeholder for generic registry access
        return registry_dir, registry_dir / "project.json"

    @staticmethod
    def _ensure_file(user_slug: str = None):
        """Not strictly necessary for scan-based, but kept for creating the active project dir."""
        registry_dir, _ = ProjectRepository._get_paths(user_slug)
        if not os.path.exists(registry_dir):
            os.makedirs(registry_dir, exist_ok=True)


    @staticmethod
    def get_all_projects(user_slug: str = None) -> List[Dict[str, Any]]:
        """
        Discovers all projects by scanning results/{username}/{project}/registry/project.json
        Production standard: Returns sorted list of all user's projects.
        """
        from app.repositories.registry.paths import get_path_structure, get_user_slug
        
        user_slug = user_slug or get_user_slug()
        results_dir = get_path_structure().get_results_dir()
        user_dir = results_dir / user_slug
        
        # If user directory doesn't exist, return empty list (no projects)
        if not user_dir.exists():
            return []
        
        projects = []
        try:
            for project_item in user_dir.iterdir():
                if not project_item.is_dir():
                    continue
                
                # Skip system directories
                if project_item.name in ["global", "__pycache__", ".git"]:
                    continue
                
                config_path = project_item / "registry" / "project.json"
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            project = json.load(f)
                            if project:
                                projects.append(project)
                    except (json.JSONDecodeError, IOError) as e:
                        # Log but continue scanning other projects
                        print(f"Warning: Failed to load project config from {config_path}: {e}")
                        continue
        except Exception as e:
            print(f"Warning: Error scanning projects in {user_dir}: {e}")
            return []
        
        # Sort by last_activity descending (newest first)
        return sorted(projects, key=lambda x: x.get("last_activity", ""), reverse=True)

    @staticmethod
    def save_project(project_data: Dict[str, Any], user_slug: str = None) -> Dict[str, Any]:
        """
        Saves a project to results/{username}/{project_slug}/registry/project.json
        
        Production standard: Uses centralized path helper, validates inputs, 
        ensures directories exist, and provides meaningful error messages.
        
        Args:
            project_data: Dictionary containing project configuration
            user_slug: User identifier (derived from email or username)
        
        Returns:
            Dictionary: The saved project data with updated metadata
        
        Raises:
            ValueError: If project data or user_slug is invalid
            IOError: If file operations fail
        """
        if not project_data:
            raise ValueError("project_data cannot be empty")
        if not isinstance(project_data, dict):
            raise ValueError("project_data must be a dictionary")
        
        user_slug = user_slug or "default_user"
        if not user_slug.strip():
            raise ValueError("user_slug cannot be empty")
        
        # Ensure project has required fields
        if "name" not in project_data or not project_data["name"].strip():
            raise ValueError("Project name is required and cannot be empty")
        
        # Generate project ID if missing
        if "id" not in project_data or not project_data["id"]:
            project_data["id"] = str(uuid.uuid4())
        
        # Update last activity timestamp
        from datetime import datetime
        project_data["last_activity"] = datetime.now().isoformat()
        
        # Ensure connection field exists
        if "connection" not in project_data:
            project_data["connection"] = None
        
        # Create filesystem-safe project slug from name
        project_name = project_data.get("name", "default").strip()
        project_slug = re.sub(r'[^a-zA-Z0-9]', '_', project_name).lower().strip('_')
        
        if not project_slug:
            raise ValueError(f"Invalid project name: '{project_name}' produces empty slug")
        
        try:
            # Get the standard project registry directory
            from app.repositories.registry.paths import get_project_registry_dir
            registry_dir = get_project_registry_dir(user_slug, project_slug)
            
            # Ensure all parent directories exist
            registry_dir.mkdir(parents=True, exist_ok=True)
            
            # Write project configuration
            config_file = registry_dir / "project.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            return project_data
            
        except Exception as e:
            raise IOError(f"Failed to save project '{project_name}' to {registry_dir}: {str(e)}")

    @staticmethod
    def delete_project(project_id: str, user_slug: str = None) -> bool:
        """
        Deletes a project and its entire directory.
        Production standard: Finds project first, then removes directory safely.
        """
        if not project_id or not project_id.strip():
            raise ValueError("project_id is required")
        
        project = ProjectRepository.get_project_by_id(project_id, user_slug)
        if not project:
            return False
        
        user_slug = user_slug or "default_user"
        project_name = project.get("name", project_id)
        
        # Generate the same slug used when saving
        project_slug = re.sub(r'[^a-zA-Z0-9]', '_', project_name).lower().strip('_')
        
        try:
            # Get the standard project directory (parent of registry)
            from app.repositories.registry.paths import get_project_registry_dir
            registry_dir = get_project_registry_dir(user_slug, project_slug)
            project_dir = registry_dir.parent  # Get parent to remove entire project folder
            
            if project_dir.exists() and project_dir.is_dir():
                import shutil
                shutil.rmtree(project_dir)
                return True
            
            return False
            
        except Exception as e:
            print(f"Warning: Error deleting project {project_id}: {e}")
            return False
        
    @staticmethod
    def delete_all_projects() -> bool:
        ProjectRepository._ensure_file()
        _, projects_file = ProjectRepository._get_paths()
        with open(projects_file, 'w') as f:
            json.dump([], f, indent=2)
        return True
        
    @staticmethod
    def get_project_by_id(project_id: str, user_slug: str = None) -> Optional[Dict[str, Any]]:
        projects = ProjectRepository.get_all_projects(user_slug)
        for p in projects:
            if p.get("id") == project_id:
                return p
        return None

    @staticmethod
    def get_storage_stats(user_slug: str = None) -> List[Dict[str, Any]]:
        """
        Scans the user's results directory to calculate stats for each project workspace.
        """
        from app.repositories.registry.paths import get_path_structure, get_user_slug
        user_slug = user_slug or get_user_slug()
        results_dir = get_path_structure().get_results_dir()

        if not os.path.exists(results_dir):
            return []

        workspaces = []
        user_dir = results_dir / user_slug
        
        if not os.path.exists(user_dir):
            return []
        
        for project_item in os.listdir(user_dir):
            item_path = user_dir / project_item
            if not os.path.isdir(item_path):
                continue
            
            # Simple recursive size calculation
            total_size = 0
            artifact_count = 0
            for dirpath, dirnames, filenames in os.walk(item_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
                    artifact_count += 1
            
            # item is now the project_slug folder
            project_name = project_item
            active_projects = ProjectRepository.get_all_projects(user_slug)
            for p in active_projects:
                import re
                p_slug = re.sub(r'[^a-zA-Z0-9]', '_', p.get("name", "")).lower().strip('_')
                if project_item == p_slug or project_item == p.get("id"):
                    project_name = p.get("name")
                    break

            workspaces.append({
                "slug": project_item,
                "name": project_name,
                "size_mb": round(total_size / (1024 * 1024), 2),
                "artifact_count": artifact_count,
                "path": str(item_path)
            })
        
        return workspaces

    @staticmethod
    def wipe_workspace_results(workspace_slug: str, user_slug: str = None) -> bool:
        """Deletes only analytical artifacts (sql, csv, logs) for a workspace, preserving registry."""
        from app.repositories.registry.paths import get_path_structure, get_user_slug
        user_slug = user_slug or get_user_slug()
        results_dir = get_path_structure().get_results_dir()
        base_path = results_dir / user_slug / workspace_slug
        
        if not base_path.exists():
            return False
            
        success = False
        # In a flattened structure, we might have model-specific folders OR items directly in the project-slug folder
        # We delete known subfolders AND all model folders (which aren't 'registry' or 'metadata_extracts')
        if base_path.exists():
            for item in os.listdir(base_path):
                target = base_path / item
                if item in ["registry", "metadata_extracts"]:
                    continue # Preserve these
                
                if target.is_dir():
                    shutil.rmtree(target)
                    success = True
                else:
                    # Also delete any loose files in the project root that aren't registry/metadata
                    os.remove(target)
                    success = True
        return success

    @staticmethod
    def cleanup_active_project_results(user_slug: str = None) -> bool:
        """Wipes results for the project currently active for this user."""
        from app.repositories.registry.user_repo import UserRepository
        user_state = UserRepository().get_state(user_slug)
        active_id = user_state.get("activeProjectId")
        
        if not active_id:
            return False
            
        project = ProjectRepository.get_project_by_id(active_id, user_slug=user_slug)
        if not project:
            return False
            
        import re
        slug = re.sub(r'[^a-zA-Z0-9]', '_', project.get("name", active_id)).lower().strip('_')
        # Clean both by project slug and project ID to be safe
        success = ProjectRepository.wipe_workspace_results(slug, user_slug=user_slug)
        if slug != active_id:
            success = success or ProjectRepository.wipe_workspace_results(active_id, user_slug=user_slug)
        return success

    @staticmethod
    def cleanup_period_results(period: str, user_slug: str = None) -> bool:
        """Selective cleanup based on time."""
        # Simplified: wipes active project results
        return ProjectRepository.cleanup_active_project_results(user_slug=user_slug)
