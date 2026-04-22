from fastapi import APIRouter
from .endpoints import projects, analysis, metadata

api_router = APIRouter()

api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["Analysis"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["Metadata"])
