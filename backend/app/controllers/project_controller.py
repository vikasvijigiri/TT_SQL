from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from app.repositories.registry.project_repo import ProjectRepository
from app.repositories.config import settings
from app.repositories.connectors.sql_repo import DBRepository

router = APIRouter(prefix="/api/projects", tags=["Projects"])

class ProjectCreate(BaseModel):
    name: str

class ProjectConnection(BaseModel):
    db_type: str  # 'postgres', 'sqlite', 'bigquery', 'snowflake'
    db_name: str  # Schema/Dataset/Database name
    database: str = "postgres" # Postgres DB name OR BQ Project ID OR Snowflake DB name
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

@router.get("/active")
async def get_active_project(user_email: str = None, user_name: str = None):
    """
    Returns the currently active project for the specific user.
    """
    from app.repositories.registry.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    
    # 1. Resolve active project from user's persistent registry state
    from app.repositories.registry.user_repo import UserRepository
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
            os.environ.pop("ACTIVE_PROJECT_ID", None)
        return {"active_project_id": None, "project": None}
        
    return {"active_project_id": active_id, "project": project}

@router.get("")
async def list_projects(user_email: str = None, user_name: str = None):
    from app.repositories.registry.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    return ProjectRepository.get_all_projects(user_slug=user_slug)

@router.post("")
async def create_project(project_in: ProjectCreate, user_email: str = None, user_name: str = None):
    """
    Create a new project.
    Production standard: Validates input, handles errors gracefully, returns meaningful feedback.
    """
    try:
        from app.repositories.registry.paths import get_user_slug
        
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
    from app.repositories.registry.paths import get_user_slug
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
        from app.repositories.registry.paths import get_user_slug
        
        if not project_id or not project_id.strip():
            raise HTTPException(status_code=400, detail="Project ID is required")
        
        user_slug = get_user_slug(user_email=user_email, user_name=user_name)
        
        # If the active project is being deleted, reset settings
        if settings.ACTIVE_PROJECT_ID == project_id:
            settings.reset()
            os.environ.pop("ACTIVE_PROJECT_ID", None)

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
    os.environ.pop("ACTIVE_PROJECT_ID", None)
    
    ProjectRepository.delete_all_projects()
    return {"status": "success"}

@router.post("/{project_id}/activate")
async def activate_project(project_id: str, user_email: str = None, user_name: str = None):
    from app.repositories.registry.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.get("connection"):
        raise HTTPException(status_code=400, detail="Project has no database connection configured")

    # In-memory activation: mutate the settings singleton directly
    settings.reload_from_project(project)
    os.environ["ACTIVE_PROJECT_ID"] = project_id

    # Record activity
    ProjectRepository.save_project(project, user_slug=user_slug)

    return {
        "status": "success",
        "message": f"Activated project '{project['name']}'",
        "project": project
    }

@router.post("/{project_id}/test")
async def test_project_connection(project_id: str, user_email: str = None, user_name: str = None):
    from app.repositories.registry.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    
    project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
    if not project or not project.get("connection"):
        raise HTTPException(status_code=404, detail="Project or connection not found")

    conn = project["connection"]
    db_type = conn.get("db_type", "postgres")
    database_name = conn.get("database", "postgres")
    schema_name = conn.get("db_name", database_name)

    test_conn = {
        "db_type": db_type,
        "schema": schema_name,
        "host": conn.get("host", ""),
        "port": conn.get("port", "5432"),
        "database": database_name,
        "user": conn.get("user", ""),
        "password": conn.get("password", ""),
        "sqlite_path": conn.get("sqlite_path", ""),
        "bq_credentials_path": conn.get("bq_credentials_path", ""),
        "sf_warehouse": conn.get("sf_warehouse", ""),
        "sf_role": conn.get("sf_role", ""),
    }

    try:
        _type = db_type.lower()
        if _type in ["postgres", "postgresql"]:
            query = f"SELECT table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY table_name;"
            result = DBRepository._execute_postgres(query, schema_name, test_conn)
        elif _type == "sqlite":
            db_path = conn.get("sqlite_path", "")
            query = "SELECT name FROM sqlite_master WHERE type='table';"
            # Use direct SQLite execution without needing active project
            result = DBRepository._execute_sqlite(query, db_path)
        elif _type == "bigquery":
            # Add fields for BQ test
            test_conn["bq_credentials_path"] = conn.get("bq_credentials_path", "")
            query = f"SELECT table_name FROM `{test_conn['database']}.{test_conn['schema']}.INFORMATION_SCHEMA.TABLES`"
            result = DBRepository._execute_bigquery(query, test_conn)
        elif _type == "snowflake":
            # Add fields for Snowflake test
            test_conn["sf_warehouse"] = conn.get("sf_warehouse", "")
            test_conn["sf_role"] = conn.get("sf_role", "")
            query = f"SELECT TABLE_NAME FROM {test_conn['database']}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{test_conn['schema']}'"
            result = DBRepository._execute_snowflake(query, test_conn)
        else:
            raise Exception(f"Unsupported database type: {db_type}")

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

    # Remove from environment if set
    import os
    os.environ.pop("ACTIVE_PROJECT_ID", None)

    return {
        "status": "success",
        "message": "Project deactivated successfully",
        "active_project_id": None
    }