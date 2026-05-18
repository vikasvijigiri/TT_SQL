import logging
from typing import List, Optional, Dict
from backend.app.utils.llm import LLMClient
from backend.app.models.schemas import CriticOutput
from backend.app.utils.logger import logger

class SQLCritic:
    """
    Adversarial Critic Agent.
    Double-checks the Planner's proposed SQL query for semantic alignment, mixed-case quoting issues, 
    incorrect join conditions, and missing spatial/variant type conversions.
    """
    
    def __init__(self, llm_client: LLMClient, semantic_engine):
        self.llm = llm_client
        self.semantic_engine = semantic_engine

    def critique_sql(self, user_query: str, proposed_sql: str, schema_context: str, lessons: str, dialect: str = "snowflake", relevant_tables: Optional[List[str]] = None, table_columns: Optional[Dict[str, List[str]]] = None) -> CriticOutput:
        """
        Runs a structured, adversarial critique of the proposed SQL.
        If a flaw is found, outputs a detailed criticism and a proposed recipe fix.
        """
        logger.set_agent("CRITIC")
        logger.info("Executing adversarial Planner-Critic query audit...")
        
        from backend.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever
        intent = HierarchicalRetriever().analyze_intent(user_query)
        combined_lessons = f"PROPOSED SQL:\n```sql\n{proposed_sql}\n```\n\nPAST LESSONS:\n{lessons}"
        
        from backend.app.core.prompts.prompt_assembler import PromptAssembler
        assembler = PromptAssembler(dialect=dialect, stage="CRITIC")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="CRITIC",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            lessons=combined_lessons
        )

        system_prompt = assembled.system_prompt
        user_prompt   = assembled.user_prompt
        
        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=CriticOutput
            )
            
            logger.log_parsed_data("Critic Output", result)
            return result
            
        except Exception as e:
            # Safe Fallback: if Critic LLM call fails, let the query proceed to execution
            logger.warning(f"Critic audit failed to compile structured response: {e}. Bypassing audit to prevent bottleneck.")
            return CriticOutput(is_valid=True)
        finally:
            logger.reset_agent()
