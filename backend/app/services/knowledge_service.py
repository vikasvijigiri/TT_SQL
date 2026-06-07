import os
import time
import requests
from typing import Dict, Tuple

from backend.app.utils.logger import logger

# Simple in-memory TTL cache: term -> (result_str, expiry_timestamp)
_KNOWLEDGE_CACHE: Dict[str, Tuple[str, float]] = {}
_CACHE_TTL_S = 300  # 5 minutes

# Circuit breaker: fail fast after N consecutive external failures within a window
_CB_FAILURE_THRESHOLD = 3
_CB_RESET_AFTER_S = 120  # re-probe after 2 minutes
_cb_failures = 0
_cb_opened_at: float = 0.0


def _cb_is_open() -> bool:
    global _cb_failures, _cb_opened_at
    if _cb_failures >= _CB_FAILURE_THRESHOLD:
        if time.time() - _cb_opened_at < _CB_RESET_AFTER_S:
            return True
        # Half-open: allow one probe
        _cb_failures = 0
    return False


def _cb_record_failure() -> None:
    global _cb_failures, _cb_opened_at
    _cb_failures += 1
    if _cb_failures >= _CB_FAILURE_THRESHOLD:
        _cb_opened_at = time.time()
        logger.warning("[WebKnowledgeService] Circuit breaker OPEN — external knowledge calls suspended.")


def _cb_record_success() -> None:
    global _cb_failures
    _cb_failures = 0


class WebKnowledgeService:
    """Provides external domain knowledge via web search (Tavily with robust keyless fallbacks)."""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY", "")
        if not self.api_key:
            logger.info("TAVILY_API_KEY not found. Operating in keyless mode (Wikipedia + DuckDuckGo fallbacks).")

    def _search_wikipedia_summary(self, term: str) -> str:
        try:
            headers = {"User-Agent": "AntigravityForensicPipeline/2.0 (contact@antigravity-ai.org)"}
            formatted_term = term.replace(" ", "_")
            api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{formatted_term}"
            response = requests.get(api_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                extract = data.get("extract", "")
                title = data.get("title", term)
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                if extract:
                    return f"EXTERNAL KNOWLEDGE (Wikipedia Summary - {title}):\n- {extract}\nSource: {page_url}"
        except Exception as e:
            logger.debug(f"Wikipedia Summary search failed: {e}")
        return ""

    def _search_wikipedia_opensearch(self, term: str) -> str:
        try:
            headers = {"User-Agent": "AntigravityForensicPipeline/2.0 (contact@antigravity-ai.org)"}
            api_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={term}&limit=3&namespace=0&format=json"
            response = requests.get(api_url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 4:
                    titles = data[1]
                    descriptions = data[2]
                    links = data[3]
                    items = []
                    for t, desc, link in zip(titles, descriptions, links):
                        items.append(f"- {t}: {desc if desc else 'Domain-specific entity.'} ({link})")
                    if items:
                        return "EXTERNAL KNOWLEDGE (Wikipedia Search):\n" + "\n".join(items)
        except Exception as e:
            logger.debug(f"Wikipedia OpenSearch failed: {e}")
        return ""

    def _search_duckduckgo_instant(self, term: str) -> str:
        try:
            api_url = f"https://api.duckduckgo.com/?q={term}&format=json"
            response = requests.get(api_url, timeout=5)
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
        """Fetch domain knowledge for a term, with TTL caching and circuit-breaker protection."""
        cache_key = f"{term}||{context}"
        now = time.time()

        # Return cached result if still valid
        if cache_key in _KNOWLEDGE_CACHE:
            cached_val, expiry = _KNOWLEDGE_CACHE[cache_key]
            if now < expiry:
                logger.debug(f"[WebKnowledgeService] Cache hit for '{term}'.")
                return cached_val

        if _cb_is_open():
            return f"Note: External knowledge circuit breaker open. '{term}' lookup skipped."

        logger.info(f"[WebKnowledgeService] Searching web for: '{term}'")
        result = ""

        # 1. Try Tavily if API key is present
        if self.api_key:
            try:
                resp = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": f"definition and database context for '{term}' in {context}",
                        "search_depth": "advanced",
                        "max_results": 3,
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if results:
                    result = f"EXTERNAL KNOWLEDGE FOR '{term}':\n" + "\n".join(
                        f"- {r['title']}: {r['content']}" for r in results
                    )
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}. Falling back to keyless sources.")

        # 2–4. Keyless fallback chain
        if not result:
            result = (
                self._search_wikipedia_summary(term)
                or self._search_wikipedia_opensearch(term)
                or self._search_duckduckgo_instant(term)
            )

        if result:
            _cb_record_success()
        else:
            _cb_record_failure()
            result = (
                f"Note: Online lookup yielded no matching articles. "
                f"Based on common knowledge, '{term}' likely refers to a domain-specific entity in {context}."
            )

        _KNOWLEDGE_CACHE[cache_key] = (result, now + _CACHE_TTL_S)
        return result

    def clarify_query(self, _query: str) -> str:
        return ""
