from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Form
from typing import Optional, List, Any, Dict, Union
import os
import shutil
from app.repositories.paths import PROJECT_ROOT

from app.db.sql_repo import DBRepository
from app.core.settings import settings
from app.services.batch_service import BatchService

router = APIRouter(prefix="/api/data", tags=["Data"])

# Dataset uploads strictly removed as part of directory simplification.


@router.post("/upload-env")
async def upload_env(file: UploadFile = File(...)):
    """
    Upload and overwrite the .env file.
    """
    # Path to the backend .env
    env_path = PROJECT_ROOT / "backend" / ".env"
    
    # If PROJECT_ROOT is already backend
    if not env_path.parent.exists():
         env_path = PROJECT_ROOT / ".env"

    try:
        with open(env_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"status": "success", "message": ".env updated. Server should reload automatically."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update .env: {e}")

@router.get("/schema")
async def get_schema(user_email: str = None, user_name: str = None):
    """
    Fetch the database schema (tables, columns, foreign keys).
    """
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    active = DBRepository._get_active_connection(user_slug=user_slug)
    
    # Validate that an active connection exists
    if not active or not active.get("db_type"):
        raise HTTPException(status_code=400, detail="No active database connection. Please select or create a project first.")
    
    db_type = active["db_type"]
    schema_name = active["schema"]

    if db_type.lower() in ["postgres", "postgresql"]:
        # Get Tables
        tables_res = DBRepository.execute_query(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_name}';",
            db_type=db_type, db_name=schema_name, user_slug=user_slug
        )
        if tables_res.error_message: raise HTTPException(status_code=500, detail=tables_res.error_message)
        tables = [row[0] for row in tables_res.rows]

        # Get Columns
        cols_query = f"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = '{schema_name}';"
        cols_res = DBRepository.execute_query(cols_query, db_type=db_type, db_name=schema_name, user_slug=user_slug)
        if cols_res.error_message: raise HTTPException(status_code=500, detail=cols_res.error_message)
        
        columns = {}
        for r in cols_res.rows:
            t_name, c_name, d_type = r
            if t_name not in columns: columns[t_name] = []
            columns[t_name].append({"name": c_name, "type": d_type})

        # Get Foreign Keys
        fk_query = f"""
        SELECT
            tc.table_name, 
            kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='{schema_name}';
        """
        fk_res = DBRepository.execute_query(fk_query, db_type=db_type, db_name=schema_name, user_slug=user_slug)
        
        foreign_keys = []
        if not fk_res.error_message:
            for r in fk_res.rows:
                foreign_keys.append({
                    "table": r[0],
                    "column": r[1],
                    "foreign_table": r[2],
                    "foreign_column": r[3]
                })

        return {
            "tables": tables,
            "columns": columns,
            "foreign_keys": foreign_keys
        }
    else:
        # SQLite implementation (fallback)
        sqlite_path = active["sqlite_path"]
        tables_res = DBRepository.execute_query("SELECT name FROM sqlite_master WHERE type='table';", db_type="sqlite", db_name="", db_path=sqlite_path, user_slug=user_slug)
        if tables_res.error_message: raise HTTPException(status_code=500, detail=tables_res.error_message)
        tables = [row[0] for row in tables_res.rows]
        
        columns = {}
        foreign_keys = []
        for t in tables:
            c_res = DBRepository.execute_query(f"PRAGMA table_info({t});", db_type="sqlite", db_name="", db_path=sqlite_path, user_slug=user_slug)
            columns[t] = [{"name": r[1], "type": r[2]} for r in c_res.rows] if not c_res.error_message else []
            
            fk_res = DBRepository.execute_query(f"PRAGMA foreign_key_list({t});", db_type="sqlite", db_name="", db_path=sqlite_path, user_slug=user_slug)
            if not fk_res.error_message:
                for r in fk_res.rows:
                    foreign_keys.append({
                        "table": t,
                        "column": r[3],
                        "foreign_table": r[2],
                        "foreign_column": r[4]
                    })
                    
        return {
            "tables": tables,
            "columns": columns,
            "foreign_keys": foreign_keys
        }

