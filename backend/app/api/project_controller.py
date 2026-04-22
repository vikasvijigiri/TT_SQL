from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from app.repositories.project_repo import ProjectRepository
from app.core.settings import settings
from app.db.sql_repo import DBRepository
from app.utils.discovery import SQLDiscoveryService

router = APIRouter(prefix="/api/projects", tags=["Projects"])
discovery_router = APIRouter(prefix="/api/discovery", tags=["Discovery"])

class DiscoveryConfig(BaseModel):
    host: str = ""
    port: str = "5432"
    user: str = ""
    password: str = ""
    database: str = ""
    path: str = "" # For SQLite

class ProjectCreate(BaseModel):
    name: str

class ProjectConnection(BaseModel):
    db_type: str  # 'postgres', 'sqlite', 'bigquery', 'snowflake'
    db_name: str  # Schema/Dataset/Database name
    database: str = "" # Postgres DB name OR BQ Project ID OR Snowflake DB name
    host: str = "" # Host/Account
    port: str = "5432"
    user: str = ""
    password: str = ""
    sqlite_path: str = ""
    qdrant_collection: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    
    # BigQuery specific
    bq_credentials_path: str = ""
    
    # Snowflake specific
    sf_warehouse: str = ""
    sf_role: str = ""
    db_root: str = "" # For Bulk SQLite

    # LLM Settings
    llm_provider: str = "" # 'bedrock', 'openai', 'anthropic', etc.
    llm_model: str = ""
    llm_api_base: str = ""
    llm_api_key: str = ""
    embedding_model: str = ""

    # Bedrock Specific
    bedrock_region: str = ""
    bedrock_access_key: str = ""
    bedrock_secret_key: str = ""

@router.get("/active")
async def get_active_project(user_email: str = None, user_name: str = None):
    """
    Returns the currently active project for the specific user.
    """
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    
    # 1. Resolve active project from user's persistent registry state
    from app.repositories.user_repo import UserRepository
    user_state = UserRepository.get_state(user_slug)
    active_id = user_state.get("activeProjectId")
    
    # 2. Fallback to global singleton (backward compatibility)
    if not active_id:
        active_id = settings.ACTIVE_PROJECT_ID
        
    if not active_id:
        return {"active_project_id": None, "project": None}
    
    project = ProjectRepository.get_project_by_id(active_id, user_slug=user_slug)
    
    # Clean up stale active IDs if the project folder was moved/deleted
    if not project:
        # If it was the global setting, reset it
        if active_id == settings.ACTIVE_PROJECT_ID:
            settings.reset()
        return {"active_project_id": None, "project": None}
        
    return {"active_project_id": active_id, "project": project}

@router.get("")
async def list_projects(user_email: str = None, user_name: str = None):
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    return ProjectRepository.get_all_projects(user_slug=user_slug)

@router.post("")
async def create_project(project_in: ProjectCreate, user_email: str = None, user_name: str = None):
    """
    Create a new project.
    Production standard: Validates input, handles errors gracefully, returns meaningful feedback.
    """
    try:
        from app.repositories.paths import get_user_slug
        
        # Validate input
        if not project_in.name or not project_in.name.strip():
            raise HTTPException(
                status_code=400, 
                detail="Project name is required and cannot be empty"
            )
        
        user_slug = get_user_slug(user_email=user_email, user_name=user_name)
        project_data = project_in.dict()
        project_data["connection"] = None
        
        # Attempt to save project
        saved_project = ProjectRepository.save_project(project_data, user_slug=user_slug)
        
        return {
            "status": "success",
            "project": saved_project,
            "message": f"Project '{saved_project['name']}' created successfully"
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid project data: {str(e)}"
        )
    except IOError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save project: {str(e)}"
        )
    except Exception as e:
        import traceback
        print(f"Unexpected error in create_project: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error creating project: {str(e)}"
        )

@router.put("/{project_id}/connection")
async def update_project_connection(project_id: str, connection_in: ProjectConnection, user_email: str = None, user_name: str = None):
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["connection"] = connection_in.dict()
    return ProjectRepository.save_project(project, user_slug=user_slug)

