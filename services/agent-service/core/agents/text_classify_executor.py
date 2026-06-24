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



from core.utils.llm import LLMClient

from core.utils.logger import logger

import contextlib





def _clean_html_text(text: str) -> str:

    if not text:

        return ""

    # Unescape HTML entities (e.g. &lt; -> <, &quot; -> ")

    val = html.unescape(str(text))

    # Strip HTML tags

    val = re.sub(r"<[^>]+>", " ", val)

    # Normalize spaces

    val = re.sub(r"\s+", " ", val)

    return val.strip()





# Rows per LLM classification call - dynamically scaled between 50 and 70 based on text length.

BATCH_SIZE = 70

# Max rows to classify before switching to sampling (controls cost + latency)

MAX_ROWS_EXACT = 500

MAX_ROWS_SAMPLE = 500



# ---------------------------------------------------------------------------

# Prompts

# ---------------------------------------------------------------------------



_CLASSIFY_SYSTEM = """You are a precise text classifier.



For each item in the list below, assign exactly one category from the allowed categories provided in the instruction.



Base your decision solely on the text content provided - no assumptions, no external knowledge.



Respond ONLY with a JSON array of objects, one per input item, in the same order:

[

  {"id": <row_id>, "category": "<chosen category>"},

  ...

]"""



_CLASSIFY_USER_TMPL = """Dataset context (if any):

{db_context}



Allowed categories: {categories}



Classification instruction: {instruction}



Items to classify:

{items_json}"""



_ANSWER_SYSTEM = """You are a precise answer formatter.



Given a question and a data table of aggregated counts by group, produce a concise

natural-language answer that directly answers the question.

Do not add speculation. Use the data as-is.



Respond with a single short sentence that is the answer -- e.g. "Africa" or "42" or

"Africa, with 312 articles" -- matching the expected answer format for the question."""



_ANSWER_USER_TMPL = """Question: {question}



Aggregated data:

{agg_table}



What is the answer?"""





def _fetch_from_mongodb(executor, id_col: str, ids: list, cols: list) -> dict:

    """Fetch documents from MongoDB for cross-database join support."""

    import os

    import pymongo

    import contextlib

    from pathlib import Path



    db_name_raw = getattr(executor, "db_name", "UNKNOWN").lower()



    # Try loading .env from DataAgentBench repository if MONGO_URI is not in current environment

    if not os.getenv("MONGO_URI"):

        with contextlib.suppress(Exception):

            from config.config import DAB_REPO

            from dotenv import load_dotenv

            dab_env = Path(DAB_REPO) / ".env"

            if dab_env.exists():

                load_dotenv(str(dab_env))



    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

    logger.info(f"[TextClassifyExecutor] Connecting to MongoDB: {mongo_uri}")



    try:

        with pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=2000) as client:

            db = None

            actual_col = None

            # Generically find the first user database and collection

            for db_cand_name in client.list_database_names():

                if db_cand_name in ("admin", "config", "local"):

                    continue

                cand_db = client[db_cand_name]

                cols = cand_db.list_collection_names()

                valid_cols = [c for c in cols if not c.startswith("system.")]

                if valid_cols:

                    db = cand_db

                    actual_col = valid_cols[0]

                    break

            

            if not db or not actual_col:

                logger.warning("[TextClassifyExecutor] No non-system collection found in MongoDB")

                return {}

                

            collection = db[actual_col]

            

            # Inspect keys from a sample document

            sample_doc = collection.find_one()

            if not sample_doc:

                logger.warning(f"[TextClassifyExecutor] Collection '{actual_col}' is empty in MongoDB")

                return {}

                

            # Find key in MongoDB that matches id_col

            mongo_id_key = None

            for k in sample_doc.keys():

                if k.lower() == id_col.lower():

                    mongo_id_key = k

                    break

            

            if not mongo_id_key:

                if "_id" in sample_doc:

                    mongo_id_key = "_id"

                else:

                    logger.warning(f"[TextClassifyExecutor] ID column '{id_col}' not found in MongoDB keys: {list(sample_doc.keys())}")

                    return {}

            

            # Query documents by matching ID in list

            # Create variations (int, str, raw) of IDs to ensure type matching

            id_list = []

            for idx in ids:

                id_list.append(idx)

                with contextlib.suppress(Exception):

                    id_list.append(int(idx))

                with contextlib.suppress(Exception):

                    id_list.append(str(idx))

            

            query = {mongo_id_key: {"$in": id_list}}

            

            # Build projection

            projection = {mongo_id_key: 1}

            for col in cols:

                for k in sample_doc.keys():

                    if k.lower() == col.lower():

                        projection[k] = 1

            

            cursor = collection.find(query, projection)

            

            # Map results

            res_map = {}

            for doc in cursor:

                doc_id = doc.get(mongo_id_key)

                vals = {}

                for col in cols:

                    for k, v in doc.items():

                        if k.lower() == col.lower():

                            vals[col] = v

                            break

                res_map[doc_id] = vals

                res_map[str(doc_id)] = vals

                with contextlib.suppress(Exception):

                    res_map[int(doc_id)] = vals

            

            logger.info(f"[TextClassifyExecutor] Fetched {len(res_map) // 3} matching documents from MongoDB.")

            return res_map

    except Exception as e:

        logger.warning(f"[TextClassifyExecutor] Failed to fetch missing columns from MongoDB: {e}")

        return {}





