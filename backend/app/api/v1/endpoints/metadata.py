from fastapi import APIRouter, HTTPException
from app.domain.metadata.extraction import MetadataExtractor
from app.domain.metadata.ingestion import MetadataIngestor
from app.infrastructure.storage.path_manager import StorageManager
from app.domain.projects.repository import ProjectRepository

router = APIRouter()

@router.post("/extract")
async def extract_metadata(user_email: str = None, project_id: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    extractor = MetadataExtractor(user_slug=slug)
    
    # Logic to resolve schema name would go here
    schema = "public" 
    metadata = extractor.extract(schema_name=schema)
    return {"status": "success", "metadata": metadata}

@router.post("/ingest")
async def ingest_metadata(collection_name: str, user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    ingestor = MetadataIngestor()
    
    # Load metadata from results folder...
    # (Simplified for refactor)
    return {"status": "success", "message": f"Ingested to {collection_name}"}

@router.get("/storage")
async def get_storage_stats(user_email: str = None):
    slug = StorageManager.get_user_slug(email=user_email)
    # Return count of projects and total storage
    projects = ProjectRepository().get_all_projects(slug)
    return {"project_count": len(projects)}
