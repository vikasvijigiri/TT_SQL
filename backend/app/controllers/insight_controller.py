from fastapi import APIRouter, HTTPException
import os
import json
from typing import List, Dict, Any
from app.repositories.registry.project_repo import ProjectRepository
from app.repositories.registry.paths import get_metadata_dir
from app.services.engines.llm_service import LLMService
from app.services.utils.logger import Logger

router = APIRouter(prefix="/api/projects", tags=["Insights"])
llm_service = LLMService()

def _format_schema_for_llm(metadata: Dict[str, Any]) -> str:
    """Formats schema into a compact string for LLM prompting."""
    lines = []
    tables = metadata.get("tables", {})
    for table_name, table_info in tables.items():
        cols = table_info.get("columns", [])
        col_desc = []
        for c in cols:
            name = c.get("column_name")
            desc = c.get("description", "")
            if desc:
                col_desc.append(f"{name} ({desc})")
            else:
                col_desc.append(name)
        lines.append(f"Table: {table_name}\nColumns: {', '.join(col_desc)}")
    return "\n\n".join(lines)

@router.get("/{project_id}/samples")
async def get_sample_questions(project_id: str):
    """
    Generate 3-4 sample analytical questions based on the database schema using LLM.
    """
    project = ProjectRepository.get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    db_name = project.get("name", "unknown")
    # Try to load metadata if it exists
    metadata_path = get_metadata_dir() / f"{db_name}.json"
    
    if not os.path.exists(metadata_path):
        # Fallback to generic questions if metadata is missing
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
        
        system_prompt = (
            "You are a Senior Business Intelligence Analyst. Given the database schema provided, "
            "generate 3 varied, highly relevant, and insightful natural language questions a user might ask. "
            "The questions should demonstrate data analysis capabilities (e.g., aggregation, trends, comparisons). "
            "Return ONLY a valid JSON object with a 'questions' key containing a list of strings."
        )
        user_prompt = f"DATABASE SCHEMA:\n{schema_summary}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        result = llm_service.get_json_completion(messages)
        
        if result and isinstance(result, dict) and "questions" in result:
            return {"questions": result["questions"], "is_dynamic": True}
        else:
            Logger.log(f"Failed to generate valid samples for {db_name}, result: {result}", level="ERROR")
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
