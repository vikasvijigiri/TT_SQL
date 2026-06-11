import re
import difflib
from typing import List, Dict, Tuple
from backend.app.models.schemas import SemanticContext, SemanticTable, SemanticColumn
from backend.app.core.pipeline_config import PipelineModeConfig, BALANCED_CONFIG

# Business-term synonym map: query word -> canonical schema tokens it maps to.
# Expands query vocabulary so difflib / Jaccard can bridge surface-form gaps.
_SYNONYM_MAP: Dict[str, List[str]] = {
    # sales / revenue
    "revenue": ["sales", "amount", "total", "income", "price", "receipt"],
    "sales": ["revenue", "amount", "total", "order"],
    "profit": ["margin", "income", "earnings", "net"],
    "price": ["cost", "rate", "fee", "amount", "charge"],
    "discount": ["reduction", "rebate", "promo"],
    # user / customer
    "customer": ["user", "client", "buyer", "member", "account", "person"],
    "user": ["customer", "client", "member", "account"],
    "author": ["writer", "creator", "user"],
    "employee": ["staff", "worker", "person"],
    # location
    "country": ["nation", "region", "territory", "geo"],
    "city": ["town", "location", "place", "municipality"],
    "address": ["location", "street", "city", "zip"],
    # time
    "date": ["time", "timestamp", "created", "updated", "day", "year", "month"],
    "year": ["date", "time", "period", "fiscal"],
    "recent": ["latest", "last", "current", "new"],
    # count / quantity
    "count": ["number", "total", "qty", "quantity", "num"],
    "total": ["sum", "count", "aggregate", "all"],
    "average": ["mean", "avg"],
    # status / type
    "status": ["state", "flag", "type", "category"],
    "type": ["kind", "category", "class", "status"],
    "category": ["type", "class", "group", "segment"],
    # product / item
    "product": ["item", "sku", "article", "goods"],
    "order": ["purchase", "transaction", "sale", "invoice"],
    "rating": ["score", "review", "rank", "grade"],
    "review": ["rating", "comment", "feedback"],
    # genomics / scientific
    "gene": ["variant", "mutation", "allele", "locus"],
    "sample": ["specimen", "case", "patient", "subject"],
    # software / github
    "repo": ["repository", "project", "package"],
    "dependency": ["package", "library", "module", "requirement"],
    "version": ["release", "tag", "revision"],
}


