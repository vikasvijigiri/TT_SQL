from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.services.utils.prep_service import PrepService

router = APIRouter(prefix="/api/prep", tags=["Preparation"])
prep_service = PrepService()

@router.post("/run")
def run_prep(force: bool = False):
    """
    Triggers the knowledge preparation pipeline.
    Streams logs via SSE.
    """
    return StreamingResponse(
        prep_service.run_pipeline(force=force),
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