@router.get("/preview/{table_name}")
async def preview_table(table_name: str, user_email: str = None, user_name: str = None):
    """
    Fetch the top 50 rows of a table for previewing.
    """
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    active = DBRepository._get_active_connection(user_slug=user_slug)
    
    # Validate that an active connection exists
    if not active or not active.get("db_type"):
        raise HTTPException(status_code=400, detail="No active database connection. Please select or create a project first.")
    
    db_type = active["db_type"]
    schema_name = active["schema"]
    
    # Basic sanitization
    table_name = "".join(c for c in table_name if c.isalnum() or c in ['_', '-'])
    
    if db_type.lower() in ["postgres", "postgresql"]:
        query = f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT 50;'
        res = DBRepository.execute_query(query, db_type=db_type, db_name=schema_name, user_slug=user_slug)
    else:
        query = f'SELECT * FROM "{table_name}" LIMIT 50;'
        res = DBRepository.execute_query(query, db_type="sqlite", db_name="", db_path=active["sqlite_path"], user_slug=user_slug)
        
    if res.error_message:
        raise HTTPException(status_code=500, detail=res.error_message)
        
    # Format rows for JSON serialization
    formatted_rows = []
    for row in res.rows:
        formatted_row = []
        for val in row:
            if hasattr(val, 'isoformat'):
                formatted_row.append(val.isoformat())
            else:
                try:
                    import decimal
                    if isinstance(val, decimal.Decimal): val = float(val)
                except:
                    pass
                formatted_row.append(val)
        formatted_rows.append(formatted_row)
        
    return {
        "columns": res.columns,
        "rows": formatted_rows
    }

@router.get("/logs/history")
async def get_execution_history(instance_id: str = None, user_email: str = None, project_id: str = None):
    """
    Fetch the execution log. Handles both cumulative and instance-specific logs.
    """
    from app.repositories.paths import get_user_slug, get_model_results_dir, InstancePaths
    from app.core.settings import settings
    
    user_slug = get_user_slug(user_email=user_email)
    p_id = project_id or settings.ACTIVE_PROJECT_ID or "default"
    model_dir = get_model_results_dir(settings.LLM_MODEL, user_slug, p_id)
    
    # Priority 1: Specific Instance Log
    if instance_id and instance_id != 'unknown':
        log_path = InstancePaths.log(instance_id, model_dir)
    else:
        # Priority 2: Generic project log/index (if exists)
        log_path = model_dir / "execution_log.md"
    
    if not os.path.exists(log_path):
        return {"content": "No execution history found yet."}
    
    try:
        # Read the file
        file_size = os.path.getsize(log_path)
        with open(log_path, "r", encoding="utf-8") as f:
            # If it's a huge cumulative log, truncate. If specific qXXX.md, send all.
            if not instance_id and file_size > 500000:
                f.seek(file_size - 500000)
                f.readline()
                content = "--- (Earlier logs truncated for performance) ---\n\n" + f.read()
            else:
                content = f.read()
                
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log: {e}")

@router.get("/storage/workspaces")
async def get_storage_stats(user_email: str = None, user_name: str = None):
    """
    Returns workspace registry stats.
    """
    from app.repositories.paths import get_user_slug
    from app.repositories.project_repo import ProjectRepository
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    return ProjectRepository.get_storage_stats(user_slug=user_slug)

@router.delete("/cleanup/workspace/{slug}")
async def wipe_workspace(slug: str, user_email: str = None, user_name: str = None):
    """
    Wipes all analytical results for a workspace.
    """
    from app.repositories.paths import get_user_slug
    from app.repositories.project_repo import ProjectRepository
    # Note: the slug passed in URL is the PROJECT slug, but we need the USER slug for pathing
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    success = ProjectRepository.wipe_workspace_results(slug, user_slug=user_slug)
    return {"status": "success" if success else "failed"}

# Intermediate Query caching has been strictly removed. Logic formerly located here is deleted.

@router.delete("/cleanup/project")
async def cleanup_project(user_email: str = None, user_name: str = None):
    """
    Wipes ALL analytical results for the ACTIVE project.
    """
    from app.repositories.paths import get_user_slug
    from app.repositories.project_repo import ProjectRepository
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    success = ProjectRepository.cleanup_active_project_results(user_slug=user_slug)
    return {"status": "success" if success else "failed"}

@router.delete("/cleanup/session")
async def cleanup_session(period: str = "today", user_email: str = None, user_name: str = None):
    """
    Wipes recently generated results from the ACTIVE project.
    """
    from app.repositories.paths import get_user_slug
    from app.repositories.project_repo import ProjectRepository
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    success = ProjectRepository.cleanup_period_results(period, user_slug=user_slug)
    return {"status": "success" if success else "failed"}

# Batch processing endpoints strictly removed.

