from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from app.domain.projects.repository import ProjectRepository
from app.domain.users.repository import UserRepository
from app.infrastructure.storage.path_manager import StorageManager
from app.core.config.settings import settings
from app.infrastructure.database.manager import DatabaseManager

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str

class ConnectionUpdate(BaseModel):
    db_type: str
    db_name: str
    sqlite_path: Optional[str] = None
    # ... extensible for other engines

@router.get("/active")
async def get_active(user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    state = UserRepository().get_state(slug)
    active_id = state.get("activeProjectId") or settings.ACTIVE_PROJECT_ID
    
    if not active_id: return {"project": None}
    project = ProjectRepository().get_project_by_id(active_id, slug)
    return {"project": project}

@router.get("/")
async def list_projects(user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    return ProjectRepository().get_all_projects(slug)

@router.post("/")
async def create(data: ProjectCreate, user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    project = {"id": StorageManager.get_instance_id(), "name": data.name, "connection": {}}
    ProjectRepository().save_project(project, slug)
    return project

@router.post("/{project_id}/activate")
async def activate(project_id: str, user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    repo = ProjectRepository()
    project = repo.get_project_by_id(project_id, slug)
    if not project: raise HTTPException(404, "Project not found")
    
    UserRepository().set_active_project(slug, project_id)
    settings.reload_from_project(project)
    return {"message": "Project activated"}

@router.post("/{project_id}/test")
async def test_connection(project_id: str, user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    project = ProjectRepository().get_project_by_id(project_id, slug)
    if not project: raise HTTPException(404, "Project not found")
    
    try:
        conn = DatabaseManager.get_connector(slug, connection_override=project.get("connection"))
        is_ok = conn.check_connection()
        return {"connected": is_ok}
    except Exception as e:
        return {"connected": False, "error": str(e)}

@router.delete("/{project_id}")
async def delete_project(project_id: str, user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    repo = ProjectRepository()
    project = repo.get_project_by_id(project_id, slug)
    if not project: raise HTTPException(404, "Project not found")
    
    repo.delete_project(project.get("_slug"), slug)
    return {"status": "success"}
