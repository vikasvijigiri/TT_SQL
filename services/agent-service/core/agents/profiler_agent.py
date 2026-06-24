import re

from typing import List

from core.sql.db_executor import DatabaseExecutor

from core.utils.logger import logger





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

            t_clean = t.strip().rstrip("'s").rstrip("'s").strip()

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



        # 4. Check if column name suggests a structured JSON/serialized attribute bag --

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

    def _extract_structured_keys(sample_values: list[str]) -> list[str]:

        """

        Generic key extractor for structured text columns.



        When a column stores JSON objects ({"key": val}) or Python-serialized dicts

        ({'key': val}), extract the top-level keys so StrategyRouter knows the column

        is queryable via json_extract() or LIKE patterns -- not a semantic gap.



        Works purely from sample text -- no hardcoding of field names.

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

                    escaped_term = term.replace("'", "--")

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

                # json_extract() or LIKE -- preventing premature cannot_answer.

                if sample_vals:

                    extracted_keys = self._extract_structured_keys(sample_vals)

                    if extracted_keys:

                        insight += (

                            "- **Structured Attribute Keys (queryable via json_extract or LIKE):**\n"

                            f"  * Detected keys: {', '.join(f'`{k}`' for k in extracted_keys)}\n"

                            "  * Use `json_extract_string(col, '$.KeyName')` or `col LIKE '%KeyName%value%'` to filter on these keys.\n"

                            "  * This column is NOT a semantic gap -- it is queryable via SQL pattern matching.\n"

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

