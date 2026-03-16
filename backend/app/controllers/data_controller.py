from fastapi import APIRouter, HTTPException, UploadFile, File
import os
import shutil
from app.repositories.registry.paths import INPUT_QUERIES_DIR, PROJECT_ROOT
from app.repositories.connectors.sql_repo import DBRepository
from app.repositories.config import settings

router = APIRouter(prefix="/api/data", tags=["Data"])

@router.post("/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    """
    Upload a JSONL dataset file.
    """
    if not file.filename.endswith(('.jsonl', '.json')):
        raise HTTPException(status_code=400, detail="Only .jsonl or .json files are allowed")
    
    # Ensure directory exists
    os.makedirs(INPUT_QUERIES_DIR, exist_ok=True)
    
    # Sanitize and resolve path
    filename = os.path.basename(file.filename)
    dest_path = INPUT_QUERIES_DIR / filename
    
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {"filename": filename, "path": str(dest_path), "status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

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
async def get_schema():
    """
    Fetch the database schema (tables, columns, foreign keys).
    """
    db_type = settings.DB_TYPE
    schema_name = settings.SCHEMA

    if db_type.lower() in ["postgres", "postgresql"]:
        # Get Tables
        tables_res = DBRepository.execute_query(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_name}';",
            db_type=db_type, db_name=schema_name
        )
        if tables_res.error_message: raise HTTPException(status_code=500, detail=tables_res.error_message)
        tables = [row[0] for row in tables_res.rows]

        # Get Columns
        cols_query = f"SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = '{schema_name}';"
        cols_res = DBRepository.execute_query(cols_query, db_type=db_type, db_name=schema_name)
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
        fk_res = DBRepository.execute_query(fk_query, db_type=db_type, db_name=schema_name)
        
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
        sqlite_path = settings.SQLITE_DB_PATH
        tables_res = DBRepository.execute_query("SELECT name FROM sqlite_master WHERE type='table';", db_type="sqlite", db_name="", db_path=sqlite_path)
        if tables_res.error_message: raise HTTPException(status_code=500, detail=tables_res.error_message)
        tables = [row[0] for row in tables_res.rows]
        
        columns = {}
        foreign_keys = []
        for t in tables:
            c_res = DBRepository.execute_query(f"PRAGMA table_info({t});", db_type="sqlite", db_name="", db_path=sqlite_path)
            columns[t] = [{"name": r[1], "type": r[2]} for r in c_res.rows] if not c_res.error_message else []
            
            fk_res = DBRepository.execute_query(f"PRAGMA foreign_key_list({t});", db_type="sqlite", db_name="", db_path=sqlite_path)
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
async def preview_table(table_name: str):
    """
    Fetch the top 50 rows of a table for previewing.
    """
    db_type = settings.DB_TYPE
    schema_name = settings.SCHEMA
    
    # Basic sanitization
    table_name = "".join(c for c in table_name if c.isalnum() or c in ['_', '-'])
    
    if db_type.lower() in ["postgres", "postgresql"]:
        query = f'SELECT * FROM "{schema_name}"."{table_name}" LIMIT 50;'
        res = DBRepository.execute_query(query, db_type=db_type, db_name=schema_name)
    else:
        query = f'SELECT * FROM "{table_name}" LIMIT 50;'
        res = DBRepository.execute_query(query, db_type="sqlite", db_name="", db_path=settings.SQLITE_DB_PATH)
        
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
