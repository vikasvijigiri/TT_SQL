from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.utils.discovery_service import SQLDiscoveryService

router = APIRouter(prefix="/api/discovery", tags=["Discovery"])

class ServerCredentials(BaseModel):
    host: str
    port: str = "5432"
    user: str
    password: str

class SchemaDiscoveryRequest(ServerCredentials):
    database: str

class SQLiteDiscoveryRequest(BaseModel):
    path: str

@router.post("/databases")
async def discover_databases(creds: ServerCredentials):
    """
    List databases on a server.
    """
    try:
        databases = SQLDiscoveryService.discover_databases(creds.dict())
        return {"databases": databases}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/schemas")
async def discover_schemas(req: SchemaDiscoveryRequest):
    """
    List schemas in a specific database.
    """
    try:
        schemas = SQLDiscoveryService.discover_schemas(req.dict(), req.database)
        return {"schemas": schemas}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/sqlite")
async def discover_sqlite(req: SQLiteDiscoveryRequest):
    """
    List SQLite files in a local directory.
    """
    try:
        files = SQLDiscoveryService.discover_sqlite_files(req.path)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