def _fetch_missing_columns(df, id_col, missing_cols, executor):

    if id_col not in df.columns:

        return df



    ids = df[id_col].dropna().unique().tolist()

    if not ids:

        return df



    ok, err, tbl_rows = executor.execute_direct(

        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "

        "UNION "

        "SELECT name FROM sqlite_temp_master WHERE type IN ('table', 'view')"

    )

    is_sqlite = ok

    if not ok:

        ok, err, tbl_rows = executor.execute_direct("SHOW TABLES")

        is_sqlite = False

        if not ok:

            logger.warning(f"Failed to list tables for missing columns: {err}")

            return df



    tables = []

    if is_sqlite:

        tables = [r["name"] for r in tbl_rows]

    else:

        if tbl_rows:

            col_name = list(tbl_rows[0].keys())[0]

            tables = [r[col_name] for r in tbl_rows]



    table_columns = {}

    for tbl in tables:

        if is_sqlite:

            ok, err, col_rows = executor.execute_direct(f'PRAGMA table_info("{tbl}")')

            if ok:

                table_columns[tbl] = [r["name"] for r in col_rows]

        else:

            ok, err, col_rows = executor.execute_direct(f'DESCRIBE "{tbl}"')

            if ok:

                table_columns[tbl] = [r["column_name"] if "column_name" in r else r[list(r.keys())[0]] for r in col_rows]



    table_to_cols = {}

    for col in missing_cols:

        for tbl, cols in table_columns.items():

            if id_col in cols and col in cols:

                table_to_cols.setdefault(tbl, []).append(col)

                break



    # If no SQL tables contain the missing columns, attempt fallback to MongoDB

    if not table_to_cols:

        logger.info(f"[TextClassifyExecutor] Columns {missing_cols} not found in SQL tables. Attempting MongoDB lookup...")

        mongo_data = _fetch_from_mongodb(executor, id_col, ids, missing_cols)

        if mongo_data:

            for col in missing_cols:

                # Map retrieved values from MongoDB to the DataFrame

                val_map = {id_val: item.get(col) for id_val, item in mongo_data.items() if item}

                df[col] = df[id_col].map(val_map)

            logger.info(f"[TextClassifyExecutor] Successfully loaded {missing_cols} from MongoDB.")

            return df



    for tbl, cols in table_to_cols.items():

        col_list_str = ", ".join(f'"{c}"' for c in cols)

        id_list_str = ", ".join(f"'{x}'" if isinstance(x, str) else str(x) for x in ids)

        fetch_sql = f'SELECT "{id_col}", {col_list_str} FROM "{tbl}" WHERE "{id_col}" IN ({id_list_str})'

        logger.info(f"[TextClassifyExecutor] Auto-fetching missing columns {cols} from table '{tbl}' using: {fetch_sql[:120]}")

        ok, err, fetched_rows = executor.execute_direct(fetch_sql)

        if ok and fetched_rows:

            for col in cols:

                val_map = {r[id_col]: r[col] for r in fetched_rows if id_col in r and col in r}

                df[col] = df[id_col].map(val_map)

        else:

            logger.warning(f"[TextClassifyExecutor] Failed to fetch missing columns {cols}: {err}")



    return df





