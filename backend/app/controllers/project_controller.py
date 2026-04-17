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
    
    # BigQuery specific
    bq_credentials_path: str = ""
    
    # Snowflake specific
    sf_warehouse: str = ""
    sf_role: str = ""

@router.get("/active")
async def get_active_project():
    active_id = settings.ACTIVE_PROJECT_ID
    if not active_id:
        return {"active_project_id": None, "project": None}
    
    project = ProjectRepository.get_project_by_id(active_id)
    
    # Clean up stale active project ID if project not found
    if not project:
        settings.reset()
        os.environ.pop("ACTIVE_PROJECT_ID", None)
        return {"active_project_id": None, "project": None}
        
    return {"active_project_id": active_id, "project": project}

@router.get("")
async def list_projects():
    return ProjectRepository.get_all_projects()

@router.post("")
async def create_project(project_in: ProjectCreate):
    project_data = project_in.dict()
    project_data["connection"] = None
    return ProjectRepository.save_project(project_data)

@router.put("/{project_id}/connection")
async def update_project_connection(project_id: str, connection_in: ProjectConnection):
    project = ProjectRepository.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project["connection"] = connection_in.dict()
    return ProjectRepository.save_project(project)

@router.delete("/{project_id}")
async def delete_project(project_id: str):
    # If the active project is being deleted, reset settings
    if settings.ACTIVE_PROJECT_ID == project_id:
        settings.reset()
        os.environ.pop("ACTIVE_PROJECT_ID", None)

    success = ProjectRepository.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "success"}

@router.delete("")
async def delete_all_projects():
    # Reset active project in memory
    settings.reset()
    os.environ.pop("ACTIVE_PROJECT_ID", None)
    
    ProjectRepository.delete_all_projects()
    return {"status": "success"}

@router.post("/{project_id}/activate")
async def activate_project(project_id: str):
    project = ProjectRepository.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.get("connection"):
        raise HTTPException(status_code=400, detail="Project has no database connection configured")

    # In-memory activation: mutate the settings singleton directly
    settings.reload_from_project(project)
    os.environ["ACTIVE_PROJECT_ID"] = project_id

    return {
        "status": "success",
        "message": f"Activated project '{project['name']}'",
        "project": project
    }

@router.post("/{project_id}/test")
async def test_project_connection(project_id: str):
    project = ProjectRepository.get_project_by_id(project_id)
    if not project or not project.get("connection"):
        raise HTTPException(status_code=404, detail="Project or connection not found")

    conn = project["connection"]
    db_type = conn.get("db_type", "postgres")
    schema_name = conn.get("db_name", "public")

    database_name = conn.get("database", "postgres")

    test_conn = {
        "db_type": db_type,
        "schema": schema_name,
        "host": conn.get("host", ""),
        "port": conn.get("port", "5432"),
        "database": database_name,
        "user": conn.get("user", ""),
        "password": conn.get("password", ""),
        "sqlite_path": conn.get("sqlite_path", ""),
    }

    try:
        _type = db_type.lower()
        if _type in ["postgres", "postgresql"]:
            query = f"SELECT table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY table_name;"
            result = DBRepository._execute_postgres(query, schema_name, test_conn)
        elif _type == "sqlite":
            db_path = conn.get("sqlite_path", "")
            query = "SELECT name FROM sqlite_master WHERE type='table';"
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
