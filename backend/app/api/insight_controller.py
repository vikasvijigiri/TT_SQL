from fastapi import APIRouter, HTTPException
import os
import json
from typing import List, Dict, Any
from app.repositories.project_repo import ProjectRepository
from app.repositories.paths import get_metadata_dir
from app.services.llm_service import LLMService
from app.core.logger import Logger

router = APIRouter(prefix="/api/projects", tags=["Insights"])
llm_service = LLMService()

def _format_schema_for_llm(metadata: Dict[str, Any]) -> str:
    """Formats schema into a detailed string including sample values for better context."""
    lines = []
    tables = metadata.get("tables", {})
    for table_name, table_info in tables.items():
        table_desc = table_info.get("description", "")
        cols = table_info.get("columns", [])
        col_lines = []
        for c in cols:
            name = c.get("column_name")
            dtype = c.get("type", "unknown")
            desc = c.get("description", "")
            samples = c.get("sample_values", [])
            
            detail = f"- {name} ({dtype})"
            if desc:
                detail += f": {desc}"
            if samples:
                # Truncate sample values for prompt length
                sample_str = ", ".join([str(s) for s in samples[:3]])
                detail += f" [e.g., {sample_str}]"
            col_lines.append(detail)
            
        table_entry = f"Table: {table_name}"
        if table_desc:
            table_entry += f" ({table_desc})"
        table_entry += "\n" + "\n".join(col_lines)
        lines.append(table_entry)
        
    return "\n\n".join(lines)

@router.get("/{project_id}/samples")
async def get_sample_questions(project_id: str, user_email: str = None, user_name: str = None):
    """
    Generate or retrieve cached sample analytical questions for a project.
    """
    from app.repositories.paths import get_user_slug
    user_slug = get_user_slug(user_email=user_email, user_name=user_name)
    project = ProjectRepository.get_project_by_id(project_id, user_slug=user_slug)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check Cache first
    cached_questions = project.get("sample_questions")
    if cached_questions and isinstance(cached_questions, list) and len(cached_questions) > 0:
        return {
            "questions": cached_questions,
            "is_dynamic": True,
            "cached": True
        }
        
    # Determine the metadata filename from the connection details (first priority) or project name
    db_name = project.get("connection", {}).get("db_name") or project.get("connection", {}).get("qdrant_collection") or project.get("name")
    
    # Derive project slug for consistent metadata path resolution
    import re
    project_slug = re.sub(r'[^a-zA-Z0-9]', '_', project.get("name", "")).lower().strip('_') or "default_project"
    
    # Try to load metadata if it exists - Path: results/{user}/{project}/metadata_extracts/{collection}.json
    metadata_path = get_metadata_dir(user_slug, project_slug) / f"{db_name}.json"
    
    if not os.path.exists(metadata_path):
        return {
            "questions": [
                "Total count of records by category",
                "Show me the top 5 entries by value",
                "Average value over the last month"
            ],
            "is_dynamic": False
        }
        
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            
        schema_summary = _format_schema_for_llm(metadata)
        
        from app.utils.prompt_loader import PromptLoader
        loader = PromptLoader()
        
        messages = loader.load_prompt("business_insight", schema_summary=schema_summary)
        
        result = llm_service.get_json_completion(messages)
        
        if result and isinstance(result, dict) and "questions" in result:
            questions = result["questions"]
            
            # Persist to Cache
            project["sample_questions"] = questions
            ProjectRepository.save_project(project)
            
            return {
                "questions": questions, 
                "is_dynamic": True,
                "cached": False
            }
        else:
            raise ValueError("Invalid LLM response")
            
    except Exception as e:
        Logger.log(f"Error generating samples for {project_id}: {str(e)}", level="ERROR")
        return {
            "questions": [
                "How many records are in the main table?",
                "List the top 10 rows by date",
                "Average values for the current period"
            ],
            "is_dynamic": False
        }
