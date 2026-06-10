"""
text_classify_executor.py
--------------------------
Executes the "text_classify_aggregate" strategy chosen by StrategyRouter.

Flow
----
1. Run the fetch_sql provided by StrategyRouter to get rows with text fields
2. Batch-classify each row via LLM (classify_spec describes categories + instruction)
3. Aggregate classified rows in Python
4. Return a human-readable answer string

Design principles
-----------------
- No hardcoding: categories, fetch SQL, and classification instruction all come
  from the LLM-produced classify_spec, derived from the actual data at runtime
- Batch LLM calls: classify up to BATCH_SIZE rows per LLM call to keep cost low
- Graceful degradation: if the dataset is huge, work from a representative sample
  and state that clearly in the answer
- The answer format matches what the question asked (e.g. "Africa" not a DataFrame)
"""

from __future__ import annotations

import json
import math
import re
import pandas as pd
import html

from backend.app.utils.llm import LLMClient
from backend.app.utils.logger import logger

def _clean_html_text(text: str) -> str:
    if not text:
        return ""
    # Unescape HTML entities (e.g. &lt; -> <, &quot; -> ")
    val = html.unescape(str(text))
    # Strip HTML tags
    val = re.sub(r'<[^>]+>', ' ', val)
    # Normalize spaces
    val = re.sub(r'\s+', ' ', val)
    return val.strip()

# Rows per LLM classification call
BATCH_SIZE = 15
# Max rows to classify before switching to sampling (controls cost + latency)
MAX_ROWS_EXACT = 500
MAX_ROWS_SAMPLE = 2000

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """You are a precise text classifier.

For each item in the list below, assign exactly one category from the allowed list.
Base your decision solely on the text content provided — no assumptions, no external knowledge.

Respond ONLY with a JSON array of objects, one per input item, in the same order:
[
  {"id": <row_id>, "category": "<chosen category>"},
  ...
]"""

_CLASSIFY_USER_TMPL = """Allowed categories: {categories}

Classification instruction: {instruction}

Items to classify:
{items_json}"""

_ANSWER_SYSTEM = """You are a precise answer formatter.

Given a question and a data table of aggregated counts by group, produce a concise
natural-language answer that directly answers the question.
Do not add speculation. Use the data as-is.

Respond with a single short sentence that is the answer — e.g. "Africa" or "42" or
"Africa, with 312 articles" — matching the expected answer format for the question."""

_ANSWER_USER_TMPL = """Question: {question}

Aggregated data:
{agg_table}

What is the answer?"""


