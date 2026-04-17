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
                slug = item.name
                size_bytes, file_count, breakdown = StorageService._calculate_dir_stats(item)
                
                stats_list.append({
                    "slug": slug,
                    "name": slug_map.get(slug, slug), # Use slug if no registry entry (orphaned)
                    "is_orphaned": slug not in slug_map,
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
        breakdown = {"log": 0, "sql": 0, "csv": 0, "other": 0}
        
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = Path(root) / f
                try:
                    size = os.path.getsize(fp)
                    total_size += size
                    total_files += 1
                    
                    # Simple extension-based breakdown
                    ext = fp.suffix.lower()
                    if ext == '.md': breakdown["log"] += size
                    elif ext == '.sql': breakdown["sql"] += size
                    elif ext == '.csv': breakdown["csv"] += size
                    else: breakdown["other"] += size
                except: continue
        
        # Convert breakdown to MB
        for k in breakdown:
            breakdown[k] = round(breakdown[k] / (1024 * 1024), 2)
            
        return total_size, total_files, breakdown
