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
import pandas as pd
import os
import time
import re
import yaml
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
        self.corrector = ExecutionCorrector(self.llm, dialect)
        self.validator = ResultValidator(self.llm)
        self.sql_manager = SQLManager()
        self.knowledge_tool = WebKnowledgeService()
        self.dialect_loader = DialectLoader()
        
        # Load System Parameters
        params_path = CONFIG_DIR / "system_params.yaml"
        with open(params_path, 'r', encoding='utf-8') as f:
            self.params = yaml.safe_load(f)
            
        self.max_retries = self.params['orchestrator'].get('max_retries', max_retries)
        
        # Build context immediately
        self.semantic_engine.build_context()

    def execute_query(self, user_query: str, instance_id: str = "test_instance") -> str:
        start_time = time.time()
        logger.log_section(f"Processing Query", color=logger.BLUE)
        logger.info(f"Query: '{user_query}'")
        
        # Module 1: Schema Linking (Adaptive Pruning based on Token Density)
        lessons_context = self.dialect_loader.load_dialect_reasoning(self.executor.dialect)
        
        # Estimate full schema size to decide on pruning
        full_schema_str = self.semantic_engine.format_for_prompt()
        h = self.params['orchestrator']['token_heuristic']
        estimated_tokens = len(full_schema_str) // h
        threshold = self.params['orchestrator']['pruning_threshold_tokens']
        
        logger.info(f"Schema density evaluated (~{estimated_tokens} tokens vs threshold {threshold}).")
        linked_schema = self.schema_linker.link_schema(user_query, dialect=self.executor.dialect, lessons=lessons_context, force_full=(estimated_tokens <= threshold))
        
        # Retrieve Reference SQL for Convergence
        reference_context = self.sql_manager.get_reference_context(instance_id)
        
        # Module 3: Initial SQL Generation (with Dynamic Rules and Best SQL Anchor)
        generation_result = self.sql_generator.generate(user_query, linked_schema, lessons=f"{lessons_context}\n{reference_context}")
        
        if not generation_result or not generation_result.sql:
            logger.error(f"FATAL: SQL Generator failed to produce initial SQL for {instance_id}")
            return "ERROR: SQL Generation Failed"
            
        current_sql = generation_result.sql
        
        # Module 3.5: Knowledge Acquisition (Web Search if needed)
        # If the linker identified unclear terms, fetch them now
        unclear_terms = [m.user_term for m in (linked_schema.value_mappings or []) if not m.db_value]
        if unclear_terms:
            logger.info(f"Unclear terms detected: {unclear_terms}. Triggering Web Research...")
            limit = self.params['orchestrator']['research_term_limit']
            for term in unclear_terms[:limit]:
                external_info = self.knowledge_tool.search_term(term, context=f"Database: {self.db_name}")
                logger.info(f"Research Result for '{term}': {external_info[:200]}...")
                # Inject this knowledge into the context for THIS run
                lessons_context += f"\nEXTERNAL KNOWLEDGE ACQUIRED:\n{external_info}\n"
                # Web knowledge acquired
                logger.info(f"WEB_KNOWLEDGE: {external_info}")
            
            # Since we got new knowledge, re-run generation with the new context!
            logger.info("Re-generating SQL with acquired web knowledge...")
            generation_result = self.sql_generator.generate(user_query, linked_schema, lessons=f"{lessons_context}\n{reference_context}")
            current_sql = generation_result.sql
        

        
        # Pre-flight Schema Verification (Catch hallucinations before execution)
        is_valid, schema_err = self.stabilizer.verify_schema_reference(current_sql, self.semantic_engine.context)
        if not is_valid:
            logger.warning(f"[SCHEMA HALLUCINATION] {schema_err}")
            error_context = f"SCHEMA ERROR: {schema_err}"
            # Force a correction before the first execution attempt
            attempts = 0 # Ensure we run the loop but skip first execution
        
        # Module 4: Execution & Self-Correction Loop
        attempts = 0
        success = False
        row_count = 0
        last_correction_thought = ""
        while attempts <= self.max_retries:
            logger.info(f"Execution Attempt {attempts + 1}/{self.max_retries + 1}")
            
            # RE-FETCH lessons every attempt
            lessons_context = self.dialect_loader.load_dialect_reasoning(self.executor.dialect)

            # Check if we already have an error (e.g. from pre-flight or repetition)
            if 'error_context' in locals() and error_context and attempts == 0:
                success = False
                logger.info(f"Skipping execution due to pre-flight error: {error_context}")
            else:
                # Check for semantic loops
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
                    # Trigger filter diagnostics for empty results
                    diag_info = self.stabilizer.diagnose_filter_collapse(current_sql, instance_id)
                    logger.info(f"[EMPTY RESULT DIAGNOSTIC] {diag_info}")
                else:
                    logger.success(f"Query returned {row_count} rows. Invoking Data IQ for quality audit.")

                # Module 5: Data IQ Layer (Audit only on successful execution)
                csv_path = os.path.join(str(RESULTS_DIR), self.db_name, f"{instance_id}.csv")
                preview_str = "No preview available (0 rows)."
                stats = {"total_rows": 0, "total_columns": 0}
                
                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path)
                        if not df.empty:
                            preview_str = df.head(10).to_markdown(index=False)
                        
                        # Compute statistics (Safe for empty DFs)
                        placeholders = self.params['data_iq']['placeholders']
                        placeholder_counts = {}
                        if not df.empty:
                            for p in placeholders:
                                c = int((df.astype(str).map(lambda x: x.strip() if isinstance(x, str) else x) == p).sum().sum())
                                if c > 0: placeholder_counts[f"count_of_{p}"] = c

                        # Basic Numeric EDA
                        numeric_stats = {}
                        for col in df.select_dtypes(include=['number']).columns:
                            numeric_stats[col] = {
                                "min": float(df[col].min()) if not df[col].empty else 0,
                                "max": float(df[col].max()) if not df[col].empty else 0,
                                "mean": float(df[col].mean()) if not df[col].empty else 0
                            }

                        stats = {
                            "total_rows": len(df),
                            "total_columns": len(df.columns),
                            "column_names": df.columns.tolist(),
                            "numeric_distribution": numeric_stats,
                            "duplicate_rows": int(df.duplicated().sum()) if not df.empty else 0,
                            "null_counts": df.isnull().sum().to_dict(),
                            "placeholder_counts": placeholder_counts,
                        }
                    except Exception as e:
                        logger.warning(f"Failed to generate stats for Data IQ: {e}")
                
                # Use pruned context for validator too
                is_zero_row = row_count == 0
                validation_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=linked_schema.selected_tables,
                    include_samples=is_zero_row
                )
                
                validation = self.validator.validate_result(user_query, current_sql, preview_str, schema_context=validation_context, stats=stats, dialect=self.executor.dialect, lessons=lessons_context, empty_result_diagnostic=diag_info)
                
                # Active Exploration Loop: If the auditor wants to probe the DB
                if validation.exploration_sql:
                    logger.info(f"Data IQ requesting exploration probe: {validation.exploration_sql}")
                    probe_success, probe_msg, probe_rows = self.executor.execute(validation.exploration_sql, f"{instance_id}_probe")
                    probe_data = f"Probe failed: {probe_msg}"
                    if probe_success:
                        probe_path = os.path.join(str(RESULTS_DIR), self.db_name, f"{instance_id}_probe.csv")
                        try:
                            probe_df = pd.read_csv(probe_path)
                            probe_data = probe_df.head(10).to_markdown(index=False)
                        except: probe_data = "Probe returned no readable data."
                    else:
                        # Re-fetch context
                        lessons_context = self.dialect_loader.load_dialect_reasoning(self.executor.dialect)
                    
                    logger.info(f"Probe Result:\n{probe_data}")
                    # Re-validate with probe data
                    validation = self.validator.validate_result(user_query, current_sql, preview_str, schema_context=validation_context, stats=stats, exploration_results=probe_data, dialect=self.executor.dialect, lessons=lessons_context, empty_result_diagnostic=diag_info)

                # Log the reasoning so we know WHY it passed/failed
                logger.log_parsed_data("Data IQ Audit Reasoning", validation.audit_reasoning)
                
                if validation.is_valid or attempts == self.max_retries:
                    # Distill the "Best SQL" pattern and CACHE it for future convergence
                    self.sql_manager.cache_success(instance_id, current_sql, validation.audit_reasoning)

                    logger.info(f"RESULT PREVIEW:\n{preview_str}")
                    total_time = time.time() - start_time
                    logger.log_final_results(sql=current_sql, row_count=row_count, latency=f"{total_time:.2f}s")
                    return current_sql
                else:
                    error_context = f"DATA QUALITY FAIL: {validation.feedback}"
                    logger.warning(f"Data IQ Check Failed! {validation.feedback}")
            else:
                # Direct Execution Error (e.g. Snowflake syntax error)
                logger.error(f"Execution failed: {result_msg}")
                logger.info("Bypassing Data IQ audit due to execution error.")
                
                # Forensic Probe: Get evidence for failure
                failed_table = None
                # Match alias.column in error: e.g., "invalid identifier 'P.PUBLICATION_NUMBER'"
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
                error_context = f"EXECUTION ERROR: {result_msg}\nEVIDENCE from {table_to_probe}:\n{evidence}"

            # Always increment attempts and call corrector if not finished
            if attempts < self.max_retries:
                logger.info("Generating corrected SQL...")
                # RE-FETCH lessons before correction
                lessons_context = self.dialect_loader.load_dialect_reasoning(self.executor.dialect)
                is_zero_row = (success and row_count == 0) or ("DATA QUALITY FAIL" in error_context)
                
                # Dynamic Schema Unpruning & Expansion on Recovery
                unpruned_tables = linked_schema.selected_tables
                if "invalid identifier" in error_context.lower() or "does not exist" in error_context.lower() or "unknown table" in error_context.lower() or attempts >= 1:
                    logger.info("Dynamic Schema Unpruning: Expanding schema context to full database view for recovery discovery.")
                    all_db_tables = [t.name for t in self.semantic_engine.context.tables] if self.semantic_engine.context else []
                    if len(all_db_tables) > 40:
                        logger.warning("Database schema exceeds 40 tables. Restricting unpruned recovery context to top 40 tables to prevent 131K Bedrock token overflow.")
                        unpruned_tables = all_db_tables[:40]
                    else:
                        unpruned_tables = None
                
                correction_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=unpruned_tables,
                    include_samples=is_zero_row
                )
                correction = self.corrector.correct_sql(
                    user_query=user_query,
                    failed_sql=current_sql,
                    error_message=error_context,
                    linked_schema=linked_schema,
                    schema_context=correction_context,
                    lessons=lessons_context
                )
                current_sql = correction.sql
                last_correction_thought = correction.thought_process
            attempts += 1
                


        # Fallback Mechanism: If all retries fail, check for a previously successful SQL
        best_sql = self.sql_manager.get_best_sql(instance_id)
        if best_sql and best_sql != current_sql:
            logger.warning(f"FALLBACK: Max retries exceeded. Reverting to cached best_sql for {instance_id}")
            # Execute one last time to save the results of the best SQL
            fb_success, fb_msg, fb_row_count = self.executor.execute(best_sql, instance_id)
            if fb_success:
                logger.success(f"FALLBACK SUCCESS: Restored best_sql result ({fb_row_count} rows)")
                total_time = time.time() - start_time
                logger.log_final_results(sql=best_sql, row_count=fb_row_count, latency=f"{total_time:.2f}s (FALLBACK)")
                return best_sql

        total_time = time.time() - start_time
        logger.log_final_results(sql=current_sql, row_count=row_count if success else 0, error=error_context if 'error_context' in locals() else "Max retries exceeded", latency=f"{total_time:.2f}s")
        return current_sql

if __name__ == "__main__":
    print("Semantic DIN-SQL Orchestrator. Use run_batch.py or run_random_eval.py to execute queries.")