class TextClassifyExecutor:
    """
    Runs fetch → classify → aggregate → answer for text-encoded attributes.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def execute(self, question: str, classify_spec: dict, executor) -> str:
        """
        Returns a plain-text answer string or raises RuntimeError on hard failure.
        """
        fetch_sql = classify_spec.get("fetch_sql", "").strip()
        group_col = classify_spec.get("group_column", "")
        text_cols = classify_spec.get("text_columns", [])
        categories = classify_spec.get("categories", [])
        target = classify_spec.get("target_category", "")
        instruction = classify_spec.get("classification_instruction", "")

        if not fetch_sql or not categories:
            raise RuntimeError("classify_spec is missing fetch_sql or categories")

        # Determine sorting before fetching to optimize DB retrieval for max/min text property queries
        q_lower = question.lower()
        sql_sort = ""
        target_text_col = None
        if text_cols:
            best_col = text_cols[0]
            best_score = -1
            comparison_words = ["longest", "greatest", "maximum", "max", "character", "characters", "length", "shortest", "least", "minimum", "min"]
            
            for tc in text_cols:
                tc_lower = tc.lower()
                if tc_lower in q_lower:
                    # Basic proximity score to comparison words
                    idx_col = q_lower.find(tc_lower)
                    min_dist = len(q_lower)
                    for cw in comparison_words:
                        idx_cw = q_lower.find(cw)
                        if idx_cw != -1:
                            dist = abs(idx_cw - idx_col)
                            if dist < min_dist:
                                min_dist = dist
                    
                    score = len(q_lower) - min_dist
                    
                    # Syntactic association boosts
                    if f"whose {tc_lower}" in q_lower:
                        score += 1000
                    if f"length of {tc_lower}" in q_lower:
                        score += 1000
                    if f"longest {tc_lower}" in q_lower or f"shortest {tc_lower}" in q_lower:
                        score += 1000
                    if f"{tc_lower} has the" in q_lower or f"{tc_lower} is the" in q_lower:
                        score += 1000
                        
                    if score > best_score:
                        best_score = score
                        best_col = tc
            target_text_col = best_col

        if target_text_col:
            if any(w in q_lower for w in ["longest", "greatest", "maximum", "max", "character", "length"]):
                sql_sort = f" ORDER BY LENGTH({target_text_col}) DESC"
            elif any(w in q_lower for w in ["shortest", "least", "minimum", "min"]):
                sql_sort = f" ORDER BY LENGTH({target_text_col}) ASC"

        # Inject order by into fetch_sql if not already present
        has_existing_order = "order by" in fetch_sql.lower()
        if sql_sort and not has_existing_order:
            fetch_sql = f"{fetch_sql.rstrip(';')}{sql_sort}"

        # ------------------------------------------------------------------
        # Step 1: Fetch rows
        # ------------------------------------------------------------------
        logger.info(f"[TextClassifyExecutor] Fetching rows: {fetch_sql[:120]}...")
        ok, err, rows = executor.execute_direct(fetch_sql)
        if not ok or not rows:
            return f"No data found for the query ({err}). Cannot determine the answer."
        df = pd.DataFrame(rows)
        if df is None or df.empty:
            return f"No data found for the query. Cannot determine the answer."

        total_rows = len(df)
        sampled = False

        if sql_sort or has_existing_order:
            # If sorted, take the top rows to preserve the sorting hierarchy
            # Cap at 300 rows (instead of 2000) for sorted queries to save costs/tokens and keep batching fast.
            sorted_limit = 300
            if total_rows > sorted_limit:
                logger.info(
                    f"[TextClassifyExecutor] {total_rows} rows — keeping top {sorted_limit} rows to preserve order"
                )
                df = df.head(sorted_limit).reset_index(drop=True)
                sampled = True
        else:
            if total_rows > MAX_ROWS_SAMPLE:
                # Too large even for sampling — use a stratified sample grouped by group_col
                logger.info(
                    f"[TextClassifyExecutor] {total_rows} rows — using stratified sample "
                    f"({MAX_ROWS_SAMPLE} rows)"
                )
                if group_col and group_col in df.columns:
                    n_groups = max(df[group_col].nunique(), 1)
                    n_per_group = MAX_ROWS_SAMPLE // n_groups
                    if n_per_group > 0:
                        sampled_dfs = []
                        for name, group in df.groupby(group_col):
                            sampled_dfs.append(group.sample(min(len(group), n_per_group), random_state=42))
                        df = pd.concat(sampled_dfs, ignore_index=True)
                    else:
                        # High cardinality grouping column: fall back to simple random sample to keep target size
                        df = df.sample(MAX_ROWS_SAMPLE, random_state=42).reset_index(drop=True)
                else:
                    df = df.sample(MAX_ROWS_SAMPLE, random_state=42).reset_index(drop=True)
                sampled = True
            elif total_rows > MAX_ROWS_EXACT:
                logger.info(
                    f"[TextClassifyExecutor] {total_rows} rows — sampling {MAX_ROWS_SAMPLE}"
                )
                df = df.sample(min(total_rows, MAX_ROWS_SAMPLE), random_state=42).reset_index(drop=True)
                sampled = True

        logger.info(
            f"[TextClassifyExecutor] Classifying {len(df)} rows "
            f"({'sample' if sampled else 'full'}) into {len(categories)} categories"
        )

        # ------------------------------------------------------------------
        # Step 2: Batch-classify
        # ------------------------------------------------------------------
        df["_category"] = None
        n_batches = math.ceil(len(df) / BATCH_SIZE)

        for batch_idx in range(n_batches):
            batch = df.iloc[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
            items = []
            for _, row in batch.iterrows():
                text_parts = {c: _clean_html_text(row[c])[:1000] for c in text_cols if c in row.index}
                items.append({"id": int(row.name), "text": text_parts})

            try:
                raw = self.llm.generate(
                    system_prompt=_CLASSIFY_SYSTEM,
                    user_prompt=_CLASSIFY_USER_TMPL.format(
                        categories=", ".join(categories),
                        instruction=instruction,
                        items_json=json.dumps(items, ensure_ascii=False),
                    ),
                )
                raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
                parsed = self._parse_classifications(raw)
                for item in parsed:
                    row_id = item.get("id")
                    cat = item.get("category", "")
                    if row_id is not None and row_id in df.index:
                        df.at[row_id, "_category"] = cat
                logger.info(
                    f"[TextClassifyExecutor] Batch {batch_idx+1}/{n_batches} done"
                )
            except Exception as e:
                logger.warning(f"[TextClassifyExecutor] Batch {batch_idx+1} failed: {e}")
                continue

        # ------------------------------------------------------------------
        # Step 3: Filter to target category and aggregate
        # ------------------------------------------------------------------
        classified = df.dropna(subset=["_category"])
        if target:
            subset = classified[
                classified["_category"].str.lower() == target.lower()
            ].copy()
        else:
            subset = classified.copy()

        if subset.empty:
            return (
                f"After classifying {'a sample of ' if sampled else ''}{total_rows} rows, "
                f"no rows matched the '{target}' category. Cannot determine the answer."
            )

        # Enrich subset with text column lengths to support queries about longest/shortest text
        for col in text_cols:
            if col in subset.columns:
                try:
                    subset[f"{col}_length"] = subset[col].astype(str).str.len()
                except Exception:
                    pass

        # Determine if the question is asking for a maximum/longest/greatest or minimum/shortest text property
        sort_col = None
        ascending = False
        q_lower = question.lower()
        if target_text_col:
            length_col = f"{target_text_col}_length"
            if length_col in subset.columns:
                if any(w in q_lower for w in ["longest", "greatest", "maximum", "max", "character", "length"]):
                    sort_col = length_col
                    ascending = False
                elif any(w in q_lower for w in ["shortest", "least", "minimum", "min"]):
                    sort_col = length_col
                    ascending = True
        
        # Fallback to any length column if target_text_col matching failed
        if not sort_col:
            length_cols = [c for c in subset.columns if str(c).endswith("_length")]
            if length_cols:
                sort_col = length_cols[0]
                if any(w in q_lower for w in ["longest", "greatest", "maximum", "max", "character", "length"]):
                    ascending = False
                elif any(w in q_lower for w in ["shortest", "least", "minimum", "min"]):
                    ascending = True

        if sort_col:
            subset = subset.sort_values(sort_col, ascending=ascending)
            # Project relevant columns: group_col, text_cols, and length cols
            cols_to_show = [c for c in [group_col] + text_cols + [sort_col] if c and c in subset.columns]
            cols_to_show = list(dict.fromkeys(cols_to_show))
            agg_df = subset[cols_to_show].head(30)
            agg_text = agg_df.to_string(index=False)
        elif group_col and group_col in subset.columns:
            agg = (
                subset.groupby(group_col)
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )
            agg_text = agg.to_string(index=False)
        else:
            agg = pd.DataFrame({"count": [len(subset)]})
            agg_text = agg.to_string(index=False)
        logger.info(f"[TextClassifyExecutor] Aggregation:\n{agg_text}")

        # ------------------------------------------------------------------
        # Step 4: LLM formats the final answer
        # ------------------------------------------------------------------
        sample_note = (
            f"\n(Note: based on a stratified sample of {len(df)}/{total_rows} rows)"
            if sampled else ""
        )
        try:
            answer_raw = self.llm.generate(
                system_prompt=_ANSWER_SYSTEM,
                user_prompt=_ANSWER_USER_TMPL.format(
                    question=question,
                    agg_table=agg_text + sample_note,
                ),
            )
            answer_raw = re.sub(r"<think>.*?</think>", "", answer_raw, flags=re.S).strip()
            # Strip wrapper phrases, keep the core answer
            answer = answer_raw.strip().strip('"').strip("'")
        except Exception:
            # Fallback: return top group directly
            answer = str(agg.iloc[0, 0]) if not agg.empty else "Unknown"

        logger.info(f"[TextClassifyExecutor] Final answer: {answer}")
        return answer

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_classifications(raw: str) -> list[dict]:
        """Extract JSON array from LLM classification response."""
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start == -1 or end == 0:
            return []
        try:
            return json.loads(raw[start:end])
        except Exception:
            return []
