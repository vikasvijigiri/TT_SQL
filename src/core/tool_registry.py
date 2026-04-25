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
    def fetch_schema(state):
        """Fetches the full schema for the database in state."""
        Logger.log(f"[TOOL] Executing fetch_schema for {state.db_name}")
        dialect = state.dialect
        
        try:
            if dialect == "sqlite":
                svc = SQLiteService(state.db_path)
                schema = svc.get_full_schema()
            elif dialect == "snowflake":
                svc = SnowflakeService()
                db = state.db_name.split(".")[0] if "." in state.db_name else state.db_name
                sch = state.db_name.split(".")[1] if "." in state.db_name else state.db_name
                schema = svc.get_schema(db, sch)
            elif dialect == "bigquery":
                svc = BigQueryService()
                schema = svc.get_dataset_schema(state.db_name)
            else:
                return {"error": f"Unsupported dialect for tool: {dialect}"}
            
            state.schema_info = schema
            state.full_schema_info = schema
            
            from core.utils import write_db_metadata
            write_db_metadata(state.db_name, schema)
            
            return {"status": "success", "table_count": len(schema)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def execute_sql(state, params=None):
        """Executes SQL query on the target database."""
        sql = params.get("sql") if params else state.chosen_query
        if not sql:
            return {"error": "No SQL provided for execution."}
        
        Logger.log(f"[TOOL] Executing SQL on {state.dialect}")
        dialect = state.dialect
        sampling = getattr(state, "sampling_enabled", False)
        
        try:
            if dialect == "sqlite":
                svc = SQLiteService(state.db_path)
                result = svc.execute_query(sql, sampling=sampling)
            elif dialect == "snowflake":
                svc = SnowflakeService()
                result = svc.execute_query(sql, sampling=sampling)
            elif dialect == "bigquery":
                svc = BigQueryService()
                # Simplified BQ execute logic (usually client.query)
                client = svc.get_client()
                rows = client.query(sql).result()
                from core.state import ExecutionResult
                result = ExecutionResult()
                result.columns = [field.name for field in rows.schema]
                all_rows = [list(row.values()) for row in rows]
                result.rows = all_rows[:5] if sampling else all_rows
                result.row_count = len(all_rows)
            else:
                return {"error": f"Dialect {dialect} execution not yet in tool-set."}
            
            state.execution_result = result
            if result.error_message:
                state.execution_error_history.append(result.error_message)
            
            # Nice Logging in markdown
            Logger.log_execution(sql, result)
            
            # Auto-save results and SQL
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
    def table_pruner(state, params=None):
        """Standardized sliding-window table selection tool."""
        if not state.schema_info:
            return {"error": "No schema available."}
        
        # Configurable window size
        window_size = 20
        table_names = sorted(list(state.schema_info.keys()))
        all_selected = []
        all_cols = {}
        
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
                    cols = item.get("columns", []) if isinstance(item, dict) else []
                    if tname in state.schema_info:
                        if tname not in all_selected: all_selected.append(tname)
                        if cols:
                            if tname not in all_cols: all_cols[tname] = set()
                            all_cols[tname].update(cols)
            except: continue

        if all_selected:
            state.relevant_tables = all_selected
            pruned = {}
            for t in all_selected:
                original = state.schema_info[t]
                pruned[t] = original # Simplified pruning for now
            state.schema_info = pruned
            return {"status": "success", "selected": len(all_selected)}
        
        return {"status": "fallback", "message": "No tables selected."}

    @staticmethod
    def sql_refinement_loop(state, params=None):
        """Advanced ensemble SQL builder-critic loop tool. 
        Respects '1-2 candidates' rule and ensures a final answer.
        """
        from agents.generic_agent import GenericAgent
        from core.llm_service import LLMService
        from core.prompt_loader import PromptLoader
        import re, json, copy
        
        llm = LLMService(model=state.model_name)
        # Builder now returns 'candidates' list
        generator = GenericAgent("SQLBuilder", "sql_builder", output_key="candidates", state_field="sql_candidates", llm_service=llm, max_tokens=6000)
        max_retries = 2 # Efficient refinement
        
        for attempt in range(1, max_retries + 1):
            state.iteration_count = attempt
            Logger.log_stage_header(f"🔄 ENSEMBLE ATTEMPT {attempt}")
            
            # 1. Generate Candidates (Now 1-2 as per new prompt)
            generator.run(state)
            candidates = getattr(state, "sql_candidates", [])
            
            # CRITICAL: If no candidates generated, force a single candidate generation
            if not candidates:
                Logger.log("⚠️ No candidates generated. Retrying with explicit single-SQL instruction.", "WARN")
                # Add a temporary instruction to state or just retry once more with same generator
                generator.run(state)
                candidates = getattr(state, "sql_candidates", [])
                if not candidates: break # Total failure
            
            # 2. Execute & Prepare Context
            evaluated_candidates = []
            for item in candidates:
                cand_sql = item.get("sql", "")
                if not cand_sql: continue
                
                service = SQLiteService(state.db_path)
                res = service.execute_query(cand_sql, sampling=True)
                
                Logger.log(f"🧪 Sampling Candidate {item.get('id')}...")
                Logger.log_execution(cand_sql, res)
                
                evaluated_candidates.append({
                    "id": item.get("id"),
                    "sql": cand_sql,
                    "reasoning": item.get("reasoning", "No reasoning provided."),
                    "execution": {
                        "error": res.error_message,
                        "rows": res.rows[:3],
                        "row_count": res.row_count
                    }
                })

            if not evaluated_candidates: continue

            # 3. Selection Critique
            state.audit_context = json.dumps(evaluated_candidates)
            messages = PromptLoader().load_prompt("sql_critic", state=state)
            response = llm.get_json_completion(messages, state=state, agent_name="SQLSelector")
            
            winner_id = response.get("winning_id")
            is_valid = response.get("is_valid", False)
            
            # Find the winning SQL or fallback to first
            winner = next((c for c in evaluated_candidates if c["id"] == winner_id), evaluated_candidates[0])
            
            state.chosen_query = winner["sql"]
            state.is_result_valid = is_valid
            state.critic_feedback = response.get("feedback", "Final selection.")
            
            if is_valid:
                Logger.log(f"✅ Selection Success: Candidate {winner_id} picked.")
                break
            else:
                Logger.log(f"⚠️ Critic rejected all or winner {winner_id}. Retrying...", "WARN")

        # Final Execution Guarantee
        if state.chosen_query:
            state.sampling_enabled = False
            ToolRegistry.execute_sql(state)
        else:
            Logger.log("🔴 CRITICAL: No SQL query could be generated after all retries.", "ERROR")
            
        return {"status": "success" if state.chosen_query else "failed"}

    @staticmethod
    def value_search(state, params=None):
        """Searches for a specific value in a table/column using LIKE matching."""
        from core.sqlite_service import SQLiteService
        if not state.db_path: return {"status": "error", "message": "No database path provided."}
        
        table = params.get("table")
        column = params.get("column")
        term = params.get("term")
        
        if not table or not column or not term:
            return {"status": "error", "message": "Missing required params: table, column, term"}
            
        service = SQLiteService(state.db_path)
        query = f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" LIKE "%{term}%" LIMIT 10'
        result = service.execute_query(query)
        
        if result.error_message:
            return {"status": "error", "message": result.error_message}
            
        matches = [str(row[0]) for row in result.rows]
        discovered_entry = f"{table}.{column}: {matches}"
        
        if not hasattr(state, "discovered_values"): state.discovered_values = []
        state.discovered_values.append(discovered_entry)
        
        return {"status": "success", "matches": matches}

    @staticmethod
    def accurate_calculate(state, params=None):
        """Performs high-precision math calculation."""
        from core.math_service import MathService
        expr = params.get("expression") if params else None
        if not expr:
            return {"error": "No expression provided."}
        
        result = MathService.calculate(expr)
        Logger.log(f"[TOOL] Accurate Calculate: {expr} = {result}")
        return {"status": "success", "result": result}

    @staticmethod
    def python_executor(state, params=None):
        """Executes arbitrary Python code for complex logic verification."""
        code = params.get("code") if params else None
        if not code:
            return {"error": "No code provided."}
        
        try:
            # Shared dictionary for execution
            exec_globals = {"Decimal": float, "math": __import__("math")}
            exec(code, exec_globals)
            result = exec_globals.get("result", "No 'result' variable set in code.")
            Logger.log(f"[TOOL] Python Executor ran successfully. Result: {result}")
            return {"status": "success", "result": result}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_tools_map():
        return {
            "fetch_schema": ToolRegistry.fetch_schema,
            "execute_sql": ToolRegistry.execute_sql,
            "table_pruner": ToolRegistry.table_pruner,
            "sql_refinement_loop": ToolRegistry.sql_refinement_loop,
            "value_search": ToolRegistry.value_search,
            "accurate_calculate": ToolRegistry.accurate_calculate,
            "python_executor": ToolRegistry.python_executor
        }
