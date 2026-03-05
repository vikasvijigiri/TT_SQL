"""
Success Analysis Agent
Analyzes successful SQL generation to identify key factors of success.
"""
import logging
from typing import Dict, Any, Optional

from tt_sql.core.llm_service import LLMService
from tt_sql.core.prompt_loader import PromptLoader

class SuccessAnalysisAgent:
    """
    Agent responsible for analyzing successful Text-to-SQL results.
    """

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        self.prompt_loader = PromptLoader()
        self.logger = logging.getLogger(__name__)

    def classify_success(self, 
                         question: str, 
                         schema_info: Dict[str, Any], 
                         plan: str, 
                         generated_sql: str) -> str:
        """
        Classifies the success result.
        """
        return "Success"

    def analyze_success(self, 
                        question: str, 
                        schema_info: Dict[str, Any], 
                        plan: str, 
                        generated_sql: str) -> str:
        """
        Analyzes a successful instance and returns a markdown report.
        """
        
        try:
            # Format schema for prompt
            schema_str = self._format_schema(schema_info)
            
            # Load prompt
            messages = self.prompt_loader.load_prompt(
                "success_analysis",
                schema=schema_str,
                plan=plan,
                sql=generated_sql
            )
            
            self.logger.info(f"Analyzing success for query: {question[:50]}...")
            
            # Get analysis from LLM
            response = self.llm.get_completion(
                messages=messages,
                temperature=0.0,
                max_tokens=2048
            )
            
            return response

        except Exception as e:
            self.logger.error(f"Error during success analysis: {e}")
            return f"# Analysis Failed\n\nCould not perform analysis due to error: {str(e)}"

    def _format_schema(self, schema_info: Dict[str, Any]) -> str:
        """Helper to format schema dict into a readable string."""
        if not schema_info:
            return "No schema information available."
            
        lines = []
        for table, columns in schema_info.items():
            lines.append(f"Table: {table}")
            for col in columns:
                if isinstance(col, dict):
                    lines.append(f"  - {col.get('name')} ({col.get('type')})")
                else:
                    lines.append(f"  - {col}")
        return "\n".join(lines)
