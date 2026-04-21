import os
from pathlib import Path
from typing import List, Dict, Any
from app.repositories.registry.project_repo import ProjectRepository

class StorageService:
    """
    Service to perform cross-project storage analytics and data management.
    """

    @staticmethod
    def get_all_storage_stats() -> List[Dict[str, Any]]:
        """
        Scans the results directory and calculates stats for every project folder.
        Correlates folders with friendly names from the Project Registry.
        """
        from app.repositories.registry.paths import DATA_DIR
        results_root = DATA_DIR / "results"
        
        if not results_root.exists():
            return []

        projects = ProjectRepository.get_all_projects()
        # Map slug to friendly name
        slug_map = {}
        for p in projects:
            # Replicate get_active_project_slug logic for matching
            name = p.get("name", p.get("id"))
            import re
            slug = re.sub(r'[^a-zA-Z0-9]', '_', name).lower()
            slug_map[slug] = name

        stats_list = []
        for item in results_root.iterdir():
            if item.is_dir():
                folder_name = item.name
                
                # Try to extract the project slug part (last part after underscore)
                # This helps match friendly names from the registry even with user prefixes
                project_slug = folder_name.split('_')[-1] if '_' in folder_name else folder_name
                
                size_bytes, file_count, breakdown = StorageService._calculate_dir_stats(item)
                
                stats_list.append({
                    "slug": folder_name,
                    "name": slug_map.get(project_slug, slug_map.get(folder_name, folder_name)),
                    "is_orphaned": project_slug not in slug_map and folder_name not in slug_map,
                    "size_mb": round(size_bytes / (1024 * 1024), 2),
                    "file_count": file_count,
                    "breakdown": breakdown
                })
        
        # Sort by size descending
        return sorted(stats_list, key=lambda x: x["size_mb"], reverse=True)

    @staticmethod
    def _calculate_dir_stats(path: Path):
        total_size = 0
        total_files = 0
        breakdown = {"logs": 0, "sql": 0, "csv": 0, "metadata": 0, "other": 0}
        
        for root, dirs, files in os.walk(path):
            current_path = Path(root)
            relative_root = current_path.relative_to(path)
            
            for f in files:
                fp = current_path / f
                try:
                    size = os.path.getsize(fp)
                    total_size += size
                    total_files += 1
                    
                    # Category mapping based on subfolder or extension
                    parts = relative_root.parts
                    if "logs" in parts:
                        breakdown["logs"] += size
                    elif "sql" in parts:
                        breakdown["sql"] += size
                    elif "csv" in parts:
                        breakdown["csv"] += size
                    elif "metadata_extracts" in parts:
                        breakdown["metadata"] += size
                    else:
                        # Fallback to extension
                        ext = fp.suffix.lower()
                        if ext == '.md': breakdown["logs"] += size
                        elif ext == '.sql': breakdown["sql"] += size
                        elif ext == '.csv': breakdown["csv"] += size
                        elif ext == '.json' and "metadata" in f.lower(): breakdown["metadata"] += size
                        else: breakdown["other"] += size
                except: continue
        
        # Convert breakdown to MB
        for k in breakdown:
            breakdown[k] = round(breakdown[k] / (1024 * 1024), 2)
            
        return total_size, total_files, breakdown
