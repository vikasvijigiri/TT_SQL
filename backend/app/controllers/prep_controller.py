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
