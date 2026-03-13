from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.repositories.config import settings
class QueryRequest(BaseModel):
    query: str = "web_query"
    db_name: str = settings.COLLECTION_NAME
    dataset_name: Optional[str] = "sample.jsonl"
    instance_id: str = ""
    use_rag: bool = True

class QueryResponse(BaseModel):
    instance_id: str
    sql: Optional[str]
    results: Optional[List[Dict[str, Any]]]
    columns: Optional[List[str]]
    logs: List[str]
    critic_feedback: Optional[str]
    business_summary: Optional[str]
