from core.sqlite_service import SQLiteService
from core.sf_service import SnowflakeService
from core.bq_service import BigQueryService
from core.logger import Logger
import os

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
                svc = SQLiteService(state.db_path)
                tables = svc.get_table_names()
            elif dialect == "snowflake":
                svc = SnowflakeService()
                parts = db_name.split(".")
                db = parts[0] if len(parts) > 0 else db_name
                sch = parts[1] if len(parts) > 1 else db
                tables = svc.get_table_names(db, sch)
            elif dialect == "bigquery":
                svc = BigQueryService()
                tables = svc.get_table_names(db_name)
            else:
                return {"error": f"Unsupported dialect: {dialect}"}
            
            state.all_table_names = tables
            Logger.log(f"Schema retrieved: {len(tables)} tables")
            return {"status": "success", "tables": tables}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_column_details(state, params=None):
        """Task 2: Stage 3 - Fetch columns for selected tables."""
        tables = []
        if params:
            tables = params.get("selected_tables") or params.get("tables") or []
        
        if not tables:
            tables = getattr(state, "selected_tables", [])
            
        if not tables:
            return {"error": "No tables selected."}
        
        current_sel = set(getattr(state, "selected_tables", []))
        for t in tables:
            current_sel.add(t)
        state.selected_tables = list(current_sel)

        res = ToolRegistry.fetch_schema(state, params={"tables": tables})
        if res.get("status") == "success":
            state.all_columns_fetched = True
        return res

    @staticmethod
    def schema_selector(state, params=None):
        """Task 2: Stages 2 & 4 - LLM-driven filtering of tables and columns."""
        import json, re
        
        try:
            resp = params if params else {}
            if not resp:
                raw_response = getattr(state, "last_raw_response", "{}")
                try:
                    json_match = re.search(r"(\{.*\})", raw_response, re.DOTALL)
                    resp = json.loads(json_match.group(1)) if json_match else json.loads(raw_response)
                except:
                    resp = {}
            
            if resp.get("selected_tables"):
                selected_raw = resp["selected_tables"]
                final_selected = []
                for s_raw in selected_raw:
                    s_clean = s_raw.split(" ")[0].strip("\"' ")
                    for full_t in state.all_table_names:
                        full_t_clean = full_t.split(" ")[0].strip("\"' ")
                        if s_clean == full_t_clean or full_t_clean.endswith(f".{s_clean}") \
                           or s_clean.upper() == full_t_clean.upper():
                            if full_t not in final_selected:
                                final_selected.append(full_t)
                
                state.selected_tables = list(set(final_selected + state.selected_tables))
                Logger.log(f"Tables selected: {state.selected_tables}")

            sel_cols_resp = resp.get("selected_columns")
            if sel_cols_resp and isinstance(sel_cols_resp, dict):
                for t_raw, cols in sel_cols_resp.items():
                    t_clean = t_raw.strip("\"' ")
                    matched_table = None
                    for st in state.selected_tables:
                        st_clean = st.strip("\"' ")
                        if t_clean == st_clean or st_clean.endswith(f".{t_clean}") \
                           or t_clean.upper() == st_clean.upper():
                            matched_table = st
                            break
                    
                    if matched_table:
                        current = state.selected_columns.get(matched_table, [])
                        state.selected_columns[matched_table] = list(set(current + cols))
                
                Logger.log(f"Columns selected: {state.selected_columns}")
                
                new_info = {}
                from core.utils import normalize_identifier
                norm_selected = {normalize_identifier(k): cols for k, cols in state.selected_columns.items()}

                for t, details in state.full_schema_info.items():
                    norm_t = normalize_identifier(t)
                    if norm_t in norm_selected:
                        allowed = [c.upper() for c in norm_selected[norm_t]]
                        new_details = details.copy()
                        new_details["columns"] = [
                            c for c in details.get("columns", []) 
                            if c.get("column_name", "").upper() in allowed
                        ]
                        new_info[t] = new_details
                state.schema_info = new_info

            if resp.get("variant_required") and state.dialect == "snowflake":
                from core.variant_inspector import VariantInspector
                vi = VariantInspector(state.db_name)
                
                v_results = []
                for entry in resp["variant_required"]:
                    col_fqn = entry.get("column", "")
                    if not col_fqn: continue
                    parts = col_fqn.split(".")
                    p_table = parts[-2].strip("\"' ") if len(parts) >= 2 else ""
                    p_col = parts[-1].strip("\"' ")
                    
                    actual_table = None
                    for t_key in state.full_schema_info.keys():
                        t_clean = t_key.strip("\"' ")
                        if p_table == t_clean or t_clean.endswith(f".{p_table}") or p_table.upper() == t_clean.upper():
                            actual_table = t_key
                            break
                    
                    if actual_table and p_col:
                        inspection = vi.inspect_column(actual_table, p_col)
                        v_results.append(inspection)
                        for schema_map in [state.full_schema_info, state.schema_info]:
                            if schema_map and actual_table in schema_map:
                                for c in schema_map[actual_table].get("columns", []):
                                    if c.get("column_name", "").upper() == p_col.upper():
                                        keys = inspection.get("keys", {})
                                        c["variant_keys"] = keys
                                        c["variant_status"] = "known" if keys else "variant_unknown"
                                        break
                state.variant_required = v_results

            if state.dialect == "snowflake":
                from core.variant_inspector import VariantInspector
                vi = VariantInspector(state.db_name)
                for t, info in state.schema_info.items():
                    for c in info.get("columns", []):
                        if "VARIANT" in str(c.get("type", "")).upper() and not c.get("variant_keys"):
                            try:
                                inspection = vi.inspect_column(t, c["column_name"])
                                keys = inspection.get("keys", {})
                                c["variant_keys"] = keys
                                c["variant_status"] = "known" if keys else "variant_unknown"
                            except: pass

            return {"status": "success"}
        except Exception as e:
            Logger.log(f"Error parsing schema selection: {e}", level="ERROR")
            return {"status": "error", "message": str(e)}

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
                svc = SQLiteService(state.db_path)
                schema = svc.get_full_schema(table_list=table_list, sample_rows=sample_rows)
            elif dialect == "snowflake":
                svc = SnowflakeService()
                target_db = db_name.split(".")[0]
                target_sch = target_db
                schema = svc.get_schema(target_db, target_sch, table_list=table_list, sample_rows=sample_rows)
            elif dialect == "bigquery":
                svc = BigQueryService()
                target_dataset = db_name.split(".")[-1]
                schema = svc.get_dataset_schema(target_dataset, table_list=table_list, sample_rows=sample_rows)
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
        sql = params.get("sql") if (params and isinstance(params, dict)) else state.chosen_query
        if not sql:
            return {"status": "error", "message": "No SQL provided for execution."}
        
        dialect = state.dialect
        sampling = getattr(state, "sampling_enabled", False)
        Logger.start_capture()
        try:
            if dialect == "sqlite":
                svc = SQLiteService(state.db_path)
                result = svc.execute_query(sql, sampling=sampling)
            elif dialect == "snowflake":
                svc = SnowflakeService()
                parts = state.db_name.split(".")
                target_db, target_sch = parts[0], parts[1] if len(parts) > 1 else parts[0]
                result = svc.execute_query(sql, sampling=sampling)
            elif dialect == "bigquery":
                svc = BigQueryService()
                client = svc.get_client()
                rows = client.query(sql).result()
                from core.state import ExecutionResult
                result = ExecutionResult()
                result.columns = [field.name for field in rows.schema]
                all_rows = [list(row.values()) for row in rows]
                result.rows = all_rows[:5] if sampling else all_rows
                result.row_count = len(all_rows)
            else:
                return {"status": "error", "message": f"Dialect {dialect} not supported."}
            
            audit_logs = Logger.stop_capture()
            state.execution_result = result
            
            from core.utils import write_csv_to_file, write_sql_to_file
            write_csv_to_file(state.instance_id, state.db_name, result.rows if not result.error_message else [], result.columns if not result.error_message else [], state.model_name)
            write_sql_to_file(state.instance_id, state.db_name, sql, state.model_name, dialect=state.dialect)
            
            Logger.log_agent_block("SQL Execution Tool", inputs=[{"desc": "Target SQL Query", "status": "active"}], result=f"{audit_logs}\n\nSummary: {'SUCCESS' if not result.error_message else 'FAILED'} ({result.row_count} rows)", status="success" if not result.error_message else "failed")
            return {"status": "success", "row_count": result.row_count, "error": result.error_message}
        except Exception as e:
            audit_logs = Logger.stop_capture()
            Logger.log_agent_block("SQL Execution Tool", [], f"{audit_logs}\nError: {str(e)}", "failed")
            return {"error": str(e)}

    @staticmethod
    def table_pruner(state, params=None):
        """Standardized sliding-window table selection tool."""
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

        Logger.log_agent_block("Table Pruning Tool", inputs=[{"desc": f"Filtering {len(table_names)} tables", "status": "active"}], result=f"Selected {len(all_selected)} relevant tables: {all_selected}", status="success" if all_selected else "no tables picked")
        if all_selected:
            state.relevant_tables = all_selected
            ToolRegistry.fetch_schema(state, params={"tables": all_selected})
            state.schema_info = {t: state.schema_info[t] for t in all_selected if t in state.schema_info}
            return {"status": "success", "selected": len(all_selected)}
        return {"status": "fallback", "message": "No tables selected."}

    @staticmethod
    def _get_service(state):
        """Helper to get the appropriate database service based on dialect."""
        dialect = state.dialect
        if dialect == "sqlite": return SQLiteService(state.db_path)
        elif dialect == "snowflake": return SnowflakeService()
        elif dialect == "bigquery": return BigQueryService()
        return None

    @staticmethod
    def value_search(state, params=None):
        """Searches for a specific value in a table/column using LIKE matching."""
        table = params.get("table")
        column = params.get("column")
        term = params.get("search") or params.get("term")
        if not table or not column or not term: return {"status": "error", "message": "Missing required params: table, column, search/term"}
        from core.utils import quote_identifier
        service = ToolRegistry._get_service(state)
        q_table = quote_identifier(table, state.dialect)
        q_column = quote_identifier(column, state.dialect)
        query = f"SELECT DISTINCT {q_column} FROM {q_table} WHERE {q_column} LIKE '%{term}%' LIMIT 10"
        return service.execute_query(query)

    @staticmethod
    def get_tools_map():
        return {
            "fetch_schema": ToolRegistry.fetch_schema,
            "execute_sql": ToolRegistry.execute_sql,
            "table_pruner": ToolRegistry.table_pruner,
            "value_search": ToolRegistry.value_search,
            "get_table_names": ToolRegistry.get_table_names,
            "get_column_details": ToolRegistry.get_column_details,
            "schema_selector": ToolRegistry.schema_selector,
        }
