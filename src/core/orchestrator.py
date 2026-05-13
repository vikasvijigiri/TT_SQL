from src.utils.logger import logger
from src.utils.llm import LLMClient
from src.indexing.semantic_engine import SemanticContextEngine
from src.mapping.schema_linker import SchemaLinker
from src.intent.classifier import QueryClassifier
from src.sql.generator import AdaptiveSQLGenerator
from src.feedback.corrector import ExecutionCorrector
from src.execution.executor import DatabaseExecutor

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
        self.executor = DatabaseExecutor(db_name=db_name, dialect=dialect)
        
        # Build context immediately
        self.semantic_engine.build_context()

    def execute_query(self, user_query: str, instance_id: str = "test_instance") -> str:
        logger.log_section(f"Processing Query", color=logger.BLUE)
        logger.info(f"Query: '{user_query}'")
        
        # Module 1: Schema Linking
        linked_schema = self.schema_linker.link_schema(user_query)
        
        # Module 2: Classification
        classification = self.classifier.classify(user_query, linked_schema)
        
        # Module 3: Initial SQL Generation
        generation_result = self.sql_generator.generate(user_query, linked_schema, classification)
        current_sql = generation_result.sql
        
        # Module 4: Execution & Self-Correction Loop
        attempts = 0
        while attempts <= self.max_retries:
            logger.info(f"Execution Attempt {attempts + 1}/{self.max_retries + 1}")
            success, result_msg, row_count = self.executor.execute(current_sql, instance_id)
            
            if success and (row_count > 0 or attempts == self.max_retries):
                logger.log_final_results(sql=current_sql, row_count=row_count)
                return current_sql
            else:
                error_context = result_msg
                if success and row_count == 0:
                    error_context = "Query executed successfully but returned 0 rows. A logic error, case-sensitivity issue (use ILIKE), or NULL filtering (use COALESCE) is likely dropping all rows. Please relax or fix the WHERE conditions."
                    logger.warning("Query returned 0 rows. Routing to Self-Corrector...")
                else:
                    logger.warning(f"Execution failed: {result_msg}")

                if attempts < self.max_retries:
                    logger.info("Generating corrected SQL...")
                    correction = self.corrector.correct_sql(
                        user_query=user_query,
                        failed_sql=current_sql,
                        error_message=error_context,
                        linked_schema=linked_schema
                    )
                    current_sql = correction.sql
                attempts += 1
                
        # If we exhausted retries
        logger.log_final_results(sql=current_sql, row_count=0, error="Max correction attempts exceeded.")
        return current_sql

if __name__ == "__main__":
    print("Semantic DIN-SQL Orchestrator. Use run_batch.py or run_random_eval.py to execute queries.")
