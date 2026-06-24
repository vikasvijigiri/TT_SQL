"""

strategy_router.py

------------------

Given the FeasibilityAgent gap report and the SchemaExplorer findings,

an LLM reasons about HOW to answer the question and returns a strategy.



Strategies

----------

direct_sql

    The schema fully supports the question.  Continue with the standard

    SQL generation pipeline, optionally injecting exploration context.



enriched_sql

    The schema partially supports the question, but exploration revealed

    enough (e.g. a naming convention, a value distribution) to let the

    SQL generator write a better query with the extra context injected.



text_classify_aggregate

    A key filter/group dimension is encoded in free text (title,

    description) with no column.  The pipeline must:

      1. Fetch candidate rows (SQL)

      2. LLM-classify each row's text into the target category

      3. Aggregate the classified results in Python

    StrategyRouter returns the SQL to fetch rows + the classification

    spec so TextClassifyExecutor can run it.



cannot_answer

    The data genuinely cannot answer the question (column missing,

    dataset scope mismatch, etc.).  Return a graceful explanation.

"""



from __future__ import annotations



import json

import re

from typing import Optional



from agent.services.llm import LLMClient

from agent.services.logger import logger



# ---------------------------------------------------------------------------

# Prompts

# ---------------------------------------------------------------------------