class TextClassifyExecutor:

    """

    Runs fetch => classify => aggregate => answer for text-encoded attributes.

    """



    def __init__(self, llm: LLMClient):

        self.llm = llm



    def execute(self, question: str, classify_spec: dict, executor) -> str:

        """

        Returns a plain-text answer string or raises RuntimeError on hard failure.



        Optimization path (tried before LLM classify):

          1. SQL-native: if fetch_sql already contains a category/label column,

             run a GROUP BY directly -- 0 LLM calls, instant answer.

          2. Pre-filter: fetch_sql should include a WHERE clause so we only

             classify rows relevant to the question, not the whole table.

          3. Large batches: BATCH_SIZE=50 means far fewer LLM round-trips.

        """

        fetch_sql = classify_spec.get("fetch_sql", "").strip()

        group_col = classify_spec.get("group_column", "")

        text_cols = classify_spec.get("text_columns", [])

        categories = classify_spec.get("categories", [])

        target = classify_spec.get("target_category", "")

        instruction = classify_spec.get("classification_instruction", "")

        native_category_col = classify_spec.get("native_category_column", "")



        if not fetch_sql or not categories:

            raise RuntimeError("classify_spec is missing fetch_sql or categories")



        # ------------------------------------------------------------------

        # Optimisation 1: SQL-native classification (0 LLM calls)

        # If the DB already has a category column, skip all LLM work and

        # answer directly via a GROUP BY SQL query.

        # ------------------------------------------------------------------

        if native_category_col:

            native_answer = self._try_native_sql(

                fetch_sql,

                native_category_col,

                group_col,

                target,

                categories,

                question,

                executor,

            )

            if native_answer is not None:

                logger.info(

                    f"[TextClassifyExecutor] SQL-native path succeeded "

                    f"(0 LLM classify calls). Answer: {native_answer}"

                )

                return native_answer

            logger.info(

                "[TextClassifyExecutor] SQL-native path failed -- "

                "falling back to LLM classify."

            )



        # Determine sorting before fetching to optimize DB retrieval for max/min text property queries

        q_lower = question.lower()

        sql_sort = ""

        target_text_col = None

        if text_cols:

            best_col = text_cols[0]

            best_score = -1

            comparison_words = [

                "longest",

                "greatest",

                "maximum",

                "max",

                "character",

                "characters",

                "length",

                "shortest",

                "least",

                "minimum",

                "min",

            ]



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

                    if (

                        f"longest {tc_lower}" in q_lower

                        or f"shortest {tc_lower}" in q_lower

                    ):

                        score += 1000

                    if (

                        f"{tc_lower} has the" in q_lower

                        or f"{tc_lower} is the" in q_lower

                    ):

                        score += 1000



                    if score > best_score:

                        best_score = score

                        best_col = tc

            target_text_col = best_col



        if target_text_col:

            if any(

                w in q_lower

                for w in [

                    "longest",

                    "greatest",

                    "maximum",

                    "max",

                    "character",

                    "length",

                ]

            ):

                sql_sort = f" ORDER BY LENGTH({target_text_col}) DESC"

            elif any(w in q_lower for w in ["shortest", "least", "minimum", "min"]):

                sql_sort = f" ORDER BY LENGTH({target_text_col}) ASC"



        # Inject order by into fetch_sql if not already present

        has_existing_order = "order by" in fetch_sql.lower()

        rows = None

        ok = False

        err = ""

        

        if sql_sort and not has_existing_order:

            sorted_fetch_sql = f"{fetch_sql.rstrip(';')}{sql_sort}"

            logger.info(f"[TextClassifyExecutor] Attempting sorted fetch: {sorted_fetch_sql[:120]}...")

            ok, err, rows = executor.execute_direct(sorted_fetch_sql)

            if ok and rows:

                fetch_sql = sorted_fetch_sql

                logger.info("[TextClassifyExecutor] Sorted fetch succeeded.")

            else:

                logger.warning(f"[TextClassifyExecutor] Sorted fetch failed: {err}. Falling back to unsorted fetch.")



        if not ok or not rows:

            logger.info(f"[TextClassifyExecutor] Fetching rows (unsorted): {fetch_sql[:120]}...")

            ok, err, rows = executor.execute_direct(fetch_sql)



        if not ok or not rows:

            raise RuntimeError(f"fetch_sql failed: {err}")

        df = pd.DataFrame(rows)

        if df is None or df.empty:

            return "No data found for the query. Cannot determine the answer."



        # Auto-fetch any missing text_columns from database

        missing_cols = [c for c in text_cols if c not in df.columns]

        if missing_cols:

            id_col = classify_spec.get("id_column", "") or group_col

            if not id_col:

                for col_name in df.columns:

                    if "id" in str(col_name).lower():

                        id_col = col_name

                        break

            if not id_col and not df.empty:

                id_col = df.columns[0]



            if id_col and id_col in df.columns:

                logger.info(f"[TextClassifyExecutor] Found missing columns {missing_cols}. Attempting auto-fetch using ID column '{id_col}'...")

                df = _fetch_missing_columns(df, id_col, missing_cols, executor)



        total_rows = len(df)

        sampled = False



        if sql_sort or has_existing_order:

            # If sorted, take the top rows to preserve the sorting hierarchy

            # Cap at 300 rows (instead of 2000) for sorted queries to save costs/tokens and keep batching fast.

            sorted_limit = 300

            if total_rows > sorted_limit:

                logger.info(

                    f"[TextClassifyExecutor] {total_rows} rows "" keeping top {sorted_limit} rows to preserve order"

                )

                df = df.head(sorted_limit).reset_index(drop=True)

                sampled = True

        else:

            if total_rows > MAX_ROWS_SAMPLE:

                # Too large even for sampling -- use a stratified sample grouped by group_col

                logger.info(

                    f"[TextClassifyExecutor] {total_rows} rows "" using stratified sample "

                    f"({MAX_ROWS_SAMPLE} rows)"

                )

                if group_col and group_col in df.columns:

                    n_groups = max(df[group_col].nunique(), 1)

                    n_per_group = MAX_ROWS_SAMPLE // n_groups

                    if n_per_group > 0:

                        sampled_dfs = []

                        for _name, group in df.groupby(group_col):

                            sampled_dfs.append(

                                group.sample(

                                    min(len(group), n_per_group), random_state=42

                                )

                            )

                        df = pd.concat(sampled_dfs, ignore_index=True)

                    else:

                        # High cardinality grouping column: fall back to simple random sample to keep target size

                        df = df.sample(MAX_ROWS_SAMPLE, random_state=42).reset_index(

                            drop=True

                        )

                else:

                    df = df.sample(MAX_ROWS_SAMPLE, random_state=42).reset_index(

                        drop=True

                    )

                sampled = True

            elif total_rows > MAX_ROWS_EXACT:

                logger.info(

                    f"[TextClassifyExecutor] {total_rows} rows "" sampling {MAX_ROWS_SAMPLE}"

                )

                df = df.sample(

                    min(total_rows, MAX_ROWS_SAMPLE), random_state=42

                ).reset_index(drop=True)

                sampled = True



        # ------------------------------------------------------------------

        # Step 1.5: Dynamic Context Injection (Schema RAG)

        # ------------------------------------------------------------------

        db_context = "No specific dataset context available."

        try:

            from config.config import DATABASES_DIR

            db_dir_duckdb = DATABASES_DIR / "duckdb" / executor.db_name.lower()

            desc_path = db_dir_duckdb / "db_description.txt"

            if desc_path.exists():

                with open(desc_path, "r", encoding="utf-8") as f:

                    db_context = f.read()

            else:

                db_dir_sqlite = DATABASES_DIR / "sqlite" / executor.db_name.lower()

                desc_path = db_dir_sqlite / "db_description.txt"

                if desc_path.exists():

                    with open(desc_path, "r", encoding="utf-8") as f:

                        db_context = f.read()

            

            # Additional generic sample rows heuristic

            if len(db_context) < 50:

                db_context += "\n(Note: The database contains " + str(total_rows) + " rows.)"

                

            logger.info(f"[TextClassifyExecutor] Loaded dataset context (len: {len(db_context)})")

        except Exception as e:

            logger.debug(f"[TextClassifyExecutor] Could not load dataset context: {e}")



        logger.info(

            f"[TextClassifyExecutor] Classifying {len(df)} rows "

            f"using {len(text_cols)} text column(s) into {len(categories)} categories"

        )



        # ------------------------------------------------------------------

        # Step 2: Batch-classify

        # ------------------------------------------------------------------

        df["_category"] = None



        # Calculate dynamic batch size based on average text length in requested columns

        avg_len = 0

        if not df.empty and text_cols:

            total_len = 0

            count = 0

            for col in text_cols:

                if col in df.columns:

                    total_len += df[col].fillna("").astype(str).str.len().sum()

                    count += len(df)

            if count > 0:

                avg_len = total_len / count



        # Dynamic batch sizing logic, using judgement on the fly (minimum 50, maximum 70)

        if avg_len < 150:

            batch_size = 70

        elif avg_len < 300:

            batch_size = 60

        else:

            batch_size = 50



        logger.info(

            f"[TextClassifyExecutor] Calculated dynamic batch size: {batch_size} (average length: {avg_len:.1f} chars)"

        )



        n_batches = math.ceil(len(df) / batch_size)



        for batch_idx in range(n_batches):

            try:

                from core.utils.cache import DAB_CANCEL_FLAG, SPIDER_CANCEL_FLAG

                if DAB_CANCEL_FLAG or SPIDER_CANCEL_FLAG:

                    raise KeyboardInterrupt("Run stopped by user")

            except Exception:

                pass



            batch = df.iloc[batch_idx * batch_size : (batch_idx + 1) * batch_size]

            items = []

            for _, row in batch.iterrows():

                text_parts = {

                    c: _clean_html_text(row[c])[:1000]

                    for c in text_cols

                    if c in row.index

                }

                items.append({"id": int(row.name), "text": text_parts})  # type: ignore



            try:

                raw = self.llm.generate(

                    system_prompt=_CLASSIFY_SYSTEM,

                    user_prompt=_CLASSIFY_USER_TMPL.format(

                        db_context=db_context,

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

                    f"[TextClassifyExecutor] Batch {batch_idx + 1}/{n_batches} done"

                )

            except Exception as e:

                logger.warning(

                    f"[TextClassifyExecutor] Batch {batch_idx + 1} failed: {e}"

                )

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

                f"After classifying {'a sample of ' if sampled else ""}{total_rows} rows, "

                f"no rows matched the '{target}' category. Cannot determine the answer."

            )



        # Enrich subset with text column lengths to support queries about longest/shortest text

        for col in text_cols:

            if col in subset.columns:

                with contextlib.suppress(Exception):

                    subset[f"{col}_length"] = subset[col].astype(str).str.len()



        # Determine if the question is asking for a maximum/longest/greatest or minimum/shortest text property

        sort_col = None

        ascending = False

        q_lower = question.lower()

        if target_text_col:

            length_col = f"{target_text_col}_length"

            if length_col in subset.columns:

                if any(

                    w in q_lower

                    for w in [

                        "longest",

                        "greatest",

                        "maximum",

                        "max",

                        "character",

                        "length",

                    ]

                ):

                    sort_col = length_col

                    ascending = False

                elif any(w in q_lower for w in ["shortest", "least", "minimum", "min"]):

                    sort_col = length_col

                    ascending = True



        # Fallback to any length column if target_text_col matching failed

        if not sort_col and any(

            w in q_lower

            for w in [

                "longest",

                "greatest",

                "maximum",

                "max",

                "character",

                "length",

                "shortest",

                "least",

                "minimum",

                "min",

            ]

        ):

            length_cols = [c for c in subset.columns if str(c).endswith("_length")]

            if length_cols:

                sort_col = length_cols[0]

                if any(

                    w in q_lower

                    for w in [

                        "longest",

                        "greatest",

                        "maximum",

                        "max",

                        "character",

                        "length",

                    ]

                ):

                    ascending = False

                elif any(

                    w in q_lower for w in ["shortest", "least", "minimum", "min"]

                ):

                    ascending = True



        agg = pd.DataFrame()

        if sort_col:

            subset = subset.sort_values(sort_col, ascending=ascending)

            # Project relevant columns: group_col, text_cols, and length cols

            cols_to_show = [

                c

                for c in [group_col, *text_cols, sort_col]

                if c and c in subset.columns

            ]

            cols_to_show = list(dict.fromkeys(cols_to_show))

            agg = subset[cols_to_show].head(30)

            agg_text = agg.to_string(index=False)

        elif group_col and group_col in subset.columns:

            agg = (

                subset.groupby(group_col)

                .size()

                .reset_index(name="count")

                .sort_values("count", ascending=False)

            )

            agg_text = agg.to_string(index=False)

        else:

            if target:

                agg = pd.DataFrame(

                    {

                        "category": [target],

                        "matching_count": [len(subset)],

                        "total_classified": [len(classified)],

                    }

                )

            else:

                if "_category" in subset.columns:

                    agg = (

                        subset.groupby("_category")

                        .size()

                        .reset_index(name="count")

                        .sort_values("count", ascending=False)

                    )

                else:

                    agg = pd.DataFrame({"count": [len(subset)]})

            agg_text = agg.to_string(index=False)

        logger.info(f"[TextClassifyExecutor] Aggregation:\n{agg_text}")



        # ------------------------------------------------------------------

        # Step 4: LLM formats the final answer

        # ------------------------------------------------------------------

        sample_note = (

            f"\n(Note: based on a stratified sample of {len(df)}/{total_rows} rows)"

            if sampled

            else ""

        )

        try:

            answer_raw = self.llm.generate(

                system_prompt=_ANSWER_SYSTEM,

                user_prompt=_ANSWER_USER_TMPL.format(

                    question=question,

                    agg_table=agg_text + sample_note,

                ),

            )

            answer_raw = re.sub(

                r"<think>.*?</think>", "", answer_raw, flags=re.S

            ).strip()

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



    def _try_native_sql(

        self,

        fetch_sql: str,

        native_col: str,

        group_col: str,

        target: str,

        categories: list,

        question: str,

        executor,

    ):

        """

        Attempt a pure-SQL answer using an existing category column.

        Returns the answer string on success, None on failure.



        Strategy:

          - Wrap fetch_sql as a CTE, GROUP BY the native category column.

          - If target is set, filter to that category and return count/ratio.

          - If no target, return the category with the highest count.

        """

        try:

            q_lower = question.lower()

            nc = f'"{native_col}"'

            cte = f"WITH _base AS ({fetch_sql.rstrip(';')})"



            if target:

                # Count rows matching target vs total (for ratio/fraction questions)

                agg_sql = (

                    f"{cte} "

                    f"SELECT "

                    f"  SUM(CASE WHEN LOWER({nc}) = LOWER('{target}') THEN 1 ELSE 0 END) AS matched, "

                    f"  COUNT(*) AS total "

                    f"FROM _base"

                )

                ok, err, rows = executor.execute_direct(agg_sql)

                if not ok or not rows:

                    return None

                matched = int(rows[0].get("matched") or rows[0].get("MATCHED") or 0)

                total = int(rows[0].get("total") or rows[0].get("TOTAL") or 0)

                if total == 0:

                    return None

                # Decide output format from question keywords

                if any(

                    w in q_lower for w in ["fraction", "ratio", "proportion", "percent"]

                ):

                    return f"{matched}/{total}"

                elif any(w in q_lower for w in ["how many", "count", "number"]):

                    return str(matched)

                else:

                    return f"{matched}/{total}"

            else:

                # No target -- return category distribution or top category

                agg_sql = (

                    f"{cte} "

                    f"SELECT {nc} AS category, COUNT(*) AS cnt "

                    f"FROM _base "

                    f"WHERE {nc} IS NOT NULL "

                    f"GROUP BY {nc} "

                    f"ORDER BY cnt DESC"

                )

                ok, _err, rows = executor.execute_direct(agg_sql)

                if not ok or not rows:

                    return None

                if any(

                    w in q_lower

                    for w in ["most", "highest", "top", "popular", "common", "dominant"]

                ):

                    top = rows[0]

                    cat = top.get("category") or top.get("CATEGORY") or ""

                    cnt = top.get("cnt") or top.get("CNT") or ""

                    return f"{cat}, {cnt}" if cnt else str(cat)

                # Format as distribution table for the answer LLM

                agg_text = "\n".join(

                    f"{r.get('category', r.get('CATEGORY', ""))}: "

                    f"{r.get('cnt', r.get('CNT', ""))}"

                    for r in rows

                )

                try:

                    answer_raw = self.llm.generate(

                        system_prompt=_ANSWER_SYSTEM,

                        user_prompt=_ANSWER_USER_TMPL.format(

                            question=question, agg_table=agg_text

                        ),

                    )

                    return re.sub(

                        r"<think>.*?</think>", "", answer_raw, flags=re.S

                    ).strip()

                except Exception:

                    return rows[0].get("category") or rows[0].get("CATEGORY")

        except Exception as e:

            logger.debug(f"[TextClassifyExecutor] native SQL path error: {e}")

            return None



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

