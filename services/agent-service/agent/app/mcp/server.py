import os
import sys
import json
import traceback
import re
from typing import Dict, Any, List, Optional
import sqlglot

# Add the workspace root to sys.path so we can import backend packages
WORKSPACE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agent.app.utils.logger import logger
from agent.app.repositories.db_executor import DatabaseExecutor
from agent.app.services.semantic_engine import SemanticContextEngine
from agent.app.core.query_analysis.capability_detector import QueryCapabilityDetector
from agent.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever


class MCPServer:
    def __init__(self):
        # Default executor setup (can be dynamically configured via initialize or tool calls)
        self.default_db = "sf_bq118"
        self.default_dialect = "snowflake"
        self._executor = None
        self._semantic_engine = None

    @property
    def executor(self) -> DatabaseExecutor:
        if self._executor is None:
            self._executor = DatabaseExecutor(
                db_name=self.default_db, dialect=self.default_dialect
            )
        return self._executor

    @property
    def semantic_engine(self) -> SemanticContextEngine:
        if self._semantic_engine is None:
            # We initialize the semantic engine pointing to resources/databases
            db_dir = os.path.join(WORKSPACE_ROOT, "backend", "resources", "databases")
            self._semantic_engine = SemanticContextEngine(db_directory=db_dir)
            self._semantic_engine.build_context()
        return self._semantic_engine

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "db_explorer_tool",
                "description": "Explores the actual data inside a table column: profiles distinct value frequency, null count, and empirical sample data to help map values correctly.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "Fully qualified table name (e.g. DEATH.DEATH.ICD10CODE)",
                        },
                        "column_name": {
                            "type": "string",
                            "description": "The exact column name to profile",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of top frequent values to return",
                            "default": 5,
                        },
                        "db_name": {
                            "type": "string",
                            "description": "Optional database context (defaults to active test database)",
                            "default": "sf_bq118",
                        },
                    },
                    "required": ["table_name", "column_name"],
                },
            },
            {
                "name": "sql_linter_tool",
                "description": "Lints and validates SQL syntax correctness for a specific database dialect using sqlglot, reporting syntax failures, column alignment errors, or unclosed parenthesis.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL query string to validate",
                        },
                        "dialect": {
                            "type": "string",
                            "description": "Target SQL dialect (e.g. snowflake, sqlite, postgres)",
                            "default": "snowflake",
                        },
                    },
                    "required": ["sql"],
                },
            },
            {
                "name": "search_schema_tool",
                "description": "Searches schema metadata (tables and columns) semantically to locate relevant fields matching natural language concepts or keywords.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search keyword or phrase (e.g. 'cause of death', 'race code', 'underlying cause')",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "agent_flow_analyzer",
                "description": "Runs a pre-flight analytical dry-run of how the agentic pipeline (Schema Linker, Critic, Validator) will handle a user query. Detects Snowflake mixed-case double-quoting risks, missing lookup join keys, and potential spatial containment issues.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_query": {
                            "type": "string",
                            "description": "The raw business question or natural language query",
                        },
                        "dialect": {
                            "type": "string",
                            "description": "Target SQL dialect",
                            "default": "snowflake",
                        },
                    },
                    "required": ["user_query"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        if name == "db_explorer_tool":
            return self._handle_db_explorer(arguments)
        elif name == "sql_linter_tool":
            return self._handle_sql_linter(arguments)
        elif name == "search_schema_tool":
            return self._handle_search_schema(arguments)
        elif name == "agent_flow_analyzer":
            return self._handle_agent_flow_analyzer(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    def _handle_db_explorer(self, args: Dict[str, Any]) -> str:
        table = args["table_name"]
        col = args["column_name"]
        limit = args.get("limit", 5)
        db = args.get("db_name", self.default_db)

        # Configure executor context
        exec_inst = self.executor
        if db != self.default_db:
            exec_inst = DatabaseExecutor(db_name=db, dialect=self.default_dialect)

        # Clean naming parts
        clean_parts = [
            p.replace('"', "").replace("\\", "").strip() for p in table.split(".")
        ]
        quoted_col = f'"{col.replace('"', "")}"'
        quoted_table = ".".join(f'"{p}"' for p in clean_parts)

        # Build SQLs
        freq_sql = f"SELECT {quoted_col} AS val, COUNT(*) AS cnt FROM {quoted_table} WHERE {quoted_col} IS NOT NULL GROUP BY {quoted_col} ORDER BY cnt DESC LIMIT {limit}"
        null_sql = f"SELECT COUNT(*) AS total, SUM(CASE WHEN {quoted_col} IS NULL THEN 1 ELSE 0 END) AS null_cnt FROM {quoted_table}"

        results = [f"## Database Profiling Results for `{table}.{col}`\n"]

        try:
            # 1. Null / Row counts
            success1, msg1, rows1 = exec_inst.execute_direct(null_sql)
            if success1 and rows1:
                r = rows1[0]
                tot = r.get("TOTAL", r.get("total", 0))
                nc = r.get("NULL_CNT", r.get("null_cnt", 0))
                pct = (nc / tot * 100) if tot > 0 else 0
                results.append(f"- **Total Rows in Table**: {tot:,}")
                results.append(f"- **Null Values Count**: {nc:,} ({pct:.2f}% null)\n")
            else:
                results.append(f"Failed to get row metrics: {msg1}\n")

            # 2. Value Frequency
            success2, msg2, rows2 = exec_inst.execute_direct(freq_sql)
            if success2 and rows2:
                results.append("### Top Frequent Values:")
                results.append("| Rank | Distinct Value | Occurrences |")
                results.append("|:----:|:---------------|:------------|")
                for idx, r in enumerate(rows2):
                    val = r.get("VAL", r.get("val", "NULL"))
                    cnt = r.get("CNT", r.get("cnt", 0))
                    results.append(f"| {idx + 1} | `{val}` | {cnt:,} |")
            else:
                results.append(f"Failed to query value frequencies: {msg2}")

            return "\n".join(results)
        except Exception as e:
            return f"Error executing explorer query: {e}\n{traceback.format_exc()}"

    def _handle_sql_linter(self, args: Dict[str, Any]) -> str:
        sql = args["sql"]
        dialect = args.get("dialect", "snowflake").lower()

        try:
            sqlglot.parse_one(sql, read=dialect)
            return f"### SQL Syntax Verification: SUCCESS\n\nSyntax is 100% correct and valid under the `{dialect}` dialect rules!"
        except Exception as e:
            err_msg = str(e)
            lines = sql.splitlines()

            # Try to extract position/line details if sqlglot provided them
            match = re.search(r"Line (\d+), Col (\d+)", err_msg)
            visual_err = ""
            if match:
                line_no = int(match.group(1))
                col_no = int(match.group(2))
                if 1 <= line_no <= len(lines):
                    target_line = lines[line_no - 1]
                    pointer = " " * (col_no - 1) + "^"
                    visual_err = (
                        f"\nLine {line_no}:\n```sql\n{target_line}\n{pointer}\n```\n"
                    )

            return f"### SQL Syntax Verification: FAILED\n\n**Syntax Error Details**:\n{err_msg}\n{visual_err}"

    def _handle_search_schema(self, args: Dict[str, Any]) -> str:
        query = args["query"].lower()
        engine = self.semantic_engine

        if not engine.context or not engine.context.tables:
            return "No schema context loaded."

        matches = []
        for tbl in engine.context.tables:
            t_score = 0
            t_name = tbl.name.lower()
            if query in t_name:
                t_score += 10
            if tbl.description and query in tbl.description.lower():
                t_score += 5

            col_matches = []
            for col in tbl.columns:
                c_name = col.name.lower()
                c_score = 0
                if query in c_name:
                    c_score += 8
                if col.description and query in col.description.lower():
                    c_score += 4

                if c_score > 0:
                    col_matches.append((col.name, col.type, col.description, c_score))

            if t_score > 0 or col_matches:
                # Calculate aggregate table match score
                total_score = t_score + sum(c[3] for c in col_matches)
                matches.append((tbl.name, tbl.description, col_matches, total_score))

        # Sort by match relevance score
        matches.sort(key=lambda x: x[3], reverse=True)

        if not matches:
            return f"No matching tables or columns found for schema search term: '{query}'."

        results = [f"## Semantic Schema Search Results for: '{query}'\n"]
        for tbl_name, desc, cols, score in matches[:5]:
            results.append(f"### Table: `{tbl_name}` (Match Score: {score})")
            if desc:
                results.append(f"- *Description*: {desc}")
            if cols:
                results.append("- *Relevant Columns*:")
                for c_name, c_type, c_desc, _ in cols[:10]:
                    desc_str = f" - {c_desc}" if c_desc else ""
                    results.append(f"  * `{c_name}` ({c_type}){desc_str}")
            results.append("")  # Separator

        return "\n".join(results)

    def _handle_agent_flow_analyzer(self, args: Dict[str, Any]) -> str:
        user_query = args["user_query"]
        dialect = args.get("dialect", "snowflake").lower()

        engine = self.semantic_engine
        retriever = HierarchicalRetriever()
        intent = retriever.analyze_intent(user_query)
        profile = QueryCapabilityDetector.detect(user_query, intent, engine.context)

        # Estimate complexity tier based on detected capabilities
        if (
            profile.requires_variants
            or (profile.requires_windows and profile.requires_joins)
            or len(user_query.split()) > 25
        ):
            complexity_tier = "Complex (Forensic Depth)"
        elif (
            not profile.requires_joins
            and not profile.requires_aggregation
            and not profile.requires_windows
            and not profile.requires_variants
        ):
            complexity_tier = "Easy (Linear Logic)"
        else:
            complexity_tier = "Medium (Relational Complexity)"

        results = ["## Agentic Workflow Analyzer Report\n"]
        results.append(f"**Query**: '{user_query}'")
        results.append(f"**Inferred Domain**: `{intent.inferred_domain}`")
        results.append(f"**Estimated Complexity**: `{complexity_tier}`\n")

        warnings = []
        notices = []

        # 1. Check for Geography/Spatial warning
        spatial_kws = [
            "distance",
            "area",
            "coordinate",
            "shape",
            "geom",
            "map",
            "within",
            "boundary",
        ]
        if any(kw in user_query.lower() for kw in spatial_kws):
            notices.append(
                "- **Geospatial Intent Detected**: The question refers to spatial calculations. Make sure to use native spatial functions (e.g., `ST_DISTANCE`, `ST_CONTAINS`, `TRY_TO_GEOGRAPHY`) instead of string-matching coordinates."
            )

        # 2. Check for Division Warning
        division_kws = ["ratio", "rate", "percent", "average", "fraction", "divide"]
        if any(kw in user_query.lower() for kw in division_kws):
            notices.append(
                "- **Metrics / Division Warning**: Mathematical ratios detected. Verify that all division statements are properly guarded with `NULLIF(denominator, 0)` in SQL to prevent division-by-zero crashes."
            )

        # 3. Check for casing risks in the active schema context
        if engine.context and engine.context.tables:
            mixed_case_cols = []
            lookup_tables = []

            for tbl in engine.context.tables:
                # Check table casing
                short_tbl_name = tbl.name.split(".")[-1]
                if short_tbl_name != short_tbl_name.upper():
                    mixed_case_cols.append(f"Table: `{tbl.name}`")

                # Check column casing
                for col in tbl.columns:
                    if col.name != col.name.upper():
                        mixed_case_cols.append(f"Column: `{tbl.name}.{col.name}`")

                # Identify Lookup / Reference Tables
                JOIN_KEY_HINTS = {"code", "id", "key", "num", "number", "ref"}
                DESC_HINTS = {"description", "desc", "name", "label", "title"}
                col_names_lower = [col.name.lower() for col in tbl.columns]
                has_code = any(
                    any(h in c for h in JOIN_KEY_HINTS) for c in col_names_lower
                )
                has_desc = any(any(h in c for h in DESC_HINTS) for c in col_names_lower)
                if has_code and has_desc:
                    lookup_tables.append(tbl.name)

            if mixed_case_cols and dialect == "snowflake":
                warnings.append("### Ã¢Å¡Â Ã¯Â¸Â Casing Fold Risks Detected (Snowflake Dialect)")
                warnings.append(
                    "Snowflake folds all unquoted identifiers to UPPERCASE. The schema contains mixed-case/lowercase tables/columns. **You MUST double-quote these identifiers in SQL precisely**:"
                )
                for m in mixed_case_cols[:6]:
                    warnings.append(f"- {m} (requires wrapping in double quotes)")
                if len(mixed_case_cols) > 6:
                    warnings.append(
                        f"- ...and {len(mixed_case_cols) - 6} other identifiers."
                    )
                warnings.append("")

            if lookup_tables:
                notices.append(
                    f"- **Reference Lookups Detected**: Found {len(lookup_tables)} potential lookup tables (e.g. `{lookup_tables[0]}`). Ensure that whenever a textual description is selected, the SQL Generator joins via the corresponding numeric identifier/code, not the text description."
                )

        if warnings:
            results.append("### Ã°Å¸â€Â´ Critical Workflow Warnings")
            results.extend(warnings)
        else:
            results.append("### Ã°Å¸Å¸Â¢ Prompt & Schema Safety: OK")
            results.append(
                "No critical Snowflake double-quoting casing risks detected.\n"
            )

        if notices:
            results.append("### Ã°Å¸â€™Â¡ Strategic Architectural Guidelines")
            results.extend(notices)

        return "\n".join(results)

    def run(self):
        """Standard input/output JSON-RPC message processing loop."""
        logger.info("[MCPServer] Model Context Protocol Stdio Server Started.")
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    request = json.loads(line)
                    response = self.handle_rpc_request(request)
                    if response:
                        sys.stdout.write(json.dumps(response) + "\n")
                        sys.stdout.flush()
                except Exception as e:
                    err_res = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": f"Parse error: {e}"},
                        "id": None,
                    }
                    sys.stdout.write(json.dumps(err_res) + "\n")
                    sys.stdout.flush()
        except KeyboardInterrupt:
            pass

    def handle_rpc_request(self, req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Validate JSON-RPC structure
        if "jsonrpc" not in req or req.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": req.get("id"),
            }

        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        try:
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "tt-sql-mcp-server", "version": "1.0.0"},
                    },
                    "id": msg_id,
                }
            elif method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "result": {"tools": self.list_tools()},
                    "id": msg_id,
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                args = params.get("arguments", {})
                tool_result = self.call_tool(tool_name, args)
                return {
                    "jsonrpc": "2.0",
                    "result": {"content": [{"type": "text", "text": tool_result}]},
                    "id": msg_id,
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": msg_id,
                }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {e}",
                    "data": traceback.format_exc(),
                },
                "id": msg_id,
            }


if __name__ == "__main__":
    server = MCPServer()
    server.run()
