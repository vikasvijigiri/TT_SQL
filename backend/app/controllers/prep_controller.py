from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.utils.prep_service import PrepService

router = APIRouter(prefix="/api/prep", tags=["Preparation"])
prep_service = PrepService()

@router.post("/run")
def run_prep(force: bool = False, user_email: str = None, user_name: str = None):
    """
    Triggers the knowledge preparation pipeline.
    Streams logs via SSE.
    """
    from app.repositories.registry.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
        
    return StreamingResponse(
        prep_service.run_pipeline(force=force, user_slug=user_slug),
        media_type="text/event-stream"
    )

@router.delete("/collection")
def delete_collection(collection_name: str = None):
    """
    Deletes the vector collection.
    """
    from app.services.metadata.ingestion_service import IngestService
    from app.repositories.config import settings
    is_service = IngestService()
    target_coll = collection_name or settings.COLLECTION_NAME
    success = is_service.delete_collection(target_coll)
    if success:
        return {"status": "success", "message": f"Collection '{target_coll}' deleted."}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to delete collection '{target_coll}'.")

@router.get("/status")
def get_prep_status(user_email: str = None, user_name: str = None):
    """Checks if RAG metadata and vector collection are ready."""
    from app.repositories.registry.paths import get_user_slug, get_metadata_dir
    from app.repositories.connectors.sql_repo import DBRepository
    from app.repositories.registry.project_repo import ProjectRepository
    import os
    import requests
    import re
    from app.repositories.config import settings

    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    active_conn = DBRepository._get_active_connection(user_slug=user_slug)
    
    # FIX: Check if no active project (empty dict or missing db_type)
    if not active_conn or not active_conn.get("db_type"):
        return {
            "ready": False, 
            "status": "No Active Project", 
            "message": "Please select a database project first",
            "metadata_exists": False,
            "qdrant_ready": False,
            "collection": None
        }

    # Get collection name using standardized function
    collection_name = DBRepository.get_collection_name(active_conn)

    # CRITICAL FIX: Derive project_slug from active project for consistent metadata paths
    project_slug = "default_project"
    active_project_id = None
    from app.repositories.registry.user_repo import UserRepository
    user_state = UserRepository.get_state(user_slug)
    active_project_id = user_state.get("activeProjectId")
    
    if active_project_id:
        project = ProjectRepository.get_project_by_id(active_project_id, user_slug=user_slug)
        if project and project.get("name"):
            project_slug = re.sub(r'[^a-zA-Z0-9]', '_', project["name"]).lower().strip('_')
    else:
        # Fallback to connection-based resolution if ID is missing but connection is loaded
        p_name = active_conn.get("db_name") or active_conn.get("database") or "default_project"
        project_slug = re.sub(r'[^a-zA-r0-9]', '_', p_name).lower().strip('_')
    
    # 1. Check Metadata JSON - Path: results/{user}/{project}/metadata_extracts/{collection}.json
    metadata_path = get_metadata_dir(user_slug, project_slug) / f"{collection_name}.json"
    metadata_exists = os.path.exists(metadata_path)

    # 2. Check Qdrant
    q_url = active_conn.get("qdrant_url") or settings.QDRANT_URL
    q_key = active_conn.get("qdrant_api_key") or settings.QDRANT_API_KEY
    qdrant_ready = False
    
    print(f"DEBUG [RagStatus]: Checking collection '{collection_name}' at {q_url}")
    if q_url and collection_name:
        try:
            resp = requests.get(f"{q_url.rstrip('/')}/collections/{collection_name}", headers={"api-key": q_key}, timeout=2)
            qdrant_ready = resp.status_code == 200
            if not qdrant_ready:
                print(f"DEBUG [RagStatus]: Qdrant responded with {resp.status_code} for collection '{collection_name}'")
        except Exception as e:
            print(f"DEBUG [RagStatus]: Connection to Qdrant failed: {str(e)}")
            qdrant_ready = False
    else:
        print(f"DEBUG [RagStatus]: Missing Qdrant URL or Collection name (q_url={q_url}, coll={collection_name})")

    return {
        "ready": metadata_exists and qdrant_ready,
        "metadata_exists": metadata_exists,
        "qdrant_ready": qdrant_ready,
        "collection": collection_name,
        "status": "Ready" if (metadata_exists and qdrant_ready) else "Missing Metadata" if not metadata_exists else "Not Injected"
    }
