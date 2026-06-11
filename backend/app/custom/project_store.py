"""
project_store.py
----------------
File-based project repository for Custom Project workspaces.

Storage layout:
  backend/custom_projects/
    settings.json                   ← global LLM / global settings
    {project_id}/
      project.json                  ← project metadata + connection config
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.core.config import BACKEND_DIR

CUSTOM_PROJECTS_DIR: Path = BACKEND_DIR / "custom_projects"
SETTINGS_FILE: Path = CUSTOM_PROJECTS_DIR / "settings.json"

_DEFAULT_SETTINGS: Dict[str, Any] = {
    "llm_provider": "anthropic",
    "llm_model": "",
    "llm_api_base": "",
    "embedding_model": "",
    "bedrock_region": "",
    "bedrock_access_key": "",
    "bedrock_secret_key": "",
    "qdrant_url": "",
    "qdrant_api_key": "",
}


def _ensure_dirs() -> None:
    CUSTOM_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


# ── Project helpers ───────────────────────────────────────────────────────────

def list_projects() -> List[Dict[str, Any]]:
    _ensure_dirs()
    results: List[Dict[str, Any]] = []
    for p in sorted(CUSTOM_PROJECTS_DIR.iterdir()):
        if p.is_dir():
            pf = p / "project.json"
            if pf.exists():
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        results.append(json.load(f))
                except Exception:
                    pass
    return results


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    _ensure_dirs()
    pf = CUSTOM_PROJECTS_DIR / project_id / "project.json"
    if not pf.exists():
        return None
    try:
        with open(pf, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_project(data: Dict[str, Any]) -> None:
    project_dir = CUSTOM_PROJECTS_DIR / data["id"]
    project_dir.mkdir(parents=True, exist_ok=True)
    pf = project_dir / "project.json"
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def create_project(name: str) -> Dict[str, Any]:
    _ensure_dirs()
    project_id = str(uuid.uuid4())
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data: Dict[str, Any] = {
        "id": project_id,
        "name": name,
        "active": False,
        "connection": {},
        "created_at": now,
        "last_activity": now,
    }
    _save_project(data)
    return data


def update_connection(project_id: str, connection: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = get_project(project_id)
    if data is None:
        return None
    data["connection"] = connection
    data["last_activity"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_project(data)
    return data


def delete_project(project_id: str) -> bool:
    import shutil
    project_dir = CUSTOM_PROJECTS_DIR / project_id
    if not project_dir.exists():
        return False
    shutil.rmtree(str(project_dir), ignore_errors=True)
    return True


def set_active(project_id: str) -> Optional[Dict[str, Any]]:
    """Mark a project as active (and deactivate all others)."""
    for proj in list_projects():
        if proj["id"] != project_id and proj.get("active"):
            proj["active"] = False
            _save_project(proj)
    data = get_project(project_id)
    if data is None:
        return None
    data["active"] = True
    data["last_activity"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _save_project(data)
    return data


def deactivate_all() -> None:
    for proj in list_projects():
        if proj.get("active"):
            proj["active"] = False
            _save_project(proj)


def get_active_project() -> Optional[Dict[str, Any]]:
    for proj in list_projects():
        if proj.get("active"):
            return proj
    return None


# ── Settings helpers ──────────────────────────────────────────────────────────

def get_settings() -> Dict[str, Any]:
    _ensure_dirs()
    if not SETTINGS_FILE.exists():
        return dict(_DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return {**_DEFAULT_SETTINGS, **saved}
    except Exception:
        return dict(_DEFAULT_SETTINGS)


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs()
    merged = {**_DEFAULT_SETTINGS, **settings}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    return merged


def reset_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        SETTINGS_FILE.unlink()
    return dict(_DEFAULT_SETTINGS)


# ── Metadata directory for a project ─────────────────────────────────────────

def get_metadata_dir(project_id: str, dialect: str, db_name: str) -> Path:
    """Return the path where per-table JSON schema files are stored."""
    return CUSTOM_PROJECTS_DIR / project_id / "metadata" / dialect.lower() / db_name.upper()
