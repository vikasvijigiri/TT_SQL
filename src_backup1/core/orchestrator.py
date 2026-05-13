import time
import asyncio
import json
import os
from datetime import datetime
import sqlglot
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from src.utils.logger import logger
from src.utils.llm import LLMService
from src.utils.prompt_loader import PromptLoader
from src.schema.schema_graph_builder import SchemaGraphBuilder
from src.schema.embedding_retriever import EmbeddingRetriever
from src.validation.sql_validator import SQLValidator
from src.utils.result_handler import save_results
from src.utils.schema_formatter import format_schema_to_str
from src.utils.data_iq import analyze_result
from src.core.models import FullPlan, CriticResult, SQLBuilderOutput, TablePruningResult, ColumnPruningResult, ValuePruningResult
from src.utils.cache_manager import CacheManager

@dataclass
class PipelineResult:
    status: str            # "success" | "failed"
    sql: str = ""
    row_count_estimate: int = 0
    stage_timings: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0

class Text2SQLPipeline:
    """
    Unified Hierarchical Planning-First Text2SQL Pipeline.
    """
    
    def __init__(self, db_name: str, db_connector, llm: LLMService, schema_with_samples: Dict[str, Any], dialect: str = "snowflake"):
        self.db_name = db_name
        self.db = db_connector
        self.llm = llm
        self.dialect = dialect
        self.schema_with_samples = schema_with_samples
        
        # Initialize Core Components
        self.builder = SchemaGraphBuilder(schema_with_samples, db_name)
        self.builder.build_or_load()
        self.embedder = EmbeddingRetriever(self.builder, db_name)
        self.sql_validator = SQLValidator(db_connector, db_name=db_name)
        self.cache = CacheManager()
        
        # Extract default schema name from the first table FQN
        self.schema_name = "PUBLIC"
        if schema_with_samples:
            first_key = list(schema_with_samples.keys())[0]
            parts = first_key.split(".")
            if len(parts) >= 2:
                self.schema_name = parts[1]
                
        # Paths to prompts
        self.table_pruner_path = os.path.join("src", "prompts", "small_schema", "table_pruner.yaml")
        self.column_pruner_path = os.path.join("src", "prompts", "small_schema", "column_pruner.yaml")
        self.value_pruner_path = os.path.join("src", "prompts", "small_schema", "value_pruner.yaml")
        self.planner_path = os.path.join("src", "prompts", "small_schema", "query_planner.yaml")
        self.planner_critic_path = os.path.join("src", "prompts", "small_schema", "query_critic.yaml")
        self.gen_path = os.path.join("src", "prompts", "small_schema", "sql_builder.yaml")
        self.gen_critic_path = os.path.join("src", "prompts", "small_schema", "sql_critic.yaml")
        
        # Dialect specific instructions
        self.dialect_instructions = self._load_dialect_instructions(dialect)

    def _load_dialect_instructions(self, dialect: str) -> str:
        dialect_yaml = os.path.join("src", "prompts", "small_schema", f"{dialect}.yaml")
        if os.path.exists(dialect_yaml):
            try:
                msgs = PromptLoader.load(dialect_yaml, variables={})
                return msgs[0]["content"] if msgs else ""
            except: pass
        return ""

    def run(self, question: str, external_knowledge: str = "") -> PipelineResult:
        """Runs the full pipeline synchronously."""
        return asyncio.run(self.run_async(question, external_knowledge=external_knowledge))

    async def run_async(self, question: str, external_knowledge: str = "") -> PipelineResult:
        """Hierarchical Pruning -> Planning -> Generation."""
        start_time = time.time()
        result = PipelineResult(status="processing")
        timings = {}

        try:
            full_schema_compressed = format_schema_to_str(self.schema_with_samples, mode="compressed")
            # 1. Hierarchical Pruning Stage
            s_start = time.time()
            
            # Optimization: Skip pruning if schema is small enough (< 4k tokens approx)
            # Conservative estimate: 1 token ~= 3.5 characters
            estimated_tokens = len(full_schema_compressed) / 3.5
            
            if estimated_tokens < 4000:
                logger.info(f"Schema is small ({int(estimated_tokens)} tokens). Skipping pruning stage.")
                pruned_schema = full_schema_compressed
                pruning_reasoning = "Full schema injected (small schema bypass)."
            else:
                logger.info(f"Schema is large ({int(estimated_tokens)} tokens). Starting Hierarchical Pruning Stage...")
                pruning_result = await self._pruning_stage(question, external_knowledge)
                if not pruning_result:
                    result.status = "failed"
                    result.warnings.append("Hierarchical Pruning failed to return a valid schema.")
                    return result
                pruned_schema, pruning_reasoning = pruning_result
            
            timings["pruning"] = time.time() - s_start
            
            if not pruned_schema:
                result.status = "failed"
                result.warnings.append("Failed to extract a valid semantic context.")
                return result

            # 2. Planning Loop
            s_start = time.time()
            plan_data = await self._planning_loop(question, pruned_schema, pruning_reasoning, external_knowledge)
            timings["planning"] = time.time() - s_start

            if not plan_data:
                result.status = "failed"
                result.warnings.append("Failed to generate a valid execution plan.")
                return result
                

            # 3. Generation Loop
            s_start = time.time()
            final_res = await self._generation_loop(question, pruned_schema, plan_data, external_knowledge)
            timings["generation"] = time.time() - s_start

            # 4. Finalize Result
            result.status = final_res["status"]
            result.sql = final_res.get("sql", "")
            result.rows = final_res.get("rows", [])
            result.row_count_estimate = final_res.get("row_count", 0)
            result.confidence = final_res.get("confidence", 0.0)
            result.warnings = final_res.get("warnings", [])
            result.stage_timings = timings
            result.latency_ms = (time.time() - start_time) * 1000

            if result.status == "success":
                save_results(self.db_name, result.sql, result.rows)

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            result.status = "failed"
            result.warnings.append(str(e))

        return result

    async def _pruning_stage(self, question: str, external_knowledge: str) -> Optional[tuple]:
        """Hierarchical Pruning: Table -> Column -> Value/Variant."""
        logger.set_agent("PRUNER")
        # A. Table Pruning
        graph_summary = self._get_graph_summary()
        all_tables_context = format_schema_to_str(self.schema_with_samples, mode="compressed")
        
        table_vars = {
            "USER_QUERY": question,
            "EXTERNAL_KNOWLEDGE": external_knowledge,
            "SCHEMA_GRAPH": graph_summary,
            "all_tables": all_tables_context,
            "DB_NAME": self.db_name,
            "SCHEMA_NAME": self.schema_name
        }
        table_res_raw = self.llm.get_json_completion(PromptLoader.load(self.table_pruner_path, variables=table_vars), agent_name="TablePruner")
        try:
            table_res = TablePruningResult.model_validate(table_res_raw)
            logger.info(f"[SUCCESS] Table Pruning: {len(table_res.relevant_tables)} tables selected.")
        except ValidationError: 
            logger.error("[FAILED] Table Pruning validation failed.")
            return None
        
        # B. Check for Small Schema Optimization
        selected_tables_schema = {t: self.schema_with_samples[t] for t in table_res.relevant_tables if t in self.schema_with_samples}
        full_selected_schema_str = format_schema_to_str(selected_tables_schema, mode="full") # Mode full includes samples
        estimated_tokens = len(full_selected_schema_str) / 3.5

        if estimated_tokens < 2000:
            logger.info(f"Selected tables are small ({int(estimated_tokens)} tokens). Skipping Column/Value pruning and passing full table context.")
            pruning_reasoning = f"Table Selection: {table_res.reasoning}\nOptimization: Full schema provided for selected tables due to small size."
            return full_selected_schema_str, pruning_reasoning

        # C. Column Pruning (Continue Hierarchical if not optimized)
        logger.info(f"Selected tables are large ({int(estimated_tokens)} tokens). Continuing Hierarchical Pruning...")
        col_vars = {
            "USER_QUERY": question,
            "EXTERNAL_KNOWLEDGE": external_knowledge,
            "SELECTED_TABLES_SCHEMA": format_schema_to_str(selected_tables_schema, mode="compressed"),
            "SCHEMA_GRAPH": self._get_graph_summary(),
            "DB_NAME": self.db_name,
            "SCHEMA_NAME": self.schema_name
        }
        col_res_raw = self.llm.get_json_completion(PromptLoader.load(self.column_pruner_path, variables=col_vars), agent_name="ColumnPruner")
        try:
            col_res = ColumnPruningResult.model_validate(col_res_raw)
            
            # Hallucination Defense: Filter columns against actual schema
            cleaned_table_columns = {}
            for table, cols in col_res.table_columns.items():
                # Extract the base table name for matching
                base_table = table.split('.')[-1].upper()
                schema_table_key = next((t for t in self.schema_with_samples.keys() if base_table == t.upper().split('.')[-1]), None)
                if schema_table_key:
                    actual_cols = [c.get("name") or c.get("column_name") for c in self.schema_with_samples[schema_table_key]["columns"]]
                    valid_cols = [c for c in cols if c in actual_cols]
                    hallucinated = set(cols) - set(valid_cols)
                    if hallucinated:
                        logger.warning(f"[HALLUCINATION CAUGHT] Dropped columns from {table}: {hallucinated}")
                    if valid_cols:
                        cleaned_table_columns[table] = valid_cols
                else:
                    logger.warning(f"[HALLUCINATION CAUGHT] Dropped entire unknown table: {table}")
            col_res.table_columns = cleaned_table_columns
            
            logger.info(f"[SUCCESS] Column Pruning: {sum(len(c) for c in col_res.table_columns.values())} columns selected.")
        except ValidationError: 
            logger.error("[FAILED] Column Pruning validation failed.")
            return None
        
        # C. Value/Variant Pruning
        # Filter schema to only include selected columns for value pruning
        filtered_for_values = {}
        for table, cols in col_res.table_columns.items():
            # Robust table matching (handle short names or FQNs)
            schema_table_key = self._find_schema_table(table)
            if schema_table_key:
                filtered_for_values[schema_table_key] = {
                    "columns": [c for c in self.schema_with_samples[schema_table_key]["columns"] if c["column_name"] in cols],
                    "sample": self.schema_with_samples[schema_table_key].get("sample", [])
                }
            else:
                logger.warning(f"Could not find table {table} in master schema for value pruning.")
        
        val_vars = {
            "USER_QUERY": question,
            "EXTERNAL_KNOWLEDGE": external_knowledge,
            "selected_columns_with_samples": json.dumps(filtered_for_values, indent=2),
            "DB_NAME": self.db_name,
            "SCHEMA_NAME": self.schema_name
        }
        val_res_raw = self.llm.get_json_completion(PromptLoader.load(self.value_pruner_path, variables=val_vars), agent_name="ValuePruner")
        try:
            val_res = ValuePruningResult.model_validate(val_res_raw)
            logger.info(f"[SUCCESS] Value/Variant Pruning: {len(val_res.values)} values, {len(val_res.variant_keys)} keys found.")
        except ValidationError: 
            logger.warning("[FAILED] Value/Variant Pruning validation failed. Continuing with empty results.")
            val_res = ValuePruningResult(reasoning="Failed to prune values")
        
        # D. Build Final Pruned Context and Collect Reasoning
        pruning_reasoning = f"Table Selection: {table_res.reasoning}\nColumn Selection: {col_res.reasoning}\nValue Grounding: {val_res.reasoning}"
        return self._build_pruned_schema_context(col_res, val_res), pruning_reasoning

    def _get_graph_summary(self) -> str:
        """Summarizes join paths from SchemaGraphBuilder."""
        summary = []
        for u, v, d in self.builder.graph.edges(data=True):
            if d.get("type") == "fk_candidate":
                summary.append(f"{u} <-> {v}")
        return "\n".join(sorted(list(set(summary))))

    def _log_execution_plan(self, plan_data: Dict[str, Any]):
        """Logs the step-by-step approach in a nice neat fashion."""
        steps = plan_data.get("action_plan", [])
        if not steps:
            logger.warning("No steps found in plan.")
            return

        logger.info("\n" + "="*60)
        logger.info(" " * 15 + "PLANNING: ANALYTICAL STRATEGY STEPS")
        logger.info("="*60)
        if plan_data.get("reasoning"):
            logger.info(f"REASONING: {plan_data['reasoning']}")
            logger.info("-" * 60)
        for i, step in enumerate(steps):
            logger.info(f"[STEP {i+1}] {step}")
            logger.info("-" * 40)
        logger.info("="*60 + "\n")

    def _build_pruned_schema_context(self, col_res: ColumnPruningResult, val_res: ValuePruningResult) -> str:
        """Constructs a detailed pruned schema string with types and samples."""
        from src.utils.schema_formatter import format_schema_to_str
        
        pruned_schema_dict = {}
        for table, cols in col_res.table_columns.items():
            # Find the correct key in schema_with_samples using case-insensitive match on the table name part
            base_table = table.split('.')[-1].upper()
            schema_table_key = next((t for t in self.schema_with_samples.keys() if base_table == t.upper().split('.')[-1]), None)
            
            if schema_table_key:
                # Create a filtered version of the table metadata
                table_meta = self.schema_with_samples[schema_table_key].copy()
                table_meta["columns"] = [c for c in table_meta["columns"] if (c.get("name") or c.get("column_name")) in cols]
                pruned_schema_dict[schema_table_key] = table_meta
            else:
                logger.warning(f"Could not find table {table} in master schema for final pruned context.")
        
        # Format the base schema with types and samples
        context = "### PRUNED SCHEMA CONTEXT ###\n\n"
        context += format_schema_to_str(pruned_schema_dict, mode="with_samples")
        context += "\n\n"
        
        # Append Grounded Values and Variant Keys if any
        if val_res.values:
            context += "### GROUNDED VALUES ###\n"
            context += json.dumps(val_res.values, indent=2)
            context += "\n\n"
            
        if val_res.variant_keys:
            context += "### VARIANT KEYS ###\n"
            context += json.dumps(val_res.variant_keys, indent=2)
            context += "\n"
            
        return context

    async def _planning_loop(self, question: str, schema: str, pruning_reasoning: str, external_knowledge: str) -> Optional[Dict[str, Any]]:
        """Autoadjustable Planning Loop with Last 2 History."""
        logger.set_agent("PLANNER")
        max_attempts = 3
        hard_cap = 6
        plan_history = [] # List of (plan_json, feedback)
        history_scores = []
        best_effort_plan = {}
        best_effort_score = -1.0
        
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            logger.info(f"Planning Attempt {attempt}/{max_attempts}...")
            
            # Format history (last 2)
            recent = plan_history[-2:]
            hist_str = ""
            for i, (old_p, old_f) in enumerate(recent):
                hist_str += f"--- FAILED ATTEMPT {len(plan_history)-len(recent)+i+1} ---\nPLAN:\n{json.dumps(old_p.action_plan, indent=2)}\n\nFEEDBACK:\n{old_f}\n-----------------------------------\n"
            
            convergence_warning = ""
            if recent:
                convergence_warning = f"\n\n[CRITICAL CONVERGENCE WARNING]\nYou have already failed {len(plan_history)} attempt(s). The previous plan was REJECTED by the auditor for the reasons listed in the FEEDBACK section below. You MUST explicitly repair these issues in your new plan. Failure to converge will result in pipeline termination.\n"

            planner_vars = {
                "USER_QUERY": question, "INTENT": question, "DIALECT_INSTRUCTIONS": self.dialect_instructions,
                "SCHEMA": schema, "PRUNING_REASONING": pruning_reasoning,
                "PREVIOUS_ACTION_PLAN": hist_str if hist_str else "None", 
                "FEEDBACK_ON_PREVIOUS_ACTION_PLAN": (convergence_warning + (recent[-1][1] if recent else "None")),
                "RESOLVED_ELEMENTS": "[]", "EXTERNAL_KNOWLEDGE": external_knowledge, "REFERENCE_DATE": datetime.now().strftime("%Y-%m-%d"),
                "DB_NAME": self.db_name,
                "SCHEMA_NAME": self.schema_name
            }
            plan_raw = self.llm.get_json_completion(PromptLoader.load(self.planner_path, variables=planner_vars), agent_name="QueryPlanner")
            if not plan_raw: continue

            try:
                plan_model = FullPlan.model_validate(plan_raw)
                plan_data = plan_model.model_dump()
                
                # Check for repetition
                if plan_history and json.dumps(plan_data, sort_keys=True) == json.dumps(plan_history[-1][0].model_dump(), sort_keys=True):
                    logger.warning("Planner returned an identical plan. Forcing correction...")
                    identity_warning = "\n[CRITICAL WARNING] Your new plan is IDENTICAL to the previous failed plan. You MUST change the logic/steps to address the feedback below."
                else:
                    identity_warning = ""

                self._log_execution_plan(plan_data)
                best_effort_plan = plan_data
            except ValidationError as e:
                logger.error(f"Planning Validation Failed: {str(e)}")
                continue

            critic_vars = {
                "USER_QUERY": question, "INTENT": question, "ACTION_PLAN": json.dumps(plan_data.get("action_plan", []), indent=2),
                "PREVIOUS_ACTION_PLAN": hist_str if hist_str else "None", 
                "FEEDBACK_ON_PREVIOUS_ACTION_PLAN": (identity_warning + recent[-1][1]) if recent else "None",
                "SCHEMA": schema, "REFERENCE_DATE": datetime.now().strftime("%Y-%m-%d"), "EXTERNAL_KNOWLEDGE": external_knowledge,
                "DIALECT_INSTRUCTIONS": self.dialect_instructions,
                "DB_NAME": self.db_name,
                "SCHEMA_NAME": self.schema_name
            }
            critic_raw = self.llm.get_json_completion(PromptLoader.load(self.planner_critic_path, variables=critic_vars), agent_name="QueryCritic")
            if not critic_raw: continue
            try:
                critic_res = CriticResult.model_validate(critic_raw)
            except ValidationError: continue

            score_map = {"pass": 1.0, "pass_with_risk": 0.5, "fail": 0.0}
            current_score = score_map.get(critic_res.logical_fit, 0.0)
            history_scores.append(current_score)
            
            if critic_res.is_valid:
                logger.info("\n" + "CONFIRMED " * 5)
                logger.info("  ACTION PLAN APPROVED BY AUDITOR")
                logger.info("CONFIRMED " * 5 + "\n")
                return plan_data
            
            logger.warning("\n" + "REJECTED " * 5)
            logger.info(f"  PLAN REJECTED (Attempt {attempt})")
            logger.info(f"  REASON: {critic_res.feedback}")
            if critic_res.suggested_fix:
                logger.info(f"  SUGGESTED FIX: {critic_res.suggested_fix}")
            logger.warning("REJECTED " * 5 + "\n")
            full_feedback = critic_res.feedback
            if critic_res.suggested_fix:
                full_feedback += f"\nSUGGESTED FIX: {critic_res.suggested_fix}"
            
            plan_history.append((plan_model, full_feedback))
            
            # Extension logic: if score improved, allow more attempts
            if len(history_scores) >= 2 and history_scores[-1] > history_scores[-2] and max_attempts < hard_cap:
                max_attempts += 2
                logger.info("Improvement detected in plan quality. Extending planning loop by +2.")
                
        # Log Plan Preview
        if best_effort_plan and isinstance(best_effort_plan, dict):
            action_plan = best_effort_plan.get("action_plan", [])
            if action_plan:
                logger.info("\n[QUERY PLAN STRATEGY]")
                for step in action_plan:
                    logger.info(f"- {step}")
                logger.info("\n")
        
        # Return best effort plan (dict) if no approval after max attempts
        return best_effort_plan

    async def _generation_loop(self, question: str, schema: str, plan: Dict[str, Any], external_knowledge: str) -> Dict[str, Any]:
        """Autoadjustable Generation Loop with Last 2 History."""
        logger.set_agent("BUILDER")
        max_attempts = 5
        hard_cap = 10
        gen_history = []
        history_scores = []
        best_effort_rows = []
        best_effort_sql = ""
        best_effort_score = -1.0
        
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            
            # Implementation of dynamic iteration extension (+2)
            if attempt == max_attempts and any(h[0] is not None for h in gen_history):
                max_attempts += 2
                logger.info(f"Extension triggered. New max attempts: {max_attempts}.")

            logger.info(f"Generation Attempt {attempt}/{max_attempts}...")
            
            # Format history (last 2)
            recent = gen_history[-2:]
            hist_str = ""
            for i, (old_sql, old_f) in enumerate(recent):
                hist_str += f"ATTEMPT {len(gen_history)-len(recent)+i+1}:\nSQL: {old_sql}\nFEEDBACK: {old_f}\n\n"

            convergence_warning = ""
            if gen_history:
                convergence_warning = f"\n\n[CRITICAL CONVERGENCE WARNING]\nYou have already failed {len(gen_history)} attempt(s). Your previous SQL was REJECTED. You MUST EXPLICITLY CHANGE YOUR APPROACH. DO NOT REPEAT THE SAME SQL. IF YOU USE SUBQUERIES AND THEY FAIL, USE CTEs OR JOINS INSTEAD.\n"

            feedback = ""
            if gen_history:
                feedback = gen_history[-1][1]

            # Add Snowflake-specific hint for subquery errors
            if feedback and "Unsupported subquery type" in feedback:
                feedback += "\n[HINT] Snowflake often fails with subqueries in WHERE/JOIN. Use CTEs or JOINs instead of IN (SELECT ...) if possible."

            gen_vars = {
                "USER_QUERY": question, "SCHEMA": schema,
                "STRATEGIES": json.dumps(plan.get("action_plan", []), indent=2),
                "PREVIOUS_SQL": hist_str if hist_str else "None", 
                "FEEDBACK": (convergence_warning + (recent[-1][1] if recent else "None")), 
                "DIALECT_INSTRUCTIONS": self.dialect_instructions,
                "DIALECT_CONSTRAINTS": "None", 
                "EXTERNAL_KNOWLEDGE": external_knowledge,
                "REFERENCE_DATE": datetime.now().strftime("%Y-%m-%d"),
                "DB_NAME": self.db_name,
                "SCHEMA_NAME": self.schema_name
            }
            gen_raw = self.llm.get_json_completion(PromptLoader.load(self.gen_path, variables=gen_vars), agent_name="SQLGenerator")
            if not gen_raw: continue
            try:
                gen_model = SQLBuilderOutput.model_validate(gen_raw)
                sql = gen_model.sql or (gen_model.candidates[0].sql if gen_model.candidates else None)
                if sql:
                    # Preliminary SQLGlot Validation
                    try:
                        sqlglot.transpile(sql, read=self.dialect)
                        logger.info(f"=== GENERATED SQL (VALID SYNTAX) ===\n{sql}")
                    except Exception as e:
                        logger.error(f"[FAILED] SQL Syntax Error: {str(e)}")
                        gen_history.append((sql, f"Syntax Error: {str(e)}"))
                        continue
            except ValidationError: continue
                
            validation = self.sql_validator.validate_and_execute(type('obj', (object,), {'sql': sql, 'dialect': self.dialect}), {"query": question})
            # 2c. Data IQ & Relaxation
            iq_res = analyze_result(validation.rows)
            history_scores.append(iq_res["confidence_score"])
            
            # Capture best effort
            if validation.is_valid and iq_res["confidence_score"] > best_effort_score:
                best_effort_rows = validation.rows
                best_effort_sql = sql
                best_effort_score = iq_res["confidence_score"]
            
            # Auto-Relaxation: If 0 rows, try to diagnose why
            relaxation_feedback = ""
            if validation.is_valid and validation.row_count_estimate == 0:
                relaxed_sql, removed_filter = self.sql_validator._diagnose_empty(sql, {"schema_mapping": {"mapped_fields": []}}) # Simplification for now
                if relaxed_sql:
                    logger.warning(f"Query returned 0 rows. Relaxed version (removing {removed_filter}) might work.")
                    relaxation_feedback = f"\n[DIAGNOSTIC] The query returned 0 rows. Removing the filter on '{removed_filter}' might yield results. Consider if this filter is too restrictive or mapped to the wrong column."

            # 2d. SQL Critic
            audit_context = {
                "sql": validation.final_sql,
                "reasoning": gen_model.reasoning if 'gen_model' in locals() else "Generated SQL",
                "execution": {
                    "status": "success" if validation.is_valid else "error",
                    "error_message": validation.warnings[0] if validation.warnings else "None",
                    "row_count": validation.row_count_estimate
                },
                "dataiq": iq_res
            }
            critic_vars = {
                "USER_QUERY": question, 
                "SCHEMA": schema, 
                "DIALECT_INSTRUCTIONS": self.dialect_instructions,
                "DIALECT_CONSTRAINTS": "None",
                "STRATEGIES": json.dumps(plan.get("action_plan", []), indent=2),
                "PREVIOUS_GENERATED_SQL": hist_str if hist_str else "None", 
                "SQL": validation.final_sql,
                "AUDIT_CONTEXT": json.dumps(audit_context, indent=2),
                "REFERENCE_DATE": datetime.now().strftime("%Y-%m-%d"), 
                "EXTERNAL_KNOWLEDGE": external_knowledge,
                "DB_NAME": self.db_name,
                "SCHEMA_NAME": self.schema_name
            }
            critic_raw = self.llm.get_json_completion(PromptLoader.load(self.gen_critic_path, variables=critic_vars), agent_name="SQLCritic")
            if not critic_raw: continue
            try:
                critic_res = CriticResult.model_validate(critic_raw)
                # Append relaxation feedback to the critic's feedback
                if relaxation_feedback:
                    critic_res.feedback = relaxation_feedback + "\n" + critic_res.feedback
            except ValidationError: continue
            
            if critic_res.is_valid and validation.is_valid:
                logger.info("\n" + "SUCCESS " * 5)
                logger.info("  SQL APPROVED BY AUDITOR & EXECUTOR")
                logger.info("SUCCESS " * 5 + "\n")
                return {"sql": validation.final_sql, "rows": validation.rows, "row_count": validation.row_count_estimate, "confidence": iq_res["confidence_score"], "status": "success"}
            
            logger.warning("\n" + "FAILURE " * 5)
            logger.info(f"  SQL REJECTED (Attempt {attempt})")
            logger.info(f"  AUDITOR STATUS: {'SUCCESS' if critic_res.is_valid else 'FAILED'}")
            logger.info(f"  LOGICAL FIT: {critic_res.logical_fit.upper()}")
            logger.info(f"  EXECUTOR STATUS: {'SUCCESS' if validation.is_valid else 'FAILED'}")
            full_feedback = ""
            if not validation.is_valid:
                full_feedback += f"EXECUTION ERROR: {validation.warnings[0] if validation.warnings else 'Unknown error'}\n"
            
            full_feedback += f"AUDITOR FEEDBACK: {critic_res.feedback}"
            if critic_res.suggested_fix:
                full_feedback += f"\nSUGGESTED FIX: {critic_res.suggested_fix}"
            
            # Log Results Preview
            if validation.is_valid and validation.rows:
                from tabulate import tabulate
                preview = tabulate(validation.rows[:5], headers="keys", tablefmt="pretty")
                logger.info("\n[EXECUTION PREVIEW]\n" + preview + "\n")
            
            gen_history.append((sql, full_feedback))
            
            if len(history_scores) >= 2 and history_scores[-1] > history_scores[-2] and max_attempts < hard_cap:
                max_attempts += 2
                logger.info("Improvement detected in result quality. Extending generation loop by +2.")
                
        # Best effort return
        if best_effort_rows:
            logger.warning("Max attempts reached. Returning best effort results.")
            return {"status": "failed", "sql": best_effort_sql, "rows": best_effort_rows, "warnings": ["Max attempts reached. Returning best effort results."]}
            
        return {"status": "failed", "warnings": ["Max attempts reached."]}

    def _find_schema_table(self, table_name: str) -> Optional[str]:
        """Matches a table name (short or FQN) against schema keys."""
        if not table_name: return None
        
        # 1. Direct match
        if table_name in self.schema_with_samples:
            return table_name
            
        # 2. Case-insensitive match
        for k in self.schema_with_samples.keys():
            if k.lower() == table_name.lower():
                return k
                
        # 3. Short name match (e.g. "DICOM_ALL" matches "DB.SCHEMA.DICOM_ALL")
        for k in self.schema_with_samples.keys():
            if k.split(".")[-1].lower() == table_name.lower():
                return k
                
        return None
