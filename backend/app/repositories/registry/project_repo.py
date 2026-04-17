import os
import json
import uuid
from typing import List, Dict, Any, Optional


class ProjectRepository:
    """
    Repository to manage database connections as 'Projects'.
    Stores configurations in a JSON file.
    """
    @staticmethod
    def _get_paths():
        from app.repositories.registry.paths import REGISTRY_DIR
        projects_file = REGISTRY_DIR / "projects.json"
        return REGISTRY_DIR, projects_file

    @staticmethod
    def _ensure_file():
        registry_dir, projects_file = ProjectRepository._get_paths()
        
        # Migration logic: Check if we have a legacy file to move
        if not os.path.exists(projects_file):
            ProjectRepository._migrate_legacy_registry(projects_file)
            
        if not os.path.exists(registry_dir):
            os.makedirs(registry_dir, exist_ok=True)
            
        if not os.path.exists(projects_file):
            with open(projects_file, 'w') as f:
                json.dump([], f)

    @staticmethod
    def _migrate_legacy_registry(target_file):
        """Attempts to find projects.json and metadata JSONs in legacy results and move to global registry."""
        from app.repositories.registry.paths import DATA_DIR, get_metadata_dir
        import shutil
        import glob
        
        # 1. Migrate projects.json
        ProjectRepository._migrate_file(
            patterns=[
                str(DATA_DIR / "results" / "*" / "metadata" / "projects.json"),
                str(DATA_DIR / "results" / "metadata_extracts" / "projects.json")
            ],
            target_file=target_file
        )
        
        # 2. Migrate database metadata (.json files)
        metadata_target_dir = get_metadata_dir()
        os.makedirs(metadata_target_dir, exist_ok=True)
        ProjectRepository._migrate_all_files(
            patterns=[
                str(DATA_DIR / "results" / "*" / "metadata" / "*.json"),
                str(DATA_DIR / "results" / "metadata_extracts" / "*.json"),
                str(DATA_DIR / "metadata_extracts" / "*.json") # ADDED THIS PATH
            ],
            target_dir=metadata_target_dir,
            exclude=["projects.json"]
        )

    @staticmethod
    def _migrate_file(patterns, target_file):
        import glob
        import shutil
        found_legacy = None
        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                found_legacy = matches[0]
                break
                
        if found_legacy and os.path.exists(found_legacy) and not os.path.exists(target_file):
            try:
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                shutil.copy2(found_legacy, target_file)
                print(f"MIGRATION: Successfully imported file from {found_legacy}")
            except Exception as e:
                print(f"MIGRATION ERROR: Failed to move legacy file: {e}")

    @staticmethod
    def _migrate_all_files(patterns, target_dir, exclude=None):
        import glob
        import shutil
        exclude = exclude or []
        for pattern in patterns:
            for match in glob.glob(pattern):
                fname = os.path.basename(match)
                if fname in exclude: continue
                
                target_path = target_dir / fname
                if not os.path.exists(target_path):
                    try:
                        shutil.copy2(match, target_path)
                        print(f"MIGRATION: Successfully imported metadata {fname} from {match}")
                    except Exception as e:
                        print(f"MIGRATION ERROR: Failed to move metadata {fname}: {e}")

    @staticmethod
    def get_all_projects() -> List[Dict[str, Any]]:
        ProjectRepository._ensure_file()
        _, projects_file = ProjectRepository._get_paths()
        try:
            with open(projects_file, 'r') as f:
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
            
        _, projects_file = ProjectRepository._get_paths()
        with open(projects_file, 'w') as f:
            json.dump(projects, f, indent=2)
            
        return project_data

    @staticmethod
    def delete_project(project_id: str) -> bool:
        projects = ProjectRepository.get_all_projects()
        initial_len = len(projects)
        projects = [p for p in projects if p.get("id") != project_id]
        
        if len(projects) < initial_len:
            _, projects_file = ProjectRepository._get_paths()
            with open(projects_file, 'w') as f:
                json.dump(projects, f, indent=2)
            return True
        return False
        
    @staticmethod
    def delete_all_projects() -> bool:
        ProjectRepository._ensure_file()
        _, projects_file = ProjectRepository._get_paths()
        with open(projects_file, 'w') as f:
            json.dump([], f, indent=2)
        return True
        
    @staticmethod
    def get_project_by_id(project_id: str) -> Optional[Dict[str, Any]]:
        projects = ProjectRepository.get_all_projects()
        for p in projects:
            if p.get("id") == project_id:
                return p
        return None
