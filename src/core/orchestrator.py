from src.utils.logger import logger
from src.utils.llm import LLMClient
from src.indexing.semantic_engine import SemanticContextEngine
from src.mapping.schema_linker import SchemaLinker
from src.intent.classifier import QueryClassifier
from src.sql.generator import AdaptiveSQLGenerator
from src.feedback.corrector import ExecutionCorrector
from src.execution.executor import DatabaseExecutor
from src.feedback.validator import ResultValidator
from src.feedback.memory import DynamicRuleLearner
import pandas as pd
import os

class SemanticDINOrchestrator:
    def __init__(self, db_directory: str, db_name: str, dialect: str = "snowflake", max_retries: int = 3):
        self.max_retries = max_retries
        
        logger.log_section("Initializing Semantic DIN-SQL Pipeline", color=logger.CYAN)
        
        self.llm = LLMClient()
        self.semantic_engine = SemanticContextEngine(db_directory=db_directory)
        self.schema_linker = SchemaLinker(self.llm, self.semantic_engine)
        self.classifier = QueryClassifier(self.llm)
        self.sql_generator = AdaptiveSQLGenerator(self.llm, self.semantic_engine, dialect)
        self.corrector = ExecutionCorrector(self.llm, dialect)
        self.validator = ResultValidator(self.llm)
        self.learner = DynamicRuleLearner(dialect=dialect)
        self.executor = DatabaseExecutor(db_name=db_name, dialect=dialect)
        self.db_name = db_name.upper()
        
        # Build context immediately
        self.semantic_engine.build_context()

    def execute_query(self, user_query: str, instance_id: str = "test_instance") -> str:
        logger.log_section(f"Processing Query", color=logger.BLUE)
        logger.info(f"Query: '{user_query}'")
        
        # Module 1: Schema Linking (with Dynamic Rules)
        lessons_context = self.learner.get_dynamic_context()
        linked_schema = self.schema_linker.link_schema(user_query, dialect=self.executor.dialect, lessons=lessons_context)
        
        # Module 2: Classification
        classification = self.classifier.classify(user_query, linked_schema)
        
        # Module 3: Initial SQL Generation (with Dynamic Rules)
        generation_result = self.sql_generator.generate(user_query, linked_schema, classification, lessons=lessons_context)
        current_sql = generation_result.sql
        
        # Module 4: Execution & Self-Correction Loop
        attempts = 0
        last_correction_thought = ""
        while attempts <= self.max_retries:
            logger.info(f"Execution Attempt {attempts + 1}/{self.max_retries + 1}")
            success, result_msg, row_count = self.executor.execute(current_sql, instance_id)
            
            if success and row_count > 0:
                # Module 5: Data IQ Layer (Validation)
                csv_path = os.path.join("results", self.db_name, f"{instance_id}.csv")
                preview_str = "No preview available."
                stats = {}
                if os.path.exists(csv_path):
                    try:
                        df = pd.read_csv(csv_path)
                        preview_str = df.head(5).to_string()
                        # Compute aggressive EDA stats for placeholder detection
                        placeholders = ["", " ", "\"\"", "\" \"", "\\", "''", "nan", "None", "NULL"]
                        placeholder_counts = {}
                        for p in placeholders:
                            count = int((df.astype(str).map(lambda x: x.strip() if isinstance(x, str) else x) == p).sum().sum())
                            if count > 0:
                                placeholder_counts[f"count_of_{p}"] = count

                        stats = {
                            "total_rows": len(df),
                            "total_cells": len(df) * len(df.columns),
                            "duplicate_rows": int(df.duplicated().sum()),
                            "null_counts": df.isnull().sum().to_dict(),
                            "placeholder_counts": placeholder_counts,
                            "total_empty_cells": sum(placeholder_counts.values()) + int(df.isnull().sum().sum())
                        }
                    except: pass
                
                validation = self.validator.validate_result(user_query, current_sql, preview_str, stats=stats)
                
                if validation.is_plausible or attempts == self.max_retries:
                    # If we succeeded via correction, analyze and learn
                    if attempts > 0:
                        self.learner.analyze_and_learn(
                            instance_id=instance_id,
                            error=error_context,
                            correction_thought=last_correction_thought,
                            attempts=attempts
                        )
                    logger.info(f"RESULT PREVIEW:\n{preview_str}")
                    logger.log_final_results(sql=current_sql, row_count=row_count)
                    return current_sql
                else:
                    error_context = f"DATA QUALITY FAIL: {validation.feedback}\nSuggestion: {validation.improvement_suggestion}"
                    logger.warning("Data IQ check failed. Re-routing to Self-Corrector...")
            else:
                error_context = result_msg
                if success and row_count == 0:
                    error_context = "Query executed successfully but returned 0 rows. A logic error, case-sensitivity issue (use ILIKE), or NULL filtering (use COALESCE) is likely dropping all rows. Please relax or fix the WHERE conditions."
                    logger.warning("Query returned 0 rows. Routing to Self-Corrector...")
                else:
                    logger.warning(f"Execution failed: {result_msg}")

            # Always increment attempts and call corrector if not finished
            if attempts < self.max_retries:
                logger.info("Generating corrected SQL...")
                is_zero_row = (success and row_count == 0) or ("DATA QUALITY FAIL" in error_context)
                correction_context = self.semantic_engine.format_for_prompt(
                    relevant_tables=linked_schema.selected_tables,
                    include_samples=is_zero_row
                )
                correction = self.corrector.correct_sql(
                    user_query=user_query,
                    failed_sql=current_sql,
                    error_message=error_context,
                    linked_schema=linked_schema,
                    schema_context=correction_context
                )
                current_sql = correction.sql
                last_correction_thought = correction.thought_process
            attempts += 1
                
        # If we exhausted retries, log as a major failure
        self.learner.analyze_and_learn(
            instance_id=instance_id,
            error="Max retries exceeded",
            correction_thought=last_correction_thought,
            attempts=attempts
        )
        logger.log_final_results(sql=current_sql, row_count=0, error="Max correction attempts exceeded.")
        return current_sql

if __name__ == "__main__":
    print("Semantic DIN-SQL Orchestrator. Use run_batch.py or run_random_eval.py to execute queries.")
