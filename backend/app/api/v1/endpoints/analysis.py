from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.schemas.api_schemas import QueryRequest
from app.domain.analysis.orchestrator import AnalysisOrchestrator
from app.infrastructure.storage.path_manager import StorageManager

router = APIRouter()

@router.post("/stream")
async def stream_query(request: QueryRequest, raw_request: Request):
    """
    Initiates a streaming Text-to-SQL analysis session.
    """
    user_slug = StorageManager.get_user_slug(email=request.user_email)
    
    # Resolve project slug (to be improved with better state resolution)
    from app.domain.users.repository import UserRepository
    state = UserRepository().get_state(user_slug)
    p_slug = state.get("activeProjectSlug") or "default"
    
    orchestrator = AnalysisOrchestrator(
        user_slug=user_slug, 
        project_slug=p_slug, 
        model_name=request.model_name
    )
    
    generator = orchestrator.stream_analysis(request, raw_request=raw_request)
    return StreamingResponse(generator, media_type="text/event-stream")