_SYSTEM = """## Role

Execution strategy planner. Choose HOW to answer a question given a schema and live data exploration.



## Strategies



| Strategy | When to use |

|---|---|

| `direct_sql` | Schema fully supports the question; no extra guidance needed |

| `enriched_sql` | Schema mostly works but exploration revealed patterns, conventions, or data quirks the SQL generator must know -- OR a value must be extracted from free text via regex/CASE/LIKE |

| `text_classify_aggregate` | A key dimension requires genuine LLM semantic reasoning (sentiment, implicit topic, cultural inference) -- NOT simple keyword presence |

| `cannot_answer` | Data genuinely cannot answer the question |



## KEYWORD/PATTERN DETECTION vs SEMANTIC CLASSIFICATION -- critical distinction

`text_classify_aggregate` requires genuine LLM semantic understanding. Use it ONLY when a concept

CANNOT be detected by any text-matching rule (e.g. sentiment polarity, implicit industry classification).



Use `enriched_sql` instead whenever the concept is detectable by pattern matching:

- "contains word X" (copyright, license, TODO, error) => `enriched_sql` + `LIKE '%word%'`

- "file path ends with README.md" => `enriched_sql` + `LIKE '%README.md'`

- "starts with 'Copyright'" => `enriched_sql` + regex or LIKE pattern

- "does not use Python" on a language description column => `enriched_sql` + anti-join with `NOT IN`



In short: if a SQL LIKE/ILIKE/regex filter can reliably detect the concept, use `enriched_sql`.



## CRITICAL RULES

1. NO `cannot_answer` IF extraction is possible: If keys/values can be extracted from JSON attributes, metadata, or structured strings via regex/split/JSON_EXTRACT, use `enriched_sql`.

2. ENTITY vs EVENT: If the question asks for "number of X" and X is a base entity (e.g. "users"), perform `COUNT(DISTINCT id)`. If X is an event (e.g. "logins"), perform `COUNT(*)`. If unclear, default to the most logical granular count.

3. STRUCTURED TEXT IS SQL: If structured text (logs, JSON, CSV-in-col) contains the answer, `enriched_sql` is mandatory. Do NOT return `cannot_answer` for data that is programmatically parseable.



## MULTI-DATABASE SQL - mandatory when schema spans multiple databases

When the schema includes tables from both DuckDB and an attached SQLite database, ALL SQL you

generate (fetch_sql, enriched_context SQL examples) MUST use the attached-database prefix for

SQLite tables. The attached prefix is shown in the schema hints or error messages.

Example: if hints say "repo_metadata_db.languages" - use that exact prefix in all SQL:

  `repo_metadata_db.languages`, `repo_metadata_db.repos`, `repo_metadata_db.licenses`

NEVER reference SQLite tables without their attached database prefix in DuckDB SQL.



## MONGODB TEXT COLLECTIONS - cross-db execution support

If the exploration shows that the required text data lives in a MongoDB collection, you MUST NOT return `cannot_answer`. The execution engine has a built-in cross-database orchestrator that seamlessly joins MongoDB with SQL using Python under the hood.

- Strategy MUST be `text_classify_aggregate` (if semantic logic is needed) or `enriched_sql` (if pattern matching).

- `fetch_sql` should simply fetch the IDs/metadata from the SQL database. The orchestrator will automatically pull the corresponding text from MongoDB during execution.



## NARROW JOIN PROTOCOL - mandatory when exploration shows "*** NARROW JOIN"

If SchemaExplorer reports `*** NARROW JOIN` between table A and table B on column C:

- The join `A.C = B.C` is the **only correct data anchor** - it defines the real queryable universe

- Scanning A alone or B alone returns WRONG results

- Your `enriched_context` MUST include:

  ```

  ANCHOR: FROM [A] JOIN [B] ON [A].[C] = [B].[C]

  Use [B].[path_col] for file-path filters -- NOT [A]'s sample columns

  Do NOT scan [A] or [B] alone under any circumstances

  ```



## text_classify_aggregate rules

- Use ONLY when ALL four conditions hold:

  (a) No dedicated category/label column exists in the schema

  (b) Genuine LLM semantic understanding is required (not just pattern matching)

  (c) fetch_sql is complete and runnable

  (d) The exact category list is known from the question or exploration

- NEVER for keyword/substring presence -- use `enriched_sql` instead

- NEVER for numeric extraction -- use `enriched_sql` instead

- NEVER when concept is stored in a JSON/serialized-text column -- use `enriched_sql` instead

- Missing fetch_sql or categories => downgrade to `enriched_sql`



## native_category_column -- critical cost optimisation

When choosing `text_classify_aggregate`, ALWAYS check whether the schema

already has a structured column that directly encodes the category (e.g. a

low-cardinality column whose sample values match the question's categories).

If such a column exists, set `native_category_column` to its exact name.

The executor will then answer with a single SQL GROUP BY -- zero LLM classify

calls. Do NOT hardcode any column name: inspect the schema sample values

actually shown in the exploration findings to decide.



## fetch_sql pre-filtering -- mandatory

The fetch_sql inside classify_spec MUST include a WHERE clause that narrows

rows to those relevant to the question (e.g. filtering by author, date range,

or entity). Never fetch the entire table when a subset is sufficient.

If no pre-filter is possible, include a LIMIT to cap rows at a reasonable

bound for the question (e.g. LIMIT 2000).



## cannot_answer rules -- use ONLY as a LAST resort

`cannot_answer` is valid ONLY when ALL of the following are true:

1. No column (direct, JSON, or serialized-text) holds any form of the required information

2. No LIKE/regex/json_extract pattern could detect the concept

3. Semantic classification would also fail due to missing data

If ANY column could answer via pattern matching, use `enriched_sql`. Prefer a best-effort SQL over giving up.



## Output -- JSON only

```json

{

  "strategy": "direct_sql|enriched_sql|text_classify_aggregate|cannot_answer",

  "reasoning": "<2-3 sentences: WHY this strategy based on exploration>",

  "enriched_context": "<direct_sql/enriched_sql: SQL generation guidance; include NARROW JOIN anchor if detected>",

  "classify_spec": {

    "fetch_sql": "<REQUIRED: complete runnable SQL with WHERE pre-filter>",

    "id_column": "<unique row identifier>",

    "group_column": "<group-by column>",

    "text_columns": ["<col>"],

    "categories": ["<exact label>"],

    "target_category": "<target or empty string>",

    "classification_instruction": "<one sentence>",

    "native_category_column": "<exact column name if DB already encodes categories, else empty string>"

  },

  "cannot_answer_reason": "<cannot_answer only>"

}

```"""