@router.delete("/{project_id}")
async def delete_project(project_id: str, user_email: str = None, user_name: str = None):
    """
    Delete a project and all associated data.
    Production standard: Validates project exists, handles errors gracefully.
    """
    try:
        from app.repositories.paths import get_user_slug
        
        if not project_id or not project_id.strip():
            raise HTTPException(status_code=400, detail="Project ID is required")
        
        user_slug = get_user_slug(user_email=user_email, user_name=user_name)
        
        # If the active project is being deleted, reset settings
        if settings.ACTIVE_PROJECT_ID == project_id:
            settings.reset()

        success = ProjectRepository.delete_project(project_id, user_slug=user_slug)
        if not success:
            raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
        
        return {
            "status": "success",
            "message": f"Project deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Unexpected error in delete_project: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )

@router.delete("")
async def delete_all_projects():
    # Reset active project in memory
    settings.reset()
    
    ProjectRepository.delete_all_projects()
    return {"status": "success"}

@router.post("/{project_id}/activate")
async def activate_project(project_id: str, user_email: str = None, user_name: str = None):
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.get("connection"):
        raise HTTPException(status_code=400, detail="Project has no database connection configured")

    # In-memory activation: mutate the settings singleton directly
    settings.reload_from_project(project)

    # Record activity
    ProjectRepository.save_project(project, user_slug=user_slug)

    return {
        "status": "success",
        "message": f"Activated project '{project['name']}'",
        "project": project
    }

@router.post("/{project_id}/test")
async def test_project_connection(project_id: str, user_email: str = None, user_name: str = None):
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    
    project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
    if not project or not project.get("connection"):
        raise HTTPException(status_code=404, detail="Project or connection not found")

    conn = project["connection"]
    db_type = conn.get("db_type", "postgres").lower()
    
    try:
        # 1. Handle Bulk SQLite Test
        if db_type == "bulk_sqlite":
            # Fallback for older projects where db_root might have been saved as sqlite_path
            db_root = conn.get("db_root") or conn.get("sqlite_path")
            if not db_root:
                return {"status": "error", "connected": False, "message": "Bulk root directory not configured.", "tables": []}
            
            if not os.path.exists(db_root) or not os.path.isdir(db_root):
                return {"status": "error", "connected": False, "message": f"Directory not found: {db_root}", "tables": []}
            
            # Use discovery service to find files
            files = SQLDiscoveryService.discover_sqlite_files(db_root)
            if not files:
                return {"status": "error", "connected": False, "message": "No database files (.sqlite, .db) found in the root directory.", "tables": []}
                
            # Filter for non-empty files
            valid_files = []
            for f in files:
                f_path = os.path.join(db_root, f)
                if os.path.getsize(f_path) > 0:
                    valid_files.append(f)
            
            if not valid_files:
                return {"status": "error", "connected": False, "message": "Databases found but they all appear to be empty or corrupted (size 0).", "tables": []}
                
            return {
                "status": "success",
                "connected": True,
                "tables": valid_files, # Return filenames as 'tables' for UI feedback
                "message": f"Successfully validated root directory. Found {len(valid_files)} non-empty databases."
            }

        # 2. Standard DB Test
        connected = DBRepository.check_connection(db_type=db_type, user_slug=user_slug, active_conn=project["connection"])
        if not connected:
             return {"status": "error", "connected": False, "message": "Failed to connect to database.", "tables": []}

        # 2. Get table list using standard query execution
        if db_type in ["postgres", "postgresql"]:
            query = "SELECT table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY table_name;"
        elif db_type == "sqlite":
            query = "SELECT name FROM sqlite_master WHERE type='table';"
        elif db_type == "bigquery":
             query = f"SELECT table_name FROM `{conn.get('database')}.{conn.get('db_name')}.INFORMATION_SCHEMA.TABLES`"
        elif db_type == "snowflake":
            query = f"SELECT TABLE_NAME FROM {conn.get('database')}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{conn.get('db_name')}'"
        else:
            raise Exception(f"Unsupported database type for table discovery: {db_type}")

        result = DBRepository.execute_query(query, user_slug=user_slug)
        if result.error_message:
            raise Exception(result.error_message)

        tables = [row[0] for row in result.rows if row] if result.rows else []

        return {
            "status": "success",
            "connected": True,
            "tables": tables,
            "message": f"Successfully connected and found {len(tables)} tables"
        }

    except Exception as e:
        return {"status": "error", "connected": False, "message": str(e), "tables": []}

@router.post("/deactivate")
async def deactivate_project():
    # Clear active project from settings
    settings.reset()

    return {
        "status": "success",
        "message": "Project deactivated successfully",
        "active_project_id": None
    }

# --- Discovery Endpoints ---

@discovery_router.post("/databases")
async def discover_databases(config: DiscoveryConfig):
    """List all available databases on a PostgreSQL server."""
    try:
        dbs = SQLDiscoveryService.discover_databases(config.dict())
        return {"status": "success", "databases": dbs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@discovery_router.post("/schemas")
async def discover_schemas(config: DiscoveryConfig):
    """List all user schemas in a specific database."""
    try:
        schemas = SQLDiscoveryService.discover_schemas(config.dict(), config.database)
        return {"status": "success", "schemas": schemas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@discovery_router.post("/sqlite")
async def discover_sqlite(config: DiscoveryConfig):
    """List all SQLite files in a local directory."""
    try:
        files = SQLDiscoveryService.discover_sqlite_files(config.path)
        return {"status": "success", "files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))