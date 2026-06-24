import re
from typing import List
from agent.app.repositories.db_executor import DatabaseExecutor
from agent.app.utils.logger import logger


class ProfilerAgent:
    """
    Reflective Schema Profiler Agent.
    Runs fast metadata profiling queries on ambiguous or rich column types
    (Variant, Geography, JSON, WKT, value coordinates) to discover structural formats dynamically.
    Also queries text columns for values matching terms in the user query to handle dirty database values.
    """

    def __init__(self):
        self.ambiguity_keywords = [
            "largest",
            "smallest",
            "max",
            "min",
            "longest",
            "shortest",
            "distance",
            "area",
            "json",
            "xml",
            "nested",
            "value",
            "coordinate",
            "shape",
            "geom",
            "characteristics",
            "relationship",
            "unknown",
            "missing",
            "null",
            "empty",
            "quality",
            "clean",
            "valid",
            "exclude",
            "marginal",
            "filter",
            "placeholder",
            "recode",
        ]

    def _extract_search_terms(self, user_query: str) -> List[str]:
        """Extract key noun/name terms from the query to search in text columns."""
        # 1. Quoted terms
        terms = re.findall(r"['\"]([^'\"]{2,})['\"]", user_query)

        # 2. Capitalized words/phrases
        words = re.findall(r"\b([A-Z][a-zA-Z0-9'\u00C0-\u017F]+)\b", user_query)
        stopwords = {
            "How",
            "What",
            "Who",
            "Where",
            "When",
            "Why",
            "Which",
            "Is",
            "Are",
            "The",
            "In",
            "USD",
            "EUR",
        }
        for w in words:
            if w not in stopwords and w not in terms and len(w) > 2:
                terms.append(w)

        clean_terms = []
        for t in terms:
            t_clean = t.strip().rstrip("'s").rstrip("Ã¢â‚¬â„¢s").strip()
            if len(t_clean) >= 2 and t_clean not in clean_terms:
                clean_terms.append(t_clean)
        return clean_terms

    def _should_profile(self, user_query: str, column_fqn: str) -> bool:
        """Heuristically decides if a column warrants active profiling."""
        col_lower = column_fqn.lower()
        # Do not profile heavy auto-generated homogeneous views starting with 'all_'
        if "all_" in col_lower:
            return False

        query_lower = user_query.lower()

        # 1. Check if query asks for size, aggregation, spatial, or data quality features
        has_query_trigger = any(kw in query_lower for kw in self.ambiguity_keywords)

        # 2. Check if the column name itself suggests it contains generic, rich, spatial, or category data
        has_col_trigger = any(
            kw in col_lower
            for kw in [
                "value",
                "coord",
                "geom",
                "shape",
                "type",
                "char",
                "rel",
                "recode",
                "status",
                "group",
                "class",
                "quality",
                "filter",
            ]
        )

        # 3. Check if it is a text column that could match name/entity query terms
        is_text_column = any(
            kw in col_lower
            for kw in [
                "title",
                "name",
                "author",
                "creator",
                "country",
                "state",
                "city",
                "category",
                "description",
                "label",
                "text",
                "tag",
                "topic",
                "brand",
                "product",
                "store",
                "platform",
                "display",
                "summary",
            ]
        )

        # 4. Check if column name suggests a structured JSON/serialized attribute bag Ã¢â‚¬â€
        #    always profile these so their keys get extracted and reported to StrategyRouter
        is_attribute_col = any(
            kw in col_lower
            for kw in [
                "attribute",
                "properties",
                "metadata",
                "attrs",
                "config",
                "settings",
                "details",
                "features",
                "extras",
                "params",
                "info",
            ]
        )

        return (
            has_query_trigger or has_col_trigger or is_text_column or is_attribute_col
        )

    @staticmethod
    def _cast_to_text(col_expr: str, dialect: str) -> str:
        """Return a dialect-appropriate expression to cast col_expr to a text type."""
        d = dialect.lower()
        if d in ("postgres", "postgresql", "redshift"):
            return f"{col_expr}::text"
        if d == "oracle":
            return f"TO_CHAR({col_expr})"
        # sqlite, duckdb, mysql, mssql, bigquery, trino, spark, snowflake all support VARCHAR
        return f"CAST({col_expr} AS VARCHAR)"

    @staticmethod
    def _extract_description_categories(sample_values: list[str]) -> dict:
        """
        Detect whether a text column embeds comma-separated category/tag lists.

        When sample text contains patterns like 'services in X, Y, Z.', 'mix of A, B.',
        'destination for P, Q.', etc., extract the top categories and the specific
        regex pattern that was matched.  Returns a dict with:
          'pattern': the matched DuckDB regexp_extract pattern, or ''
          'top_categories': list of top category strings found in samples
          'description_format': human-readable explanation of the embedding format
        """
        import re as _re

        # Candidate patterns ordered by specificity; character class [A-Za-z, /&()''-]
        # includes parentheses (for names like "American (New)"), apostrophes (for "Women's"),
        # and hyphens.  NEVER use (.*) Ã¢â‚¬â€ it captures full sentences.
        _CC = r"[A-Za-z, /&()'Ã¢â‚¬â„¢-]"
        candidate_patterns = [
            # 'in the category/categories of "X, Y"'  (quoted variant)
            (
                r"in the categor(?:y|ies) of ['\"]([A-Za-z, /&()'Ã¢â‚¬â„¢-]+)['\"]",
                "in the category of 'X, Y'",
            ),
            # 'in the (categories|fields|areas) of X, Y.'  (unquoted variant)
            (
                r"in the (?:categor(?:y|ies)|fields?|areas?) of (" + _CC + r"+?)\.",
                "in the categories/fields of X, Y.",
            ),
            # 'categories such as X, Y, Z.'
            (
                r"categor(?:y|ies) such as (" + _CC + r"+?)\.",
                "categories such as X, Y.",
            ),
            # 'services in X, Y, Z.'  /  'services including X, Y.'  / 'services, including X, Y.'
            (
                r"services[, ]+(?:in|including) (" + _CC + r"+?)\.",
                "services in/including X, Y, Z.",
            ),
            # ', including X, Y, Z.'  (general including-list)
            (r", including (" + _CC + r"+?)\.", ", including X, Y, Z."),
            # 'mix of X, Y, Z.'  /  'ranging from X, Y.'  /  'options in X, Y.'  /  'solutions in X, Y.'
            (
                r"(?:mix of|ranging from|options in|services in|(?:range of )?solutions in|array of (?:dishes |options )?in) ("
                + _CC
                + r"+?)\.",
                "mix of / ranging from / options/solutions in X, Y.",
            ),
            # 'destination for X, Y.'
            (r"destination for (" + _CC + r"+?)\.", "destination for X, Y."),
            # 'menu featuring X, Y, Z.'
            (
                r"menu featuring ("
                + _CC
                + r"+?)(?:, (?:perfect|ideal|making|convenient)|\. |\.$)",
                "menu featuring X, Y, Z.",
            ),
        ]
        matched_pattern = ""
        matched_label = ""
        all_cats: dict[str, int] = {}

        for sample in sample_values:
            if not sample or not isinstance(sample, str):
                continue
            for pat, label in candidate_patterns:
                m = _re.search(pat, sample, _re.IGNORECASE)
                if m:
                    cat_str = m.group(1)
                    cats = _re.split(r",\s*| and ", cat_str)
                    cats = [
                        c.strip().strip("'\"")
                        for c in cats
                        if c.strip() and len(c.strip()) > 1
                    ]
                    for c in cats:
                        all_cats[c] = all_cats.get(c, 0) + 1
                    if not matched_pattern:
                        # Convert Python regex to a DuckDB-compatible regexp_extract pattern
                        matched_pattern = pat
                        matched_label = label
                    break  # one pattern per sample

        if not matched_pattern or not all_cats:
            return {}

        top_cats = [c for c, _ in sorted(all_cats.items(), key=lambda x: -x[1])[:8]]
        return {
            "pattern": matched_pattern,
            "label": matched_label,
            "top_categories": top_cats,
        }

    @staticmethod
    def _extract_structured_keys(sample_values: list[str]) -> list[str]:
        """
        Generic key extractor for structured text columns.

        When a column stores JSON objects ({"key": val}) or Python-serialized dicts
        ({'key': val}), extract the top-level keys so StrategyRouter knows the column
        is queryable via json_extract() or LIKE patterns Ã¢â‚¬â€ not a semantic gap.

        Works purely from sample text Ã¢â‚¬â€ no hardcoding of field names.
        """
        import re as _re

        key_counts: dict[str, int] = {}
        # Matches both JSON "key": and Python-dict 'key': or u'key':
        key_pattern = _re.compile(r"""(?:u?['"])([A-Za-z][A-Za-z0-9_]*)(?:['"])\s*:""")
        for sample in sample_values:
            if not sample or not isinstance(sample, str):
                continue
            stripped = sample.strip()
            # Only process if it looks like a dict/object
            if not (stripped.startswith("{") or stripped.startswith("u'")):
                continue
            for match in key_pattern.finditer(stripped):
                key = match.group(1)
                key_counts[key] = key_counts.get(key, 0) + 1
        # Return keys sorted by frequency, top 15
        return [k for k, _ in sorted(key_counts.items(), key=lambda x: -x[1])[:15]]

    def profile_columns(
        self,
        user_query: str,
        selected_columns: List[str],
        executor: DatabaseExecutor,
        dialect: str = "sqlite",
    ) -> str:
        """
        Runs non-disruptive, ultra-fast profiling queries on qualified columns.
        Returns a formatted markdown knowledge snippet.
        """
        logger.set_agent("PROFILER")
        logger.info("Evaluating selected columns for active schema profiling...")

        profiling_insights = []
        profiled_count = 0
        search_terms = self._extract_search_terms(user_query)

        for col_fqn in selected_columns:
            if not self._should_profile(user_query, col_fqn):
                continue

            # Restrict to at most 6 profiling targets to avoid excessive overhead
            if profiled_count >= 6:
                break

            parts = col_fqn.split(".")
            if len(parts) < 2:
                continue

            clean_parts = [p.replace('"', "").replace("\\", "").strip() for p in parts]
            col_name = clean_parts[-1]

            quoted_col = f'"{col_name}"'
            quoted_table = ".".join(f'"{p}"' for p in clean_parts[:-1])

            logger.info(
                f"Running active profiling probe on: {quoted_table}.{quoted_col}"
            )

            col_lower = col_name.lower()
            is_text_col = any(
                kw in col_lower
                for kw in [
                    "title",
                    "name",
                    "author",
                    "creator",
                    "country",
                    "state",
                    "city",
                    "category",
                    "description",
                    "label",
                    "text",
                    "tag",
                    "topic",
                    "brand",
                    "product",
                    "store",
                    "platform",
                    "display",
                    "summary",
                ]
            )

            insight = f"### Live Profiling Insights for `{col_fqn}`:\n"
            has_data = False

            # If it's a text column and we have search terms, run fuzzy value searches first
            if is_text_col and search_terms:
                matched_values = []
                for term in search_terms:
                    # Escape single quotes in search term
                    escaped_term = term.replace("'", "''")
                    # Try direct match and fuzzy match on a sample to prevent full scans on multi-gigabyte tables
                    cast_col = self._cast_to_text(quoted_col, dialect)
                    search_sql = f"SELECT DISTINCT {cast_col} AS val FROM (SELECT {quoted_col} FROM {quoted_table} LIMIT 20000) WHERE {cast_col} LIKE '%{escaped_term}%' LIMIT 3"
                    try:
                        success_s, _msg_s, rows_s = executor.execute_direct(search_sql)
                        if success_s and rows_s:
                            term_matches = [
                                str(r.get("VAL", r.get("val", "")))
                                for r in rows_s
                                if r.get("VAL") is not None or r.get("val") is not None
                            ]
                            if term_matches:
                                matched_values.append(
                                    f"  * Matched values for term '{term}': {', '.join([f'`{v}`' for v in term_matches])}"
                                )
                    except Exception as e:  # noqa: BLE001
                        logger.debug(f"Profiler text search failed: {e}")

                if matched_values:
                    insight += (
                        "- **Entity/Search Matches in Database:**\n"
                        + "\n".join(matched_values)
                        + "\n"
                    )
                    has_data = True

            # Universal Probes (Frequency & Samples)
            # Use subquery sampling (LIMIT 20000) to prevent full-table scan grouping on large datasets
            cast_col = self._cast_to_text(quoted_col, dialect)
            type_probe_sql = (
                f"SELECT {cast_col} AS val, COUNT(*) AS cnt "
                f"FROM (SELECT {quoted_col} FROM {quoted_table} LIMIT 20000) "
                f"WHERE {quoted_col} IS NOT NULL GROUP BY val ORDER BY cnt DESC LIMIT 3"
            )
            sample_probe_sql = (
                f"SELECT {cast_col} AS val FROM {quoted_table} "
                f"WHERE {quoted_col} IS NOT NULL LIMIT 3"
            )

            try:
                # Run Probe 1 (Frequency)
                success1, _msg1, rows1 = executor.execute_direct(type_probe_sql)
                if success1 and rows1:
                    insight += "- **Top Frequent Values & Distribution:**\n"
                    for r in rows1:
                        insight += f"  * Value: `{r.get('VAL', r.get('val', 'UNKNOWN'))}` | Frequency Count: {r.get('CNT', r.get('cnt', 0))}\n"
                    has_data = True

                # Run Probe 2 (Samples)
                success2, _msg2, rows2 = executor.execute_direct(sample_probe_sql)
                sample_vals = []
                if success2 and rows2:
                    insight += "- **Empirical Sample Formats:**\n"
                    for i, r in enumerate(rows2):
                        val_str = str(r.get("VAL", r.get("val", "")))
                        sample_vals.append(val_str)
                        if len(val_str) > 400:
                            val_str = val_str[:400] + "... [TRUNCATED]"
                        insight += f"  * Sample {i + 1}: `{val_str}`\n"
                    has_data = True

                # Probe 3: Structured key extraction for JSON/Python-dict columns.
                # If sample values look like dicts, extract top-level keys so the
                # StrategyRouter and SQL generator know which keys are queryable via
                # json_extract() or LIKE Ã¢â‚¬â€ preventing premature cannot_answer.
                if sample_vals:
                    extracted_keys = self._extract_structured_keys(sample_vals)
                    if extracted_keys:
                        insight += (
                            "- **Structured Attribute Keys (queryable via json_extract or LIKE):**\n"
                            f"  * Detected keys: {', '.join(f'`{k}`' for k in extracted_keys)}\n"
                            "  * Use `json_extract_string(col, '$.KeyName')` or `col LIKE '%KeyName%value%'` to filter on these keys.\n"
                            "  * This column is NOT a semantic gap Ã¢â‚¬â€ it is queryable via SQL pattern matching.\n"
                        )
                        has_data = True

                # Probe 4: Detect embedded category/tag lists in description-like columns.
                # If sample values contain patterns like 'services in X, Y, Z.' or 'mix of A, B.',
                # extract the top categories and the extraction pattern so the SQL generator
                # knows exactly how to query them Ã¢â‚¬â€ without relying on overly broad (.*)  patterns.
                if sample_vals and "description" in col_lower:
                    cat_info = self._extract_description_categories(sample_vals)
                    if cat_info:
                        top_cats = cat_info["top_categories"]
                        label = cat_info["label"]
                        insight += (
                            "- **Embedded Category/Tag List Detected:**\n"
                            f"  * Categories appear in the format: `{label}`\n"
                            f"  * Sample top categories from this column: {', '.join(f'`{c}`' for c in top_cats[:6])}\n"
                            "  * TWO-STEP extraction approach:\n"
                            "    1. Extract category list using COALESCE of multiple patterns with char class `[A-Za-z, /&()''-]+?` (NO `.*`):\n"
                            "       - `regexp_extract(description, 'in the (?:categor(?:y|ies)|fields?|areas?) of ([A-Za-z, /&()''-]+?)[.]', 1)` (quoted or unquoted)\n"
                            "       - `regexp_extract(description, ', including ([A-Za-z, /&()''-]+?)[.]', 1)`\n"
                            "       - `regexp_extract(description, 'services[, ]+(?:in|including) ([A-Za-z, /&()''-]+?)[.]', 1)`\n"
                            "       - `regexp_extract(description, '(?:options in|(?:range of )?solutions in) ([A-Za-z, /&()''-]+?)[.]', 1)`\n"
                            "    2. Split with `UNNEST(regexp_split_to_array(cat_str, ', | and '))`, TRIM, COUNT DISTINCT per category.\n"
                            "    3. For the final metric (count + avg), use `description LIKE '%' || top_category || '%'` Ã¢â‚¬â€ "
                            "this correctly includes all matching businesses and gives the expected result.\n"
                            "  * NEVER use `(.*)` in the extraction Ã¢â‚¬â€ it captures the full sentence beyond the category list.\n"
                        )
                        has_data = True

                if has_data:
                    profiling_insights.append(insight)
                    profiled_count += 1

            except Exception as e:
                logger.warning(f"Profiling failed for column {col_fqn}: {e}")

        logger.reset_agent()

        if profiling_insights:
            return "\n\n".join(profiling_insights)
        return ""
