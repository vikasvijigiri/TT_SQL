import os
from core.logger import Logger

class ToolRegistry:
    """
    A registry of Python functions (tools) that can be called by GenericAgents.
    """
    
    @staticmethod
    def get_table_names(state, params=None):
        """Task 2: Stage 1 - Fetch only table names."""
        dialect = state.dialect
        db_name = state.db_name
        
        try:
            if dialect == "sqlite":
                from core.sqlite_service import SQLiteService
                svc = SQLiteService(state.db_path)
                tables = svc.get_table_names()
            elif dialect == "snowflake":
                from core.sf_service import SnowflakeService
                svc = SnowflakeService()
                db = db_name.split(".")[0] if "." in db_name else db_name
                conn = svc.get_connection(database=db)
                r_db = svc.get_real_database_name(conn, db)
                cursor = conn.cursor()
                cursor.execute(f"SHOW TABLES IN DATABASE \"{r_db}\"")
                tables = [row[1] for row in cursor.fetchall()]
            elif dialect == "bigquery":
                from core.bq_service import BigQueryService
                svc = BigQueryService()
                schema = svc.get_dataset_schema(db_name)
                tables = list(schema.keys())
            else:
                return {"error": f"Dialect {dialect} not supported for get_table_names"}
                
            return {"status": "success", "tables": tables}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def fetch_schema(state, params=None):
        """Fetches the schema for the database in state."""
        dialect = state.dialect
        db_name = state.db_name
        table_list = params.get("tables") if params else None
        sample_rows = params.get("sample_rows", False) if params else False
        
        Logger.start_capture()
        try:
            if dialect == "sqlite":
                from core.sqlite_service import SQLiteService
                svc = SQLiteService(state.db_path)
                schema = svc.get_full_schema(table_list=table_list, sample_rows=sample_rows)
            elif dialect == "snowflake":
                from core.sf_service import SnowflakeService
                svc = SnowflakeService()
                # Use multi-schema discovery logic
                schema = svc.fetch_schema(database=db_name, table_list=table_list)
            elif dialect == "bigquery":
                from core.bq_service import BigQueryService
                svc = BigQueryService()
                schema = svc.get_dataset_schema(db_name) # Already does full fetch
            else:
                return {"error": f"Unsupported dialect: {dialect}"}
            
            audit_logs = Logger.stop_capture()
            Logger.log(f"Schema retrieved: {len(schema)} tables")
            
            if table_list and state.schema_info:
                state.schema_info.update(schema)
                state.full_schema_info.update(schema)
            else:
                state.schema_info = schema
                state.full_schema_info = schema
            
            state.all_table_names = list(schema.keys())
            
            from core.utils import write_db_metadata
            write_db_metadata(db_name, state.full_schema_info)
            
            mode = "Detailed" if table_list else "Lightweight"
            Logger.log_agent_block(
                f"Schema Extraction Tool ({mode})",
                inputs=[{"desc": f"Extracting metadata for {db_name}", "status": "active"}],
                result=f"{audit_logs}\n\nSummary: Discovered/Updated {len(schema)} tables.",
                status="success"
            )
            return {"status": "success", "table_count": len(schema)}
        except Exception as e:
            audit_logs = Logger.stop_capture()
            Logger.log_agent_block("Schema Extraction Tool", [], f"{audit_logs}\nError: {str(e)}", "failed")
            return {"error": str(e)}

    @staticmethod
    def execute_sql(state, params=None):
        """Executes SQL query on the target database."""
        sql = params.get("sql") if params else state.chosen_query
        if not sql:
            return {"error": "No SQL provided for execution."}
        
        Logger.log(f"[TOOL] Executing SQL on {state.dialect}")
        dialect = state.dialect
        
        try:
            if dialect == "sqlite":
                from core.sqlite_service import SQLiteService
                svc = SQLiteService(state.db_path)
                result = svc.execute_query(sql)
            elif dialect == "snowflake":
                from core.sf_service import SnowflakeService
                svc = SnowflakeService()
                result = svc.execute_query(sql, database=state.db_name)
            elif dialect == "bigquery":
                from core.bq_service import BigQueryService
                svc = BigQueryService()
                client = svc.get_client()
                rows = client.query(sql).result()
                from core.state import ExecutionResult
                result = ExecutionResult()
                result.columns = [field.name for field in rows.schema]
                result.rows = [list(row.values()) for row in rows]
                result.row_count = len(result.rows)
            else:
                return {"error": f"Dialect {dialect} execution not yet in tool-set."}
            
            state.execution_result = result
            if result.error_message:
                if not hasattr(state, "execution_error_history"): state.execution_error_history = []
                state.execution_error_history.append(result.error_message)
            
            Logger.log_execution(sql, result)
            
            from core.utils import write_csv_to_file, write_sql_to_file
            write_csv_to_file(
                state.instance_id, 
                state.db_name, 
                result.rows if not result.error_message else [["error", result.error_message]], 
                result.columns if not result.error_message else ["status", "error"],
                state.model_name
            )
            write_sql_to_file(state.instance_id, state.db_name, sql, state.model_name)
            
            return {"status": "success", "row_count": result.row_count, "error": result.error_message}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_column_details(state, params=None):
        """Task 2: Stage 3/4 - Fetch detailed column metadata."""
        return ToolRegistry.fetch_schema(state, params=params)

    @staticmethod
    def table_pruner(state, params=None):
        if not state.schema_info: return {"error": "No schema available."}
        window_size = 20
        table_names = sorted(list(state.schema_info.keys()))
        all_selected = []
        from core.llm_service import LLMService
        from core.prompt_loader import PromptLoader
        from core.utils import format_schema_to_str
        import re, json
        llm = LLMService(model=state.model_name)
        loader = PromptLoader()
        for i in range(0, len(table_names), window_size):
            window = table_names[i:i+window_size]
            window_schema = {t: state.schema_info[t] for t in window}
            schema_str = format_schema_to_str(window_schema, detailed=False)
            messages = loader.load_prompt("table_selector", state=state, schema_path=schema_str)
            resp_text = llm.get_completion(messages, state=state, agent_name="Tool:TablePruner")
            try:
                json_match = re.search(r"(\{.*\})", resp_text, re.DOTALL)
                resp_json = json.loads(json_match.group(1)) if json_match else json.loads(resp_text)
                for item in resp_json.get("relevant_tables", []):
                    tname = item if isinstance(item, str) else item.get("table")
                    if not tname: continue
                    t_clean = str(tname).split(" ")[0].replace('"', '').replace("'", "").lower()
                    matched_table = None
                    for schema_table in state.schema_info.keys():
                        st_clean = str(schema_table).split(" ")[0].replace('"', '').replace("'", "").lower()
                        if t_clean == st_clean or st_clean.endswith(f".{t_clean}"):
                            matched_table = schema_table
                            break
                    if matched_table and matched_table not in all_selected:
                        all_selected.append(matched_table)
            except: continue
        if all_selected:
            state.relevant_tables = all_selected
            ToolRegistry.fetch_schema(state, params={"tables": all_selected})
            state.schema_info = {t: state.schema_info[t] for t in all_selected if t in state.schema_info}
            return {"status": "success", "selected": len(all_selected)}
        return {"status": "fallback", "message": "No tables selected."}

    @staticmethod
    def value_search(state, params=None):
        table, column, term = params.get("table"), params.get("column"), params.get("search") or params.get("term")
        if not table or not column or not term: return {"status": "error", "message": "Missing params"}
        dialect = state.dialect
        if dialect == "sqlite":
            from core.sqlite_service import SQLiteService
            svc = SQLiteService(state.db_path)
        elif dialect == "snowflake":
            from core.sf_service import SnowflakeService
            svc = SnowflakeService()
        else: return {"status": "error", "message": f"Unsupported dialect {dialect}"}
        from core.utils import quote_identifier
        q_table = quote_identifier(table, dialect)
        q_column = quote_identifier(column, dialect)
        query = f"SELECT DISTINCT {q_column} FROM {q_table} WHERE {q_column} LIKE '%{term}%' LIMIT 10"
        return svc.execute_query(query, database=state.db_name)

    @staticmethod
    def _get_service(state):
        """Helper to get the appropriate database service based on dialect."""
        dialect = state.dialect
        if dialect == "sqlite":
            from core.sqlite_service import SQLiteService
            return SQLiteService(state.db_path)
        elif dialect == "snowflake":
            from core.sf_service import SnowflakeService
            return SnowflakeService()
        elif dialect == "bigquery":
            from core.bq_service import BigQueryService
            return BigQueryService()
        return None

    @staticmethod
    def get_tools_map():
        return {
            "fetch_schema": ToolRegistry.fetch_schema,
            "execute_sql": ToolRegistry.execute_sql,
            "table_pruner": ToolRegistry.table_pruner,
            "value_search": ToolRegistry.value_search,
            "get_table_names": ToolRegistry.get_table_names,
            "get_column_details": ToolRegistry.get_column_details
        }
