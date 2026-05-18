from backend.app.utils.logger import logger
from backend.app.utils.llm import LLMClient
from backend.app.services.semantic_engine import SemanticContextEngine
from backend.app.agents.schema_linker import SchemaLinker
from backend.app.services.sql_generator import AdaptiveSQLGenerator
from backend.app.agents.sql_corrector import ExecutionCorrector
from backend.app.repositories.db_executor import DatabaseExecutor
from backend.app.services.result_validator import ResultValidator

from backend.app.services.knowledge_service import WebKnowledgeService
from backend.app.services.sql_manager import SQLManager
from backend.app.utils.stabilizer import ExecutionStabilizer
from backend.app.agents.profiler import DynamicProfiler
from backend.app.agents.critic import SQLCritic
from backend.app.core.observability.telemetry import PipelineTelemetry
from backend.app.core.dialects.rule_retriever import DialectRuleRetriever
from backend.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever

import pandas as pd
import os
import time
import re
import yaml
from pathlib import Path
from backend.app.core.config import RESULTS_DIR, CONFIG_DIR
from backend.app.utils.dialect_loader import DialectLoader

class SemanticDINOrchestrator:
    def __init__(self, db_directory: str, db_name: str, dialect: str = "snowflake", max_retries: int = 3):
        self.db_name = db_name
        
        logger.log_section("Initializing Semantic DIN-SQL Pipeline", color=logger.CYAN)
        
        self.llm = LLMClient()
        self.executor = DatabaseExecutor(db_name=db_name, dialect=dialect)
        self.stabilizer = ExecutionStabilizer(self.executor)
        self.semantic_engine = SemanticContextEngine(db_directory=db_directory)
        self.schema_linker = SchemaLinker(self.llm, self.semantic_engine)
        self.sql_generator = AdaptiveSQLGenerator(self.llm, self.semantic_engine, dialect)
        self.corrector = ExecutionCorrector(self.llm, self.semantic_engine, dialect)
        self.validator = ResultValidator(self.llm, self.semantic_engine)
        self.sql_manager = SQLManager()
        self.knowledge_tool = WebKnowledgeService()
        self.dialect_loader = DialectLoader()
        self.profiler = DynamicProfiler()
        self.critic = SQLCritic(self.llm, self.semantic_engine)
        
        # Load System Parameters
        params_path = CONFIG_DIR / "system_params.yaml"
        with open(params_path, 'r', encoding='utf-8') as f:
            self.params = yaml.safe_load(f)
            
        self.max_retries = self.params['orchestrator'].get('max_retries', max_retries)
        
        # Build context immediately
        self.semantic_engine.build_context()

    def _safe_markdown_preview(self, df: pd.DataFrame, max_rows: int = 10, max_col_width: int = 100) -> str:
        if df.empty:
            return "No preview available (0 rows)."
        preview_df = df.head(max_rows).copy()
        for col in preview_df.columns:
            preview_df[col] = preview_df[col].astype(str).apply(lambda x: x[:max_col_width] + "..." if len(x) > max_col_width else x)
        md = preview_df.to_markdown(index=False)
        if len(md) > 4000:
            md = md[:4000] + "\n...[TRUNCATED]"
        return md

    def _get_base_lessons(self, intent, external_knowledge: str = None) -> str:
        rule_retriever = DialectRuleRetriever(self.executor.dialect)
        lessons = rule_retriever.retrieve_relevant_rules(intent)
        if external_knowledge:
            doc_path = Path(r"c:\Users\VikasVijigiri\Documents\old_txt_sql_spider2.0\backend\resources\documents") / external_knowledge
            if doc_path.exists():
                try:
                    doc_content = doc_path.read_text(encoding='utf-8')
                    lessons += f"\n\nEXTERNAL KNOWLEDGE / DOMAIN SPECIFICATIONS:\n{doc_content}\n"
                    logger.info(f"Loaded external knowledge from {external_knowledge}")
                except Exception as e:
                    logger.warning(f"Failed to read external knowledge file {external_knowledge}: {e}")
        return lessons

    def execute_query(self, user_query: str, instance_id: str = "test_instance", external_knowledge: str = None) -> str:
        start_time = time.time()
        telemetry = PipelineTelemetry(query_id=instance_id)
        telemetry.start_stage("schema_linking")

        logger.log_section(f"Processing Query", color=logger.BLUE)
        logger.info(f"Query: '{user_query}'")
        
        retriever = HierarchicalRetriever()
        intent = retriever.analyze_intent(user_query)
        lessons_context = self._get_base_lessons(intent, external_knowledge)
        
        # Estimate full schema size to decide on pruning
        full_schema_str = self.semantic_engine.format_for_prompt()
        h = self.params['orchestrator']['token_heuristic']
        estimated_tokens = len(full_schema_str) // h
        threshold = self.params['orchestrator']['pruning_threshold_tokens']
        
        logger.info(f"Schema density evaluated (~{estimated_tokens} tokens vs threshold {threshold}).")
        linked_schema = self.schema_linker.link_schema(user_query, dialect=self.executor.dialect, lessons=lessons_context, force_full=(estimated_tokens <= threshold))
        
        table_columns_map = {}
        if linked_schema and linked_schema.selected_columns:
            for fqn in linked_schema.selected_columns:
                if "." in fqn:
                    parts = fqn.split(".")
                    t_name = ".".join(parts[:-1])
                    c_name = parts[-1]
                    if t_name not in table_columns_map:
                        table_columns_map[t_name] = []
                    table_columns_map[t_name].append(c_name)

        telemetry.end_stage("schema_linking")
        telemetry.start_stage("profiling_and_generation")

        # Dynamic Profiling Probe (Reflective schema exploration before generation)
        profiling_insights = self.profiler.profile_columns(user_query, linked_schema.selected_columns, self.executor)
        if profiling_insights:
            logger.info("Injecting live profiling insights into SQL generation context...")
            lessons_context += f"\n\nDYNAMIC PROFILING INSIGHTS FROM DATA AUDIT:\n{profiling_insights}\n"

        # Retrieve Reference SQL for Convergence
        reference_context = self.sql_manager.get_reference_context(instance_id)
        
        # Module 3: Initial SQL Generation (with Dynamic Rules and Best SQL Anchor)
        lessons_context = self._safeguard_lessons(lessons_context)
        generation_result = self.sql_generator.generate(user_query, linked_schema, lessons=f"{lessons_context}\n{reference_context}")
        
        if not generation_result or not generation_result.sql:
            logger.error(f"FATAL: SQL Generator failed to produce initial SQL for {instance_id}")
            return "ERROR: SQL Generation Failed"
            
        current_sql = generation_result.sql
        
        # Module 3.5: Knowledge Acquisition (Web Search if needed)
        unclear_terms = [m.user_term for m in (linked_schema.value_mappings or []) if not m.db_value]
        if unclear_terms:
            logger.info(f"Unclear terms detected: {unclear_terms}. Triggering Web Research...")
            limit = self.params['orchestrator']['research_term_limit']
            for term in unclear_terms[:limit]:
                external_info = self.knowledge_tool.search_term(term, context=f"Database: {self.db_name}")
                logger.info(f"Research Result for '{term}': {external_info[:200]}...")
                lessons_context += f"\nEXTERNAL KNOWLEDGE ACQUIRED:\n{external_info}\n"
                logger.info(f"WEB_KNOWLEDGE: {external_info}")
            
            logger.info("Re-generating SQL with acquired web knowledge...")
            lessons_context = self._safeguard_lessons(lessons_context)
            generation_result = self.sql_generator.generate(user_query, linked_schema, lessons=f"{lessons_context}\n{reference_context}")
            current_sql = generation_result.sql
        
        # Adversarial Planner-Critic Check
        critic_lessons = f"{lessons_context}\n{reference_context}"
        critic_schema_context = self.semantic_engine.format_for_prompt(
            relevant_tables=linked_schema.selected_tables,
            include_samples=False
        )
        critic_res = self.critic.critique_sql(user_query, current_sql, critic_schema_context, critic_lessons, self.executor.dialect, relevant_tables=linked_schema.selected_tables, table_columns=table_columns_map)
        if not critic_res.is_valid:
            logger.warning(f"[ADVERSARIAL CRITIC REJECTION] {critic_res.criticism}")
            logger.info(f"Critic proposed fix recipe: {critic_res.proposed_fix}")
            
            critic_feedback = f"\n\n[ADVERSARIAL CRITIC FEEDBACK]: Your previous SQL design was rejected with criticism:\n{critic_res.criticism}\nProposed Fix Recipe:\n{critic_res.proposed_fix}\nYou MUST rewrite the SQL to resolve these criticisms!"
            lessons_context = self._safeguard_lessons(lessons_context + critic_feedback)
            generation_result = self.sql_generator.generate(user_query, linked_schema, lessons=f"{lessons_context}\n{reference_context}")
            current_sql = generation_result.sql

        # Pre-flight Schema Verification
        is_valid, schema_err = self.stabilizer.verify_schema_reference(current_sql, self.semantic_engine)
        if not is_valid:
            logger.warning(f"[SCHEMA HALLUCINATION] {schema_err}")
            error_context = f"SCHEMA ERROR: {schema_err}"
            attempts = 0
        
        telemetry.end_stage("profiling_and_generation")
        telemetry.start_stage("execution_and_audit")

        # Module 4: Execution & Self-Correction Loop
        attempts = 0
        success = False
        row_count = 0
        last_correction_thought = ""
        while attempts <= self.max_retries:
            logger.info(f"Execution Attempt {attempts + 1}/{self.max_retries + 1}")
            
            lessons_context = self._get_base_lessons(intent, external_knowledge)

            if 'error_context' in locals() and error_context and attempts == 0:
                success = False
                logger.info(f"Skipping execution due to pre-flight error: {error_context}")
            else:
                sql_hash = self.stabilizer.get_sql_hash(current_sql)
                if sql_hash in self.stabilizer.retry_history:
                    logger.warning(f"[RETRY MEMORY] Semantically identical SQL. Forcing pivot.")
                    table_to_probe = linked_schema.selected_tables[0] if linked_schema.selected_tables else "dual"
                    evidence = self.stabilizer.get_sample_evidence(table_to_probe, instance_id)
                    error_context = f"REPETITION ERROR: Do not repeat previous SQL. Evidence from {table_to_probe}:\n{evidence}"
                    success = False
                else:
                    self.stabilizer.retry_history.add(sql_hash)
                    success, result_msg, row_count = self.executor.execute(current_sql, instance_id)
            
            if success:
                diag_info = ""
                if row_count == 0:
                    logger.warning("Query returned 0 rows. Invoking Data IQ for discovery/probing.")
                    diag_info = self.stabilizer.diagnose_filter_collapse(current_sql, instance_id)
                    logger.info(f"[EMPTY RESULT DIAGNOSTIC] {diag_info}")
                else:
                    logger.success(f"Query returned {row_count} rows. Invoking Data IQ for quality audit.")

                csv_path = os.path.join(str(RESULTS_DIR), self.db_name, f"{instance_id}.csv")
                preview_str = "No preview available (0 rows)."
                stats = {"total_rows": 0, "total_columns": 0}
                
                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path)
                        if not df.empty:
                            preview_str = self._safe_markdown_preview(df)
                        
                        placeholders = self.params['data_iq']['placeholders']
                        placeholder_counts = {}
                        if not df.empty:
                            for p in placeholders:
                                c = int((df.astype(str).map(lambda x: x.strip() if isinstance(x, str) else x) == p).sum().sum())
                                if c > 0: placeholder_counts[f"count_of_{p}"] = c

                        column_profiles = {}
                        data_iq_alerts = []
                        total_rows = len(df)
                        
                        if not df.empty:
                            for col in df.columns:
                                s = df[col]
                                nunique = int(s.nunique(dropna=False))
                                is_num = pd.api.types.is_numeric_dtype(s)
                                
                                col_info = {
                                    "distinct_values": nunique,
                                    "null_count": int(s.isnull().sum())
                                }
                                
                                if is_num:
                                    col_info["min"] = float(s.min()) if not s.empty and not s.isnull().all() else 0
                                    col_info["max"] = float(s.max()) if not s.empty and not s.isnull().all() else 0
                                    col_info["mean"] = float(s.mean()) if not s.empty and not s.isnull().all() else 0
                                    std_val = s.std()
                                    col_info["std"] = float(std_val) if pd.notnull(std_val) else 0.0
                                    
                                    # Check for all-zero column
                                    if total_rows > 1 and (s.dropna() == 0).all():
                                        data_iq_alerts.append(f"ALERT: Column '{col}' contains ONLY numeric zero (0.0) across all {total_rows} rows!")
                                else:
                                    col_info["sample_values"] = s.dropna().astype(str).head(3).tolist()
                                    
                                # Check for zero variance
                                if total_rows > 5 and nunique == 1:
                                    val_str = str(s.iloc[0]) if not s.empty else "NULL"
                                    data_iq_alerts.append(f"ALERT: Column '{col}' has ZERO VARIANCE! Every single row across all {total_rows} rows has the identical value: '{val_str}'")
                                    
                                column_profiles[col] = col_info

                        stats = {
                            "total_rows": total_rows,
                            "total_columns": len(df.columns),
                            "column_names": df.columns.tolist(),
                            "column_profiles": column_profiles,
                            "duplicate_rows": int(df.duplicated().sum()) if not df.empty else 0,
                            "placeholder_counts": placeholder_counts,
                            "data_iq_alerts": data_iq_alerts
                        }
                    except Exception as e:
                        logger.warning(f"Failed to generate stats for Data IQ: {e}")
                
                is_zero_row = row_count == 0
                validation_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=linked_schema.selected_tables,
                    include_samples=is_zero_row
                )
                
                validation = self.validator.validate_result(user_query, current_sql, preview_str, schema_context=validation_context, stats=stats, dialect=self.executor.dialect, lessons=lessons_context, empty_result_diagnostic=diag_info, relevant_tables=linked_schema.selected_tables, table_columns=table_columns_map)
                
                if validation.exploration_sql:
                    logger.info(f"Data IQ requesting exploration probe: {validation.exploration_sql}")
                    probe_success, probe_msg, probe_rows = self.executor.execute(validation.exploration_sql, f"{instance_id}_probe")
                    probe_data = f"Probe failed: {probe_msg}"
                    if probe_success:
                        probe_path = os.path.join(str(RESULTS_DIR), self.db_name, f"{instance_id}_probe.csv")
                        try:
                            probe_df = pd.read_csv(probe_path)
                            probe_data = self._safe_markdown_preview(probe_df)
                        except: probe_data = "Probe returned no readable data."
                    else:
                        lessons_context = self._get_base_lessons(intent, external_knowledge)
                    
                    logger.info(f"Probe Result:\n{probe_data}")
                    validation = self.validator.validate_result(user_query, current_sql, preview_str, schema_context=validation_context, stats=stats, exploration_results=probe_data, dialect=self.executor.dialect, lessons=lessons_context, empty_result_diagnostic=diag_info, relevant_tables=linked_schema.selected_tables, table_columns=table_columns_map)

                logger.log_parsed_data("Data IQ Audit Reasoning", validation.audit_reasoning)
                
                if validation.is_valid or attempts == self.max_retries:
                    self.sql_manager.cache_success(instance_id, current_sql, validation.audit_reasoning)

                    logger.info(f"RESULT PREVIEW:\n{preview_str}")
                    total_time = time.time() - start_time
                    telemetry.end_stage("execution_and_audit")
                    telemetry.log_summary()
                    logger.log_final_results(sql=current_sql, row_count=row_count, latency=f"{total_time:.2f}s")
                    return current_sql
                else:
                    error_context = f"DATA QUALITY FAIL: {validation.feedback}"
                    logger.warning(f"Data IQ Check Failed! {validation.feedback}")
            else:
                logger.error(f"Execution failed: {result_msg}")
                logger.info("Bypassing Data IQ audit due to execution error.")
                
                missing_obj_match = re.search(r"(?:Object|Table|View)\s+'?([a-zA-Z0-9_\.]+)'?\s+(?:does not exist|not found)", result_msg, re.IGNORECASE)
                discovery_feedback = ""
                if missing_obj_match:
                    missing_obj = missing_obj_match.group(1).split('.')[-1]
                    logger.info(f"Detected missing table/object reference: '{missing_obj}'. Running dynamic cross-database table discovery...")
                    discovered = self.semantic_engine.discover_and_load_table(missing_obj)
                    if discovered:
                        fqns = ", ".join(f"'{t.name}'" for t in discovered)
                        discovery_feedback = f"\n[CROSS-DATABASE DISCOVERY] The table '{missing_obj}' was not found in the active database. However, we dynamically discovered and loaded the matching authoritative cross-database table(s): {fqns}. You MUST modify the SQL query to join/query from {fqns} instead of the missing '{missing_obj}'!"
                
                failed_table = None
                patterns = self.dialect_loader.get_error_patterns(self.executor.dialect)
                pattern = r"invalid identifier '\"?([A-Z0-9_]+)\"?\.\"?([A-Z0-9_]+)\"?'"
                if isinstance(patterns, dict):
                    pattern = patterns.get('invalid_identifier', pattern)
                
                table_match = re.search(pattern, result_msg, re.IGNORECASE)
                if table_match:
                    alias = table_match.group(1).upper()
                    join_pattern = rf'(?:FROM|JOIN)\s+((?:\"[^\"]+\"\.)*(?:\"[^\"]+\"|[A-Z0-9_]+))\s+(?:AS\s+)?\"?{alias}\"?\b'
                    alias_map = re.findall(join_pattern, current_sql, re.IGNORECASE)
                    if alias_map:
                        raw = alias_map[0].replace('"', '')
                        failed_table = raw.split('.')[-1]
                
                valid_table = None
                if failed_table:
                    for t_fqn in linked_schema.selected_tables:
                        if t_fqn.upper().endswith(f".{failed_table.upper()}") or t_fqn.upper() == failed_table.upper():
                            valid_table = t_fqn
                            break
                if not valid_table and linked_schema.selected_tables:
                    valid_table = linked_schema.selected_tables[0]
                
                table_to_probe = valid_table if valid_table else "dual"
                evidence = self.stabilizer.get_sample_evidence(table_to_probe, instance_id)
                error_context = f"EXECUTION ERROR: {result_msg}{discovery_feedback}\nEVIDENCE from {table_to_probe}:\n{evidence}"

            if attempts < self.max_retries:
                logger.info("Generating corrected SQL...")
                lessons_context = self._get_base_lessons(intent, external_knowledge)
                is_zero_row = (success and row_count == 0) or ("DATA QUALITY FAIL" in error_context)
                
                unpruned_tables = linked_schema.selected_tables
                if "invalid identifier" in error_context.lower() or "does not exist" in error_context.lower() or "unknown table" in error_context.lower() or attempts >= 1:
                    logger.info("Dynamic Schema Unpruning: Expanding schema context to full database view for recovery discovery.")
                    all_db_tables = [t.name for t in self.semantic_engine.context.tables] if self.semantic_engine.context else []
                    if len(all_db_tables) > 40:
                        logger.warning("Database schema exceeds 40 tables. Restricting unpruned recovery context to top 40 tables.")
                        unpruned_tables = all_db_tables[:40]
                    else:
                        unpruned_tables = None
                
                correction_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=unpruned_tables,
                    include_samples=is_zero_row
                )
                lessons_context = self._safeguard_lessons(lessons_context)
                correction = self.corrector.correct_sql(
                    user_query=user_query,
                    failed_sql=current_sql,
                    error_message=error_context,
                    linked_schema=linked_schema,
                    schema_context=correction_context,
                    lessons=lessons_context,
                    relevant_tables=unpruned_tables,
                    table_columns=table_columns_map if unpruned_tables == linked_schema.selected_tables else None
                )
                current_sql = correction.sql
                last_correction_thought = correction.thought_process
            attempts += 1

        best_sql = self.sql_manager.get_best_sql(instance_id)
        if best_sql and best_sql != current_sql:
            logger.warning(f"FALLBACK: Max retries exceeded. Reverting to cached best_sql for {instance_id}")
            fb_success, fb_msg, fb_row_count = self.executor.execute(best_sql, instance_id)
            if fb_success:
                logger.success(f"FALLBACK SUCCESS: Restored best_sql result ({fb_row_count} rows)")
                total_time = time.time() - start_time
                telemetry.end_stage("execution_and_audit")
                telemetry.log_summary()
                logger.log_final_results(sql=best_sql, row_count=fb_row_count, latency=f"{total_time:.2f}s (FALLBACK)")
                return best_sql

        total_time = time.time() - start_time
        telemetry.end_stage("execution_and_audit")
        telemetry.log_summary()
        logger.log_final_results(sql=current_sql, row_count=row_count if success else 0, error=error_context if 'error_context' in locals() else "Max retries exceeded", latency=f"{total_time:.2f}s")
        return current_sql

    def _safeguard_lessons(self, lessons_context: str) -> str:
        if len(lessons_context) > 6000:
            logger.info("Token Safeguard: Condensing context by keeping only the most recent core lessons.")
            return lessons_context[:2000] + "\n\n... [TRUNCATED FOR TOKEN CONVERGENCE] ...\n\n" + lessons_context[-3500:]
        return lessons_context

if __name__ == "__main__":
    print("Semantic DIN-SQL Orchestrator. Use run_batch.py or run_random_eval.py to execute queries.")
