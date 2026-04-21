from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
from app.repositories.config import settings
import logging

logger = logging.getLogger("auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class GoogleLoginRequest(BaseModel):
    credential: str

@router.post("/google")
async def google_login(req: GoogleLoginRequest):
    """
    Verifies a Google ID token (credential) from the frontend
    and returns user information if valid.
    """
    token = req.credential
    client_id = settings.GOOGLE_CLIENT_ID

    if not client_id:
        logger.error("GOOGLE_CLIENT_ID not configured in settings")
        raise HTTPException(status_code=500, detail="OAuth Configuration Error")

    try:
        # Verify the ID token using Google's public keys
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), client_id)

        # ID token is valid. Get the user's Google Account ID from the decoded token.
        # userid = idinfo['sub']
        email = idinfo.get('email')
        name = idinfo.get('name')
        picture = idinfo.get('picture')

        return {
            "success": True,
            "user": {
                "email": email,
                "name": name,
                "picture": picture
            }
        }

    except ValueError as e:
        # Invalid token
        logger.warning(f"Invalid Google Token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid Authentication Token")
    except Exception as e:
        logger.error(f"Unexpected Auth Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")
