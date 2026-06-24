import os
import re
import time
import urllib.parse
import requests
from typing import Dict, Tuple

from agent.app.utils.logger import logger

# ---------------------------------------------------------------------------
# SCHEMA CONCEPT DETECTION — Only block terms that are unambiguously DB-only
# Previous version was too aggressive: it blocked ALL short single-word terms,
# which prevented lookup of valid entities like IXIC, NSEI, apple/swift, etc.
# ---------------------------------------------------------------------------

# Column/metric names that would never have a Wikipedia article
_SCHEMA_METRIC_RE = re.compile(
    r"^(count|num|number|id|ids|flag|rate|score|stars?|total|avg|sum|"
    r"mean|median|rank|pct|percent|ratio|proportion|"
    r"metric|value|amount|quantity|cost|size|length|weight|"
    r"created_at|updated_at|deleted_at|is_active|is_deleted)$",
    re.IGNORECASE,
)

# Ticker/index patterns — these ARE web-searchable (stock market indices)
_TICKER_RE = re.compile(r"^[A-Z]{1,6}$|^\^[A-Z]{2,6}$|^[A-Z0-9]{2,12}\.[A-Z]{1,3}$")

# GitHub-style repo names
_REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


def _is_schema_concept(term: str) -> bool:
    """Return True ONLY when a term is unambiguously a DB column/metric, not a real-world entity."""
    t = term.strip()

    # Exact match against metric keywords only (not partial)
    if _SCHEMA_METRIC_RE.match(t):
        return True

    # snake_case with >= 2 underscores → likely a column name (e.g. is_active, created_at)
    if t.count("_") >= 2:
        return True

    # camelCase column names (e.g. totalRevenue, recordCount)
    if re.search(r"[a-z][A-Z]", t) and " " not in t and "_" not in t:
        return True

    # Stock tickers and repo names are REAL entities — never skip them
    if _TICKER_RE.match(t) or _REPO_RE.match(t):
        return False

    # Previously: ANY short single token was blocked. This was wrong.
    # Now: only block if it looks like a raw numeric/SQL expression
    if re.match(r"^[\d\s\+\-\*\/\(\)\.]+$", t):
        return True

    return False


# ---------------------------------------------------------------------------
# TTL Cache + Circuit breaker (unchanged from original)
# ---------------------------------------------------------------------------
_KNOWLEDGE_CACHE: Dict[str, Tuple[str, float]] = {}
_CACHE_TTL_S = 300  # 5 minutes

_CB_FAILURE_THRESHOLD = 5          # raised from 3 — more tolerant
_CB_RESET_AFTER_S = 60             # reset faster (1 min vs 2 min)
_cb_failures = 0
_cb_opened_at: float = 0.0


def _cb_is_open() -> bool:
    global _cb_failures, _cb_opened_at
    if _cb_failures >= _CB_FAILURE_THRESHOLD:
        if time.time() - _cb_opened_at < _CB_RESET_AFTER_S:
            return True
        _cb_failures = 0  # half-open
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


# ---------------------------------------------------------------------------
# WebKnowledgeService — enhanced keyless fallback chain
# ---------------------------------------------------------------------------