class SchemaRetriever:
    """
    Hybrid semantic and lexical schema retrieval engine. Ranks candidate tables,
    columns, and nested keys against query intent before LLM prompt generation.
    """

    def __init__(self, config: PipelineModeConfig = BALANCED_CONFIG):
        self.config = config
        self.similarity_threshold = config.retrieval_similarity_threshold

    def _expand_with_synonyms(self, tokens: set) -> set:
        """Augment a token set with domain synonyms to improve recall."""
        extra: set = set()
        for t in tokens:
            for syn in _SYNONYM_MAP.get(t, []):
                extra.add(syn)
        return tokens | extra

    def _tokenize(self, text: str) -> set:
        clean = re.sub(r"[^a-zA-Z0-9_]", " ", text.lower())
        tokens = [t.strip() for t in clean.split() if len(t.strip()) > 1]
        # split snake_case or camelCase
        expanded = []
        for t in tokens:
            sub = [s.strip() for s in t.split("_") if len(s.strip()) > 1]
            expanded.extend(sub)
            if t not in expanded:
                expanded.append(t)
        return set(expanded)

    def compute_hybrid_score(
        self,
        query_tokens: set,
        item_name: str,
        item_desc: str,
        item_samples: List[str] | None = None,
        variant_keys: List[str] | None = None,
    ) -> float:
        item_tokens = self._tokenize(item_name)
        if item_desc:
            item_tokens.update(self._tokenize(item_desc))

        # 1. Keyword overlap (Jaccard-like or intersection ratio)
        intersection = query_tokens.intersection(item_tokens)
        keyword_overlap = (len(intersection) / max(1, len(query_tokens))) * 0.4

        # 2. Semantic/string similarity (difflib SequenceMatcher on name and query)
        query_str = " ".join(query_tokens)
        item_str = " ".join(item_tokens)
        semantic_similarity = (
            difflib.SequenceMatcher(None, query_str, item_str).quick_ratio() * 0.3
        )

        # 3. Business term overlap (exact token match in samples or ontology tags)
        business_term_overlap = 0.0
        if item_samples:
            sample_tokens = set()
            for s in item_samples:
                sample_tokens.update(self._tokenize(str(s)))
            if query_tokens.intersection(sample_tokens):
                business_term_overlap = 0.2

        if "[Ontology:" in (item_desc or ""):
            business_term_overlap += 0.1

        # 4. Variant key overlap
        variant_key_overlap = 0.0
        if variant_keys:
            vk_tokens = set()
            for vk in variant_keys:
                vk_tokens.update(self._tokenize(vk))
            if query_tokens.intersection(vk_tokens):
                variant_key_overlap = 0.2

        total_score = (
            semantic_similarity
            + keyword_overlap
            + business_term_overlap
            + variant_key_overlap
        )
        return round(min(1.0, total_score), 3)

    def retrieve_tables(
        self, query: str, context: SemanticContext, top_k: int | None = None
    ) -> List[SemanticTable]:
        if not context or not context.tables:
            return []

        k = top_k or self.config.max_tables_per_query
        query_tokens = self._expand_with_synonyms(self._tokenize(query))

        scored_tables: List[Tuple[float, SemanticTable]] = []
        for table in context.tables:
            # check table cols and keys
            all_samples = []
            all_vk = []
            for col in table.columns:
                all_samples.extend(col.sample_values)
                all_vk.extend(col.nested_keys)

            score = self.compute_hybrid_score(
                query_tokens, table.name, table.description or "", all_samples, all_vk
            )
            # If query mentions table exact name or token, give high boost
            tbl_base = table.name.lower().replace('"', "").split(".")[-1]
            if any(qt == tbl_base or qt in tbl_base for qt in query_tokens):
                score += 0.5

            scored_tables.append((score, table))

        scored_tables.sort(key=lambda x: x[0], reverse=True)
        # Filter by threshold and take top k
        filtered = [
            t for s, t in scored_tables if s >= self.similarity_threshold or s > 0.1
        ][:k]
        return filtered

    def retrieve_columns(
        self, query: str, table: SemanticTable, top_k: int | None = None
    ) -> List[SemanticColumn]:
        k = top_k or self.config.max_columns_per_table
        query_tokens = self._expand_with_synonyms(self._tokenize(query))

        scored_cols: List[Tuple[float, SemanticColumn]] = []
        for col in table.columns:
            score = self.compute_hybrid_score(
                query_tokens,
                col.name,
                col.description or "",
                col.sample_values,
                col.nested_keys,
            )

            # Boost identifiers (PK/FK) or standard core columns (like id, created_at)
            c_clean = col.name.lower().replace('"', "")
            if any(h == c_clean for h in ("id", "name", "code", "key", "status")):
                score += 0.25
            if any(qt == c_clean or qt in c_clean for qt in query_tokens):
                score += 0.5

            scored_cols.append((score, col))

        scored_cols.sort(key=lambda x: x[0], reverse=True)
        filtered = [
            c for s, c in scored_cols if s >= self.similarity_threshold or s > 0.05
        ][:k]
        return filtered

    def retrieve_variant_keys(
        self, query: str, col: SemanticColumn, top_k: int = 15
    ) -> List[str]:
        if not col.nested_keys:
            return []
        query_tokens = self._tokenize(query)

        scored_keys: List[Tuple[float, str]] = []
        for key in col.nested_keys:
            key_tokens = self._tokenize(key)
            overlap = len(query_tokens.intersection(key_tokens)) / max(
                1, len(query_tokens)
            )
            score = overlap + (
                difflib.SequenceMatcher(None, " ".join(query_tokens), key).quick_ratio()
                * 0.5
            )
            scored_keys.append((score, key))

        scored_keys.sort(key=lambda x: x[0], reverse=True)
        return [k for s, k in scored_keys if s > 0.05][:top_k]
