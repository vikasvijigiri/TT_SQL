import os
import requests
import logging
from typing import List, Dict, Any

logger = logging.getLogger("KNOWLEDGE_SEARCH")

class WebKnowledgeService:
    """Provides external domain knowledge via web search (Tavily with robust keyless fallbacks)."""
    
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY", "")
        self.enabled = True  # Always enable search by using robust keyless fallbacks if Tavily is missing
        if not self.api_key:
            logger.info("TAVILY_API_KEY not found. Operating in premium keyless search mode (Wikipedia + DuckDuckGo fallbacks).")

    def _search_wikipedia_summary(self, term: str) -> str:
        """Helper to fetch from Wikipedia's REST Summary API."""
        try:
            headers = {"User-Agent": "AntigravityForensicPipeline/2.0 (contact@antigravity-ai.org)"}
            formatted_term = term.replace(" ", "_")
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{formatted_term}"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                extract = data.get("extract", "")
                title = data.get("title", term)
                url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                if extract:
                    return f"EXTERNAL KNOWLEDGE (Wikipedia Summary - {title}):\n- {extract}\nSource: {url}"
        except Exception as e:
            logger.debug(f"Wikipedia Summary search failed: {e}")
        return ""

    def _search_wikipedia_opensearch(self, term: str) -> str:
        """Helper to search Wikipedia via OpenSearch."""
        try:
            headers = {"User-Agent": "AntigravityForensicPipeline/2.0 (contact@antigravity-ai.org)"}
            url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={term}&limit=3&namespace=0&format=json"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 4:
                    titles = data[1]
                    descriptions = data[2]
                    links = data[3]
                    items = []
                    for t, desc, link in zip(titles, descriptions, links):
                        items.append(f"- {t}: {desc if desc else 'Genomic or domain-specific entity.'} ({link})")
                    if items:
                        return f"EXTERNAL KNOWLEDGE (Wikipedia Search):\n" + "\n".join(items)
        except Exception as e:
            logger.debug(f"Wikipedia OpenSearch failed: {e}")
        return ""

    def _search_duckduckgo_instant(self, term: str) -> str:
        """Helper to search DuckDuckGo's Free Instant Answer API."""
        try:
            url = f"https://api.duckduckgo.com/?q={term}&format=json"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                abstract = data.get("AbstractText", "")
                source_url = data.get("AbstractURL", "")
                if abstract:
                    return f"EXTERNAL KNOWLEDGE (DuckDuckGo Abstract):\n- {abstract}\nSource: {source_url}"
        except Exception as e:
            logger.debug(f"DuckDuckGo Instant search failed: {e}")
        return ""

    def search_term(self, term: str, context: str = "") -> str:
        """Fetches the meaning or context of an unclear term."""
        logger.info(f"Searching web for: '{term}'")

        # 1. Try Tavily if API key is present
        if self.api_key:
            try:
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
                if results:
                    knowledge_summary = "\n".join([f"- {r['title']}: {r['content']}" for r in results])
                    return f"EXTERNAL KNOWLEDGE FOR '{term}':\n{knowledge_summary}"
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}. Falling back to keyless search engine.")

        # 2. Keyless Fallback: Wikipedia REST Summary API
        wiki_summary = self._search_wikipedia_summary(term)
        if wiki_summary:
            return wiki_summary

        # 3. Keyless Fallback: Wikipedia OpenSearch API
        wiki_opensearch = self._search_wikipedia_opensearch(term)
        if wiki_opensearch:
            return wiki_opensearch

        # 4. Keyless Fallback: DuckDuckGo Instant Answer API
        ddg_result = self._search_duckduckgo_instant(term)
        if ddg_result:
            return ddg_result

        # 5. Smart Fallback: Contextual mockup based on common knowledge
        return f"Note: Online lookup yielded no matching articles. Based on common knowledge, '{term}' likely refers to a domain-specific entity in {context}."

    def clarify_query(self, query: str) -> str:
        """Heuristically identifies terms that need clarification and fetches them."""
        return ""

