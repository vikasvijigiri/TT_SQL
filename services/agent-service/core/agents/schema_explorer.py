"""

schema_explorer.py

------------------

When the FeasibilityAgent detects a gap (a question concept with no schema column),

SchemaExplorer runs lightweight, zero-LLM introspection to understand the data:



  1. SELECT DISTINCT on every column of every relevant table (up to 50 values each)

  2. Cross-table join probes -- discover which table pairs share columns and whether

     the join is narrow (much smaller than either table alone).  Narrow joins define

     the true queryable universe and must be used as the SQL anchor.

  3. SELECT sample rows (10"20) from relevant tables

  4. Read any hint / description files provided by the caller

  5. Summarise raw findings as plain text for StrategyRouter



All of this is deterministic SQL + file I/O -- no LLM call, no hardcoding.

The analyst pattern: "before deciding how to query, look at the data."

"""



from __future__ import annotations



from pathlib import Path

from typing import Optional



from core.utils.logger import logger





class SchemaExplorer:

    """

    Runs introspection queries against the live database and reads auxiliary

    description files. Returns a human-readable findings string.

    """



    MAX_DISTINCT_VALUES = 50

    MAX_SAMPLE_ROWS = 20

    MAX_TEXT_SAMPLE_CHARS = 120  # truncate long text fields in display

    MAX_JOIN_PROBES = 30  # cap total join probes to avoid excessive queries

    NARROW_JOIN_THRESHOLD = 0.1  # join < 10 % of smaller table = narrow join



    def explore(

        self,

        gap_concepts: list[str],

        schema_text: str,

        executor,  # DatabaseExecutor instance

        hint_files: Optional[list[str]] = None,

        description_text: Optional[str] = None,

    ) -> str:

        """

        Returns a multi-section exploration report as plain text.

        Never raises -- failures are caught and noted in the report.

        """

        sections: list[str] = []



        # 1. Read hint / description files

        hint_text = self._read_hints(hint_files, description_text)

        if hint_text:

            sections.append(f"=== HINT FILES ===\n{hint_text}")



        # 2. Parse table names from schema_text

        tables = self._extract_table_names(schema_text)

        if not tables:

            sections.append("(Could not extract table names from schema)")

            return "\n\n".join(sections)



        # 3. SELECT DISTINCT on all columns (understand value space)

        distinct_section = self._probe_distinct_values(tables, executor)

        if distinct_section:

            sections.append(f"=== COLUMN VALUE SAMPLES ===\n{distinct_section}")



        # 4. Cross-table join probes -- discover shared keys and narrow joins.

        #    A narrow join (join rows << either table size) means the joined view IS

        #    the meaningful data universe; queries must anchor on it, not on either

        #    table alone.  This is discovered dynamically from actual column overlap.

        join_section = self._probe_cross_table_joins(tables, executor)

        if join_section:

            sections.append(f"=== CROSS-TABLE JOIN PROBES ===\n{join_section}")



        # 5. Sample rows (understand text field content)

        sample_section = self._probe_sample_rows(tables, executor)

        if sample_section:

            sections.append(f"=== SAMPLE ROWS ===\n{sample_section}")



        # 6. Summarise gap concepts against what was found

        gap_note = (

            f"=== GAP ANALYSIS ===\n"

            f"The question requires: {', '.join(gap_concepts)}\n"

            f"None of the above map directly to a schema column.\n"

            f"Based on the data above, reason about how to derive this information."

        )

        sections.append(gap_note)



        report = "\n\n".join(sections)

        logger.info(

            f"[SchemaExplorer] Report ready ({len(report)} chars, {len(sections)} sections)"

        )

        return report



    # ------------------------------------------------------------------

    # Hint / description file reader

    # ------------------------------------------------------------------



    def _read_hints(

        self,

        hint_files: Optional[list[str]],

        description_text: Optional[str],

    ) -> str:

        parts: list[str] = []



        if description_text:

            parts.append(description_text.strip()[:2000])



        if hint_files:

            for fpath in hint_files:

                p = Path(fpath)

                if p.exists():

                    try:

                        content = p.read_text(

                            encoding="utf-8", errors="replace"

                        ).strip()

                        parts.append(f"[{p.name}]\n{content[:2000]}")

                    except Exception as e:

                        parts.append(f"[{p.name}] (read error: {e})")



        return "\n\n".join(parts)



    # ------------------------------------------------------------------

    # Live DB probing

    # ------------------------------------------------------------------



    @staticmethod

    def _tref(table: str, quote: str) -> str:

        """Return the correct SQL table reference for FROM/JOIN clauses.



        Qualified names (db.table) must NOT be wrapped in a single outer quote

        pair -- doing so confuses most SQL engines.  Plain names use the normal

        identifier quote character.

        """

        if "." in table:

            return table  # e.g. repo_metadata_db.languages -- use as-is

        return f"{quote}{table}{quote}"



    def _probe_distinct_values(self, tables: list[str], executor) -> str:

        lines: list[str] = []

        dialect = getattr(executor, "dialect", "sqlite")

        quote = '"' if dialect in ("sqlite", "postgres", "duckdb") else "`"



        for table in tables:

            if "all_" in table.lower():

                continue

            # Get column names first

            try:

                col_sql = self._columns_query(table, dialect, quote)

                ok, _, col_data = executor.execute_direct(col_sql, timeout=60)

                if not ok or not col_data:

                    continue

                # PRAGMA table_info / our DESCRIBE wrapper return name at index 1

                columns = [

                    list(r.values())[1] if len(r) > 1 else next(iter(r.values()))

                    for r in col_data

                ]

            except Exception as e:

                logger.debug(f"[SchemaExplorer] col probe failed for {table}: {e}")

                continue



            tref = self._tref(table, quote)

            for col in columns[:12]:  # cap at 12 columns per table

                try:

                    q = (

                        f"SELECT DISTINCT {quote}{col}{quote} "

                        f"FROM {tref} "

                        f"WHERE {quote}{col}{quote} IS NOT NULL "

                        f"LIMIT {self.MAX_DISTINCT_VALUES}"

                    )

                    ok2, _, raw_rows = executor.execute_direct(q, timeout=60)

                    if not ok2 or not raw_rows:

                        continue

                    vals = [str(next(iter(r.values())))[:60] for r in raw_rows]

                    lines.append(f"  {table}.{col}: [{', '.join(vals[:20])}]")

                except Exception:

                    continue



        return "\n".join(lines) if lines else "(no distinct value data)"



    def _probe_cross_table_joins(self, tables: list[str], executor) -> str:

        """

        Dynamically discover cross-table relationships by:

          1. Fetching column names for every table.

          2. Finding all pairs that share at least one column name.

          3. Running COUNT(*) for each shared-column JOIN.

          4. Flagging narrow joins where the result is much smaller than either

             table alone -- those joins define the real queryable universe.



        Fully generic: no column names, table names, or schema assumptions are

        hardcoded. Works for any dialect (sqlite, duckdb, postgres).

        """

        dialect = getattr(executor, "dialect", "sqlite")

        quote = '"' if dialect in ("sqlite", "postgres", "duckdb") else "`"



        # --- collect column names and row counts per table ---

        table_cols: dict[str, list[str]] = {}  # table => [original-case col names]

        table_size: dict[str, int] = {}



        for table in tables:

            if "all_" in table.lower():

                continue

            try:

                col_sql = self._columns_query(table, dialect, quote)

                ok, _, col_data = executor.execute_direct(col_sql, timeout=60)

                if not ok or not col_data:

                    continue

                cols = [

                    list(r.values())[1] if len(r) > 1 else next(iter(r.values()))

                    for r in col_data

                ]

                table_cols[table] = cols

            except Exception:

                continue



            try:

                tref = self._tref(table, quote)

                ok2, _, cnt_rows = executor.execute_direct(

                    f"SELECT COUNT(*) FROM {tref}", timeout=60

                )

                if ok2 and cnt_rows:

                    table_size[table] = int(next(iter(cnt_rows[0].values())))

            except Exception:

                pass



        if len(table_cols) < 2:

            return ""



        lines: list[str] = []

        probes_run = 0

        table_list = list(table_cols.keys())



        for i, ta in enumerate(table_list):

            for tb in table_list[i + 1 :]:

                if probes_run >= self.MAX_JOIN_PROBES:

                    lines.append(

                        f"  (join probe cap of {self.MAX_JOIN_PROBES} reached)"

                    )

                    break



                # Case-insensitive column name overlap

                cols_a_lower = {c.lower(): c for c in table_cols[ta]}

                cols_b_lower = {c.lower(): c for c in table_cols[tb]}

                shared_lower = sorted(set(cols_a_lower) & set(cols_b_lower))



                if not shared_lower:

                    continue



                for col_lower in shared_lower:

                    if probes_run >= self.MAX_JOIN_PROBES:

                        break



                    col_a = cols_a_lower[col_lower]  # original case from table A

                    col_b = cols_b_lower[col_lower]  # original case from table B



                    try:

                        join_sql = (

                            f"SELECT COUNT(*) "

                            f"FROM {self._tref(ta, quote)} a "

                            f"JOIN {self._tref(tb, quote)} b "

                            f"ON a.{quote}{col_a}{quote} = b.{quote}{col_b}{quote}"

                        )

                        ok, _, rows = executor.execute_direct(join_sql, timeout=60)

                        if not ok or not rows:

                            continue

                        join_count = int(next(iter(rows[0].values())))

                        probes_run += 1



                        size_a = table_size.get(ta)

                        size_b = table_size.get(tb)



                        size_note = ""

                        if size_a is not None and size_b is not None:

                            size_note = (

                                f" (table sizes: {ta}={size_a:,}, {tb}={size_b:,})"

                            )

                            min_size = min(size_a, size_b)

                            if min_size > 0:

                                ratio = join_count / min_size

                                if ratio < self.NARROW_JOIN_THRESHOLD:

                                    size_note += (

                                        f"\n    *** NARROW JOIN ({ratio:.1%} of smaller table) -- "

                                        f"CRITICAL: this join defines the real data universe. "

                                        f"Queries MUST anchor on "

                                        f"'{ta} JOIN {tb} ON {col_a}={col_b}' "

                                        f"NOT on either table scanned alone. ***"

                                    )

                                elif join_count < min_size:

                                    size_note += f"  (selective join, {ratio:.1%} of smaller table)"



                        lines.append(

                            f"  {ta}.{col_a} = {tb}.{col_b}: "

                            f"{join_count:,} joined rows{size_note}"

                        )



                    except Exception as e:

                        logger.debug(

                            f"[SchemaExplorer] join probe {ta}<->{tb} on {col_lower}: {e}"

                        )

                        continue



        if not lines:

            return "(no shared column names found between tables -- tables appear independent)"



        header = (

            "Each line shows how two tables connect via a shared column and "

            "how many rows the join produces.\n"

            "NARROW JOINs (marked ***) are the correct anchors for multi-table queries -- "

            "scanning either table alone gives the wrong universe.\n"

        )

        return header + "\n".join(lines)



    def _probe_sample_rows(self, tables: list[str], executor) -> str:

        lines: list[str] = []

        dialect = getattr(executor, "dialect", "sqlite")

        quote = '"' if dialect in ("sqlite", "postgres", "duckdb") else "`"



        for table in tables[:4]:  # limit to first 4 tables

            if "all_" in table.lower():

                continue

            try:

                q = f"SELECT * FROM {self._tref(table, quote)} LIMIT {self.MAX_SAMPLE_ROWS}"

                ok2, _, raw_rows = executor.execute_direct(q, timeout=60)

                if not ok2 or not raw_rows:

                    continue

                lines.append(f"  Table: {table}")

                lines.append(f"  Columns: {list(raw_rows[0].keys())}")

                for row in raw_rows[:5]:

                    truncated = {

                        k: str(v)[: self.MAX_TEXT_SAMPLE_CHARS] for k, v in row.items()

                    }

                    lines.append(f"    {truncated}")

            except Exception as e:

                logger.debug(f"[SchemaExplorer] sample failed for {table}: {e}")

                continue



        return "\n".join(lines) if lines else "(no sample row data)"



    # ------------------------------------------------------------------

    # Narrow-join extraction (used by callers to amend linked schema)

    # ------------------------------------------------------------------



    @staticmethod

    def extract_narrow_join_tables(exploration: str) -> list[tuple[str, str, str]]:

        """

        Parse the exploration report and return (table_a, table_b, shared_col)

        for every NARROW JOIN found.  Callers use this to add the missing table

        to the linked schema BEFORE SQL generation so the generator can use the

        correct join anchor.

        """

        import re



        results: list[tuple[str, str, str]] = []

        # Match the join line followed IMMEDIATELY by the *** NARROW JOIN marker.

        # Format:

        #   "  table_a.col_a = table_b.col_b: N joined rows ...\n"

        #   "    *** NARROW JOIN ..."

        # CRITICAL: no intermediate lines allowed between the join line and the marker.

        # Allowing intermediate lines causes the regex to match the WRONG table pair

        # (e.g. commit " files when the marker is actually for contents " files).

        # Handle both plain (table.col) and qualified (db.table.col) references.

        # A plain ref has exactly one dot; a qualified ref has two dots.

        pattern = re.compile(

            r"^\s{2}([\w.]+)\.(\w+)\s*=\s*([\w.]+)\.(\w+):\s*[\d,]+\s*joined rows[^\n]*\n"

            r"[ \t]*\*\*\*\s*NARROW JOIN",

            re.MULTILINE,

        )

        for m in pattern.finditer(exploration):

            table_a, col_a, table_b, _col_b = (

                m.group(1),

                m.group(2),

                m.group(3),

                m.group(4),

            )

            results.append((table_a, table_b, col_a))

        return results



    # ------------------------------------------------------------------

    # Helpers

    # ------------------------------------------------------------------



    @staticmethod

    def _extract_table_names(schema_text: str) -> list[str]:

        """Parse table names from formatted schema text.



        Handles both plain table names and db-qualified names (db.table).

        Qualified names are returned as-is so downstream probes can use the

        correct prefix when querying cross-database schemas (e.g. DuckDB with

        an attached SQLite database).

        """

        import re



        # Prefer qualified names (db.table) first, then plain names

        patterns = [

            r"Table:\s*[`\"]?(\w+\.\w+)[`\"]?",  # qualified: db.table

            r"Table:\s*[`\"]?(\w+)[`\"]?",  # plain: table

            r"^[`\"]?(\w+)[`\"]?\s*\(",  # CREATE-style

            r"CREATE TABLE\s+[`\"]?(\w+)[`\"]?",

        ]

        found = []

        for pat in patterns:

            matches = re.findall(pat, schema_text, re.I | re.M)

            found.extend(matches)

        # Deduplicate; skip SQL keywords; also skip bare db-prefix entries

        # (e.g. "repo_metadata_db") when the qualified form was already found

        seen: set[str] = set()

        qualified_dbs: set[str] = set()

        result = []

        for t in found:

            key = t.lower()

            if key in seen or key in ("create", "table", "if"):

                continue

            seen.add(key)

            result.append(t)

            if "." in t:

                qualified_dbs.add(t.split(".")[0].lower())



        # Remove bare db-prefix entries already covered by a qualified form

        result = [t for t in result if t.lower() not in qualified_dbs]

        return result



    @staticmethod

    def _columns_query(table: str, dialect: str, quote: str) -> str:

        if "." in table and dialect == "duckdb":

            # Qualified name (e.g. repo_metadata_db.languages) -- use DESCRIBE

            # wrapped in a subquery so callers always see (cid, name, ...) shape:

            # we fake the cid column so index [1] still gives the column name.

            return f"SELECT 0 AS cid, column_name AS name FROM (DESCRIBE {table})"

        if dialect in ("sqlite", "duckdb"):

            return f"PRAGMA table_info({quote}{table}{quote})"

        elif dialect == "postgres":

            return (

                f"SELECT column_name FROM information_schema.columns "

                f"WHERE table_name = '{table}' ORDER BY ordinal_position"

            )

        else:

            return f"SHOW COLUMNS FROM {quote}{table}{quote}"

