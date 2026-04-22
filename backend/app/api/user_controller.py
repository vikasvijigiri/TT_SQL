from fastapi import APIRouter, HTTPException, Query
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.repositories.user_repo import UserRepository
from app.repositories.paths import get_user_slug

router = APIRouter(prefix="/user", tags=["User"])

class UserState(BaseModel):
    currentView: Optional[str] = None
    activeProjectId: Optional[str] = None
    selectedDataset: Optional[str] = None

@router.get("/state")
async def get_user_state(
    user_email: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None)
):
    """Retrieve the last persisted state for a user."""
    if not user_email and not user_name:
        return {}
        
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    state = UserRepository.get_state(user_slug)
    return state

@router.post("/state")
async def save_user_state(
    state: Dict[str, Any],
    user_email: Optional[str] = Query(None),
    user_name: Optional[str] = Query(None)
):
    """Save the current state for a user."""
    if not user_email and not user_name:
        return {"status": "skipped", "reason": "No user identity provided"}
        
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    saved_state = UserRepository.save_state(user_slug, state)
    return {"status": "success", "state": saved_state}
