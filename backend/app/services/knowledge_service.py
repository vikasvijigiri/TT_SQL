import os
import requests
import logging
from typing import List, Dict, Any
from backend.app.core.config import RESULTS_DIR

logger = logging.getLogger("KNOWLEDGE_SEARCH")

class WebKnowledgeService:
    """Provides external domain knowledge via web search (Tavily/Serper fallback)."""
    
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY", "")
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.warning("TAVILY_API_KEY not found. Web search will be mocked for domain clarification.")

    def search_term(self, term: str, context: str = "") -> str:
        """Fetches the meaning or context of an unclear term."""
        if not self.enabled:
            return f"Note: Web search is currently disabled. Based on common knowledge, '{term}' likely refers to a domain-specific entity in {context}."

        logger.info(f"Searching web for: {term}")
        try:
            # Using Tavily for high-quality LLM-ready search results
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": f"definition and database context for '{term}' in {context}",
                    "search_depth": "advanced",
                    "max_results": 3
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            if not results:
                return f"No specific web results found for '{term}'."
                
            knowledge_summary = "\n".join([f"- {r['title']}: {r['content']}" for r in results])
            return f"EXTERNAL KNOWLEDGE FOR '{term}':\n{knowledge_summary}"
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return f"Knowledge retrieval failed for '{term}'."

    def clarify_query(self, query: str) -> str:
        """Heuristically identifies terms that need clarification and fetches them."""
        # This can be expanded to use an LLM to pick terms, 
        # but for now, we'll provide the tool for the Orchestrator to call.
        return ""
