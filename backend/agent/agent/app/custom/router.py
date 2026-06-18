"""
router.py
---------
FastAPI router for Custom Project endpoints.
Mount at /api/custom in api.py:
    app.include_router(custom_router, prefix="/api/custom")

Endpoints
---------
  GET    /projects               Ã¢â‚¬â€œ list all custom projects
  POST   /projects               Ã¢â‚¬â€œ create a new project
  PUT    /projects/{id}/connection Ã¢â‚¬â€œ save DB connection settings
  DELETE /projects/{id}          Ã¢â‚¬â€œ delete a project
  POST   /projects/{id}/test     Ã¢â‚¬â€œ test the DB connection
  POST   /projects/{id}/activate Ã¢â‚¬â€œ activate project + extract schema
  POST   /projects/deactivate    Ã¢â‚¬â€œ deactivate the active project
  GET    /settings               Ã¢â‚¬â€œ read global LLM settings
  PUT    /settings               Ã¢â‚¬â€œ save global LLM settings
  DELETE /settings               Ã¢â‚¬â€œ reset global settings
  POST   /stream                 Ã¢â‚¬â€œ NL-to-SQL streaming (SSE)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.app.core.config import RESULTS_DIR
from agent.app.core.connection import parse_connection
from agent.app.custom import project_store as store
from agent.app.custom.connection_bridge import (
    make_executor,
    patch_orchestrator_executor,
    project_to_connection_string,
)
from agent.app.custom.schema_extractor import SchemaExtractor
from agent.app.utils.logger import logger

custom_router = APIRouter()


# Ã¢â€â‚¬Ã¢â€â‚¬ SSE helper Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

def _sse(type_: str, payload: Any) -> str:
    if isinstance(payload, str):
        data = json.dumps({"type": type_, "message": payload})
    elif isinstance(payload, dict):
        data = json.dumps({"type": type_, **payload})
    else:
        data = json.dumps({"type": type_, "data": payload})
    return f"data: {data}\n\n"


# Ã¢â€â‚¬Ã¢â€â‚¬ Pydantic models Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

class CreateProjectBody(BaseModel):
    name: str


class ProjectConnection(BaseModel):
    db_type: str = ""
    db_name: str = ""
    database: str = ""
    host: str = ""
    port: Any = ""
    user: str = ""
    password: str = ""
    sqlite_path: str = ""
    db_root: str = ""
    bq_credentials_path: str = ""
    sf_warehouse: str = ""
    sf_role: str = ""
    qdrant_collection: str = ""


class GlobalSettings(BaseModel):
    llm_provider: str = ""
    llm_model: str = ""
    llm_api_base: str = ""
    embedding_model: str = ""
    bedrock_region: str = ""
    bedrock_access_key: str = ""
    bedrock_secret_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""


class StreamRequest(BaseModel):
    query: str
    project_id: str
    session_id: str = ""
    use_rag: bool = True


# Ã¢â€â‚¬Ã¢â€â‚¬ Projects Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@custom_router.get("/projects")
def get_projects() -> List[Dict[str, Any]]:
    return store.list_projects()


@custom_router.post("/projects")
def create_project(body: CreateProjectBody) -> Dict[str, Any]:
    if not body.name.strip():
        raise HTTPException(400, "Project name cannot be empty.")
    return store.create_project(body.name.strip())


@custom_router.put("/projects/{project_id}/connection")
def save_connection(project_id: str, body: ProjectConnection) -> Dict[str, Any]:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    conn_dict = body.model_dump()
    updated = store.update_connection(project_id, conn_dict)
    return updated or {}


@custom_router.delete("/projects/{project_id}")
def delete_project(project_id: str) -> Dict[str, str]:
    if not store.delete_project(project_id):
        raise HTTPException(404, "Project not found.")
    return {"status": "deleted"}


@custom_router.post("/projects/{project_id}/test")
def test_connection(project_id: str) -> Dict[str, Any]:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")
    conn = project.get("connection") or {}
    if not conn or not conn.get("db_type"):
        return {"status": "error", "message": "No connection configured for this project.", "tables": []}

    try:
        project_to_connection_string(conn)  # validate only
    except Exception as e:
        return {"status": "error", "message": f"Invalid connection settings: {e}", "tables": []}

    try:
        executor = make_executor(conn)
        extractor = SchemaExtractor(executor)
        tables = extractor._list_tables()
        return {
            "status": "success",
            "connected": True,
            "message": f"Connected successfully. Found {len(tables)} table(s).",
            "tables": tables[:50],
        }
    except Exception as e:
        logger.error(f"[CustomRouter] Connection test failed: {e}")
        return {"status": "error", "connected": False, "message": str(e), "tables": []}


@custom_router.post("/projects/{project_id}/activate")
def activate_project(project_id: str) -> Dict[str, Any]:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    conn = project.get("connection") or {}
    if not conn or not conn.get("db_type"):
        raise HTTPException(400, "Project has no DB connection configured.")

    try:
        conn_str = project_to_connection_string(conn)
    except Exception as e:
        raise HTTPException(400, f"Invalid connection settings: {e}")

    conn_cfg = parse_connection(conn_str)
    metadata_dir = store.get_metadata_dir(project_id, conn_cfg.dialect, conn_cfg.db_name)

    # Extract schema if the metadata directory is empty
    existing_schemas = list(metadata_dir.glob("*.json")) if metadata_dir.exists() else []
    if not existing_schemas:
        try:
            executor = make_executor(conn)
            extractor = SchemaExtractor(executor)
            n = extractor.extract_to_dir(metadata_dir)
            logger.info(f"[CustomRouter] Schema extracted: {n} tables -> {metadata_dir}")
        except Exception as e:
            logger.error(f"[CustomRouter] Schema extraction failed: {e}")
            # Don't block activation Ã¢â‚¬â€ orchestrator will still attempt with empty schema

    activated = store.set_active(project_id)
    return {"status": "activated", "project": activated}


@custom_router.post("/projects/deactivate")
def deactivate_project() -> Dict[str, str]:
    store.deactivate_all()
    return {"status": "deactivated"}


# Ã¢â€â‚¬Ã¢â€â‚¬ Global settings Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@custom_router.get("/settings")
def get_settings() -> Dict[str, Any]:
    return store.get_settings()


@custom_router.put("/settings")
def save_settings(body: GlobalSettings) -> Dict[str, Any]:
    return store.save_settings(body.model_dump())


@custom_router.delete("/settings")
def reset_settings() -> Dict[str, Any]:
    return store.reset_settings()


# Ã¢â€â‚¬Ã¢â€â‚¬ NL-to-SQL streaming Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

@custom_router.post("/stream")
async def stream_query(body: StreamRequest) -> StreamingResponse:
    project = store.get_project(body.project_id)
    if project is None:
        raise HTTPException(404, "Project not found.")

    conn = project.get("connection") or {}
    if not conn or not conn.get("db_type"):
        raise HTTPException(400, "Project has no DB connection configured. Activate a project first.")

    try:
        conn_str = project_to_connection_string(conn)
    except Exception as e:
        raise HTTPException(400, f"Invalid connection settings: {e}")

    conn_cfg = parse_connection(conn_str)
    metadata_dir = store.get_metadata_dir(body.project_id, conn_cfg.dialect, conn_cfg.db_name)
    query_text = body.query.strip()

    # Deterministic instance_id for caching same query results
    q_hash = hashlib.md5(query_text.encode()).hexdigest()[:8]
    instance_id = f"custom_{body.project_id[:8]}_{q_hash}"

    async def event_stream():
        pipeline_events: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        result_container: Dict[str, Any] = {}

        def on_stage(stage: str, status: str) -> None:
            loop.call_soon_threadsafe(
                pipeline_events.put_nowait,
                {"stage": stage, "status": status},
            )

        def run_pipeline() -> None:
            from agent.app.core.orchestrator import SemanticDINOrchestrator

            # Ensure metadata exists before creating orchestrator
            existing = list(metadata_dir.glob("*.json")) if metadata_dir.exists() else []
            if not existing:
                try:
                    executor = make_executor(conn)
                    extractor = SchemaExtractor(executor)
                    extractor.extract_to_dir(metadata_dir)
                except Exception as ex:
                    logger.warning(f"[CustomRouter] On-demand schema extraction failed: {ex}")

            try:
                orchestrator = SemanticDINOrchestrator(
                    db_directory=str(metadata_dir),
                    connection_string=conn_str,
                )
                patch_orchestrator_executor(orchestrator, conn)
                result_container["sql"] = orchestrator.execute_query(
                    query_text,
                    instance_id=instance_id,
                    pipeline_callback=on_stage,
                )
            except Exception as exc:
                result_container["error"] = str(exc)
            finally:
                loop.call_soon_threadsafe(pipeline_events.put_nowait, None)  # sentinel

        # Launch pipeline in background thread
        loop.run_in_executor(None, run_pipeline)

        # Stream stage events until sentinel (None)
        while True:
            event = await pipeline_events.get()
            if event is None:
                break
            yield _sse("stage", event)

        # Surface error or result
        if "error" in result_container:
            yield _sse("error", result_container["error"])
            yield _sse("done", "done")
            return

        result_sql: str = result_container.get("sql", "")
        if result_sql.startswith("ERROR:"):
            yield _sse("error", result_sql)
            yield _sse("done", "done")
            return

        yield _sse("sql", {"sql": result_sql})

        # Read results from the CSV written by the executor
        results: List[Dict[str, Any]] = []
        columns: List[str] = []
        total_count = 0

        csv_path = Path(RESULTS_DIR) / conn_cfg.db_name / f"{instance_id}.csv"

        def _read_csv():
            if not csv_path.exists():
                return [], [], 0
            try:
                df = pd.read_csv(csv_path)
                cols = df.columns.tolist()
                cnt = len(df)
                res_df = df.head(200)
                # Convert NaN Ã¢â€ â€™ None for JSON serialisation
                res = json.loads(res_df.to_json(orient="records"))
                return res, cols, cnt
            except Exception as e:
                logger.warning(f"[CustomRouter] Could not read results CSV: {e}")
                return [], [], 0

        results, columns, total_count = await asyncio.to_thread(_read_csv)

        yield _sse(
            "result",
            {
                "sql": result_sql,
                "results": results,
                "columns": columns,
                "total_count": total_count,
            },
        )
        yield _sse("done", "done")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
