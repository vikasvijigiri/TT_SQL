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
async def get_sample_questions(project_id: str):
    """
    Generate or retrieve cached sample analytical questions for a project.
    """
    project = ProjectRepository.get_project_by_id(project_id)
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
    
    # Try to load metadata if it exists
    metadata_path = get_metadata_dir() / f"{db_name}.json"
    
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
        
        system_prompt = (
            "You are a Senior Business Intelligence Lead. Your goal is to look at the database schema, "
            "table descriptions, and sample data values provided, and pick the most relevant tables to generate "
            "3 varied, and highly insightful natural language questions that a business leader might ask."
            "\n\nRules:"
            "\n1. Questions must be answerable using the provided columns."
            "\n2. Use the sample values to understand the domain (e.g., if you see names like 'Royal Challengers', generate cricket-specific questions)."
            "\n3. Generate varied levels (e.g., one summary count, one top-performing analysis, and one trend/time-based analysis)."
            "\n4. Return ONLY a valid JSON object: {\"questions\": [\"Question 1\", \"Question 2\", \"Question 3\"]}"
        )
        user_prompt = f"DATABASE SCHEMA:\n{schema_summary}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
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