_USER_TMPL = """**Question:** {question}



**Schema:**

{schema_text}



**Feasibility gaps:**

{gap_report}



**Exploration findings:**

{exploration}



Choose the best strategy. If exploration shows NARROW JOIN, your enriched_context must include the join anchor."""





class StrategyRouter:

    """One LLM call that turns gap + exploration into an actionable execution plan."""



    def __init__(self, llm: LLMClient):

        self.llm = llm



    def route(

        self,

        question: str,

        schema_text: str,

        feasibility: dict,

        exploration: str,

    ) -> dict:

        """

        Returns a strategy dict.  Never raises - falls back to direct_sql

        if the LLM call or parse fails.

        """

        logger.set_agent("STRATEGY_ROUTER")

        logger.info("> AGENT EXECUTION: STRATEGY_ROUTER")

        try:

            gap_report = json.dumps(

                {

                    "has_gaps": feasibility.get("has_gaps", False),

                    "gap_summary": feasibility.get("gap_summary", ""),

                    "gaps": [

                        {"term": c["term"], "reason": c.get("gap_reason", "")}

                        for c in feasibility.get("concepts", [])

                        if c.get("gap")

                    ],

                },

                indent=2,

            )



            prompt = _USER_TMPL.format(

                question=question,

                schema_text=schema_text,

                gap_report=gap_report,

                exploration=exploration or "(no exploration performed)",

            )



            try:

                raw = self.llm.generate(

                    system_prompt=_SYSTEM,

                    user_prompt=prompt,

                )

                raw = self._strip_think(raw)

                result = self._parse(raw)

                if result:

                    logger.info(f"[StrategyRouter] strategy={result['strategy']}")

                    logger.info(f"[StrategyRouter] reasoning: {result['reasoning'][:120]}")

                    # Safety net: if cannot_answer was chosen but exploration found data,

                    # try to rescue it with a smarter fallback.

                    if (

                        result["strategy"] == "cannot_answer"

                        and exploration

                        and len(exploration.strip()) > 100

                    ):

                        # Determine whether the data is pattern-extractable (JSON/structured) or

                        # free-text narrative (requires semantic classification).

                        expl_lower = exploration.lower()

                        has_json_signal = any(

                            sig in exploration

                            for sig in [

                                "Structured Attribute Keys",  # profiler found JSON keys

                                '"$.',  # json_extract pattern

                                "LIKE '%",  # LIKE pattern suggestion

                                "json_extract",  # explicit json suggestion

                                '{"',  # JSON object in sample

                                "{'",  # Python dict in sample

                            ]

                        )

                        has_narrative_text = any(

                            sig in expl_lower

                            for sig in [

                                "description",

                                "located at",

                                "this establishment",

                                "offers a range",

                                "provides a",

                                "premier destination",

                                "services including",

                            ]

                        )



                        base = result.get("enriched_context") or result.get(

                            "cannot_answer_reason", ""

                        )



                        if has_json_signal:

                            # Pattern-extractable: downgrade to enriched_sql

                            logger.warning(

                                "[StrategyRouter] cannot_answer returned but JSON/structured data detected - "

                                "downgrading to enriched_sql for pattern-based extraction."

                            )

                            result["strategy"] = "enriched_sql"

                            result["enriched_context"] = (

                                (base + "\n\n" if base else "")

                                + "GUIDANCE: The required value may be embedded in a structured JSON or serialized-text column. "

                                "Use the EXPLORATION FINDINGS to identify the exact column and extraction pattern. "

                                "Use json_extract_string(), regexp_extract(), LIKE, or CASE expressions. "

                                "You MUST write a SQL query - do NOT refuse or return empty SQL."

                            )

                        elif has_narrative_text:

                            # Free-text narrative: route to text_classify_aggregate for LLM classification

                            logger.warning(

                                "[StrategyRouter] cannot_answer returned but narrative text column detected - "

                                "upgrading to text_classify_aggregate for LLM-based semantic extraction."

                            )

                            result["strategy"] = "text_classify_aggregate"

                            # Provide a minimal classify_spec scaffold if none exists.

                            # Do NOT hardcode column names or category labels - leave them

                            # empty so the SQL generator fills them from the actual schema.

                            if not result.get("classify_spec"):

                                result["classify_spec"] = {

                                    "fetch_sql": "",

                                    "id_column": "",

                                    "text_columns": [],  # filled by SQL generator from schema

                                    "categories": [],  # filled by SQL generator from question

                                    "target_category": "",

                                    "native_category_column": "",

                                    "classification_instruction": "",

                                }

                        else:

                            # Unknown data type: best-effort enriched_sql

                            logger.warning(

                                "[StrategyRouter] cannot_answer returned with exploration data - "

                                "defaulting to enriched_sql as best-effort fallback."

                            )

                            result["strategy"] = "enriched_sql"

                            result["enriched_context"] = (

                                (base + "\n\n" if base else "")

                                + "GUIDANCE: Attempt to extract the required value using available columns. "

                                "You MUST write a SQL query - do NOT refuse or return empty SQL."

                            )

                    return result

            except Exception as e:

                logger.debug(f"[StrategyRouter] failed (non-fatal): {e}")



            return self._default()

        finally:

            logger.reset_agent()



    # ------------------------------------------------------------------

    # Helpers

    # ------------------------------------------------------------------



    @staticmethod

    def _strip_think(text: str) -> str:

        return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()



    @staticmethod

    def _parse(raw: str) -> Optional[dict]:

        start = raw.find("{")

        end = raw.rfind("}") + 1

        if start == -1 or end == 0:

            return None

        try:

            obj = json.loads(raw[start:end])

            obj.setdefault("strategy", "direct_sql")

            obj.setdefault("reasoning", "")

            obj.setdefault("enriched_context", "")

            obj.setdefault("classify_spec", {})

            obj.setdefault("cannot_answer_reason", "")

            if obj["strategy"] not in (

                "direct_sql",

                "enriched_sql",

                "text_classify_aggregate",

                "cannot_answer",

            ):

                obj["strategy"] = "direct_sql"



            # Normalise classify_spec fields -- set safe defaults, no hardcoding

            spec = obj.get("classify_spec", {})

            spec.setdefault("fetch_sql", "")

            spec.setdefault("id_column", "")

            spec.setdefault("group_column", "")

            spec.setdefault("text_columns", [])

            spec.setdefault("categories", [])

            spec.setdefault("target_category", "")

            spec.setdefault("classification_instruction", "")

            # native_category_column: populated by LLM from schema inspection, never hardcoded

            spec.setdefault("native_category_column", "")

            obj["classify_spec"] = spec



            # Validate text_classify_aggregate -- if spec is incomplete, downgrade to enriched_sql

            if obj["strategy"] == "text_classify_aggregate":

                missing_fetch = not spec.get("fetch_sql", "").strip()

                missing_cats = not spec.get("categories")

                if missing_fetch or missing_cats:

                    obj["strategy"] = "enriched_sql"

                    base = obj.get("enriched_context") or obj.get("reasoning", "")

                    guidance = (

                        "\nGUIDANCE: The required value may be embedded in a free-text column. "

                        "Use the EXPLORATION FINDINGS below to identify the exact column and pattern. "

                        "Use regexp_extract(), REGEXP_SUBSTR(), LIKE, or CASE expressions to extract it. "

                        "You MUST write a SQL query -- do NOT refuse or return empty SQL."

                    )

                    obj["enriched_context"] = (base + guidance).strip()

                    logger.debug(

                        "[StrategyRouter] text_classify_aggregate classify_spec incomplete "

                        f"(missing: {'fetch_sql ' if missing_fetch else ""}{'categories' if missing_cats else ""}) "

                        "-- downgraded to enriched_sql"

                    )

            return obj

        except Exception:

            return None



    @staticmethod

    def _default() -> dict:

        return {

            "strategy": "direct_sql",

            "reasoning": "Strategy routing failed; falling back to direct SQL generation.",

            "enriched_context": "",

            "classify_spec": {},

            "cannot_answer_reason": "",

        }