class WebKnowledgeService:
    """Provides external domain knowledge via web search.

    Priority:
      1. Tavily (if TAVILY_API_KEY set in environment)
      2. Wikipedia REST summary (exact + fuzzy title)
      3. Wikipedia OpenSearch (finds closest article title)
      4. Wikipedia full-text search API (catches aliases + redirects)
      5. GitHub API (for repo names like apple/swift)
      6. DuckDuckGo Instant Answer
    """

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY", "")
        if not self.api_key:
            logger.info(
                "TAVILY_API_KEY not set — using enhanced keyless fallback chain "
                "(Wikipedia REST + OpenSearch + full-text + GitHub + DuckDuckGo)."
            )

    # ── Wikipedia REST summary ────────────────────────────────────────────
    def _search_wikipedia_summary(self, term: str) -> str:
        """Direct article lookup — works for exact titles."""
        try:
            headers = {"User-Agent": "TT-SQL-Pipeline/2.0 (research-agent; not-commercial)"}
            encoded = urllib.parse.quote(term.replace(" ", "_"))
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "")
                title = data.get("title", term)
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                if extract:
                    return f"EXTERNAL KNOWLEDGE (Wikipedia — {title}):\n- {extract}\nSource: {page_url}"
        except Exception as e:
            logger.debug(f"[WebKnowledge] Wikipedia summary failed for '{term}': {e}")
        return ""

    # ── Wikipedia OpenSearch (fuzzy title search) ─────────────────────────
    def _search_wikipedia_opensearch(self, term: str) -> str:
        """Finds the closest Wikipedia article title — handles redirects and aliases."""
        try:
            headers = {"User-Agent": "TT-SQL-Pipeline/2.0 (research-agent; not-commercial)"}
            encoded = urllib.parse.quote(term)
            url = (
                f"https://en.wikipedia.org/w/api.php"
                f"?action=opensearch&search={encoded}&limit=3&namespace=0&format=json"
            )
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 4:
                    titles, descriptions, links = data[1], data[2], data[3]
                    items = []
                    for t, desc, link in zip(titles, descriptions, links, strict=False):
                        items.append(f"- {t}: {desc if desc else 'Known entity.'} ({link})")
                    if items:
                        return "EXTERNAL KNOWLEDGE (Wikipedia Search):\n" + "\n".join(items)
        except Exception as e:
            logger.debug(f"[WebKnowledge] Wikipedia OpenSearch failed for '{term}': {e}")
        return ""

    # ── Wikipedia full-text search API ───────────────────────────────────
    def _search_wikipedia_fulltext(self, term: str) -> str:
        """Full-text search — catches 'Argo Group' → 'Argo Group International Holdings'."""
        try:
            headers = {"User-Agent": "TT-SQL-Pipeline/2.0 (research-agent; not-commercial)"}
            encoded = urllib.parse.quote(term)
            url = (
                f"https://en.wikipedia.org/w/api.php"
                f"?action=query&list=search&srsearch={encoded}"
                f"&srlimit=3&srprop=snippet&format=json"
            )
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("query", {}).get("search", [])
                if hits:
                    items = []
                    for h in hits[:3]:
                        title   = h.get("title", "")
                        snippet = re.sub(r"<[^>]+>", "", h.get("snippet", ""))
                        items.append(f"- {title}: {snippet}")
                    return (
                        f"EXTERNAL KNOWLEDGE (Wikipedia Full-Text Search for '{term}'):\n"
                        + "\n".join(items)
                    )
        except Exception as e:
            logger.debug(f"[WebKnowledge] Wikipedia full-text search failed for '{term}': {e}")
        return ""

    # ── GitHub API (for repo names) ───────────────────────────────────────
    def _search_github(self, term: str) -> str:
        """Looks up GitHub repos — handles terms like 'apple/swift', 'tensorflow/tensorflow'."""
        if "/" not in term:
            return ""
        try:
            owner, repo = term.split("/", 1)
            # Direct repo lookup first
            resp = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers={"Accept": "application/vnd.github+json"},
                timeout=6,
            )
            if resp.status_code == 200:
                data = resp.json()
                desc = data.get("description", "No description available.")
                lang = data.get("language", "unknown")
                stars = data.get("stargazers_count", 0)
                return (
                    f"EXTERNAL KNOWLEDGE (GitHub — {term}):\n"
                    f"- Repository: {data.get('full_name', term)}\n"
                    f"- Description: {desc}\n"
                    f"- Language: {lang}, Stars: {stars:,}\n"
                    f"Source: {data.get('html_url', '')}"
                )
            # If direct lookup fails, search for it
            encoded = urllib.parse.quote(f"{owner} {repo}")
            sresp = requests.get(
                f"https://api.github.com/search/repositories?q={encoded}&per_page=3",
                headers={"Accept": "application/vnd.github+json"},
                timeout=6,
            )
            if sresp.status_code == 200:
                items = sresp.json().get("items", [])
                if items:
                    r0 = items[0]
                    return (
                        f"EXTERNAL KNOWLEDGE (GitHub Search — '{term}'):\n"
                        f"- Best match: {r0.get('full_name')} — {r0.get('description', '')}\n"
                        f"Source: {r0.get('html_url', '')}"
                    )
        except Exception as e:
            logger.debug(f"[WebKnowledge] GitHub search failed for '{term}': {e}")
        return ""

    # ── Stock index lookup (for IXIC, NSEI, etc.) ────────────────────────
    def _search_stock_index(self, term: str) -> str:
        """Looks up well-known stock indices by their ticker symbol via Wikipedia."""
        # Map common tickers to their full names for better Wikipedia lookup
        KNOWN_INDICES = {
            "IXIC": "NASDAQ Composite", "NSEI": "NIFTY 50", "GSPC": "S&P 500",
            "DJI": "Dow Jones Industrial Average", "FTSE": "FTSE 100",
            "N225": "Nikkei 225", "HSI": "Hang Seng Index",
            "SSEC": "SSE Composite Index", "GDAXI": "DAX",
            "FCHI": "CAC 40", "STOXX50E": "Euro Stoxx 50",
            "399001": "SZSE Component Index", "000001": "SSE Composite",
        }
        # Strip common suffixes: .SZ .SS .NS .BO
        base = re.sub(r"\.(SZ|SS|NS|BO|L|PA|DE|HK|T)$", "", term.strip("^"))
        wiki_name = KNOWN_INDICES.get(base) or KNOWN_INDICES.get(term.strip("^"))
        if wiki_name:
            result = self._search_wikipedia_summary(wiki_name)
            if result:
                return result + f"\n(Ticker symbol: {term})"
        return ""

    # ── DuckDuckGo instant answer ─────────────────────────────────────────
    def _search_duckduckgo_instant(self, term: str) -> str:
        try:
            encoded = urllib.parse.quote(term)
            url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                abstract = data.get("AbstractText", "")
                source   = data.get("AbstractURL", "")
                if abstract:
                    return f"EXTERNAL KNOWLEDGE (DuckDuckGo):\n- {abstract}\nSource: {source}"
                # Try Related Topics
                related = data.get("RelatedTopics", [])
                if related and isinstance(related[0], dict):
                    text = related[0].get("Text", "")
                    if text:
                        return f"EXTERNAL KNOWLEDGE (DuckDuckGo Related):\n- {text}"
        except Exception as e:
            logger.debug(f"[WebKnowledge] DuckDuckGo search failed for '{term}': {e}")
        return ""

    # ── Main entry point ──────────────────────────────────────────────────
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

        if _is_schema_concept(term):
            result = (
                f"Note: '{term}' is a database-specific concept. "
                f"Use schema introspection and SQL functions to interpret it — web search not applicable."
            )
            logger.info(f"[WebKnowledgeService] Skipping web lookup for schema concept: '{term}'")
            _KNOWLEDGE_CACHE[cache_key] = (result, now + _CACHE_TTL_S)
            return result

        if _cb_is_open():
            return f"Note: External knowledge circuit breaker open. '{term}' lookup skipped."

        logger.info(f"[WebKnowledgeService] Searching web for: '{term}'")
        result = ""

        # 1. Tavily (premium — if API key present)
        if self.api_key:
            try:
                resp = requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": f"{term} {context}".strip(),
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

        # 2–7. Enhanced keyless fallback chain
        if not result:
            # Route to the best source based on term shape
            if _REPO_RE.match(term):
                # GitHub repo (e.g. apple/swift, tensorflow/tensorflow)
                result = self._search_github(term)

            if not result and _TICKER_RE.match(term.strip("^")):
                # Stock index ticker (e.g. IXIC, NSEI, 399001.SZ)
                result = self._search_stock_index(term)

            if not result:
                # Wikipedia exact → OpenSearch → full-text chain
                result = (
                    self._search_wikipedia_summary(term)
                    or self._search_wikipedia_opensearch(term)
                    or self._search_wikipedia_fulltext(term)
                    or self._search_duckduckgo_instant(term)
                )

        if result:
            _cb_record_success()
            logger.info(f"[WebKnowledgeService] Found knowledge for '{term}' ({len(result)} chars)")
        else:
            _cb_record_failure()
            result = (
                f"Note: Online lookup yielded no matching articles for '{term}'. "
                f"Based on context '{context}', this is likely a domain-specific entity."
            )

        _KNOWLEDGE_CACHE[cache_key] = (result, now + _CACHE_TTL_S)
        return result
