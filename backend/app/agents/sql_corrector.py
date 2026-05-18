import sqlglot
import re
from typing import List, Dict, Optional
from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.utils.dialect_loader import DialectLoader
from backend.app.core.dialects.rule_retriever import DialectRuleRetriever
from backend.app.core.retrieval.hierarchical_retriever import HierarchicalRetriever
from backend.app.models.schemas import SelfCorrectorOutput, SchemaLinkerOutput
from backend.app.utils.logger import logger

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("self_corrector.yaml")


class ExecutionCorrector:
    def __init__(self, llm_client: LLMClient, semantic_engine, dialect: str = "snowflake"):
        self.llm = llm_client
        self.semantic_engine = semantic_engine
        self.dialect = dialect.lower()
        self.dialect_loader = DialectLoader()

    def _validate_syntax(self, sql: str) -> bool:
        try:
            sqlglot.parse_one(sql, read=self.dialect)
            return True
        except Exception as e:
            logger.warning(f"SQLGlot syntax validation failed on corrected SQL: {e}")
            return False

    def _format_value_mappings(self, linked_schema: SchemaLinkerOutput) -> str:
        if not linked_schema.value_mappings:
            return "None"
        lines = []
        for m in linked_schema.value_mappings:
            lines.append(f"  - User said '{m.user_term}' -> use '{m.db_value}' in column {m.column}")
        return "\n".join(lines)

    def correct_sql(
        self,
        user_query: str,
        failed_sql: str,
        error_message: str,
        linked_schema: SchemaLinkerOutput,
        schema_context: str = "",
        lessons: str = "",
        relevant_tables: Optional[List[str]] = None,
        table_columns: Optional[Dict[str, List[str]]] = None
    ) -> SelfCorrectorOutput:
        logger.set_agent("SELF_CORRECTOR")
        logger.info("Executing Self-Correction Module")

        intent = HierarchicalRetriever().analyze_intent(user_query)
        val_mappings_str = f"VALUE MAPPINGS FROM SCHEMA LINKER:\n{self._format_value_mappings(linked_schema)}"
        combined_lessons = f"FAILED SQL:\n```sql\n{failed_sql}\n```\n\nERROR CONTEXT:\n{error_message}\n\n{val_mappings_str}\n\n{lessons}"

        if table_columns is None:
            table_columns = {}
            if linked_schema and linked_schema.selected_columns:
                for fqn in linked_schema.selected_columns:
                    if "." in fqn:
                        parts = fqn.split(".")
                        t_name = ".".join(parts[:-1])
                        c_name = parts[-1]
                        if t_name not in table_columns:
                            table_columns[t_name] = []
                        table_columns[t_name].append(c_name)

        if relevant_tables is None:
            relevant_tables = linked_schema.selected_tables if linked_schema else None

        from backend.app.core.prompts.prompt_assembler import PromptAssembler
        assembler = PromptAssembler(dialect=self.dialect, stage="SELF_CORRECTOR")
        assembled = assembler.assemble(
            user_query=user_query,
            agent_type="SELF_CORRECTOR",
            context=self.semantic_engine.context,
            intent=intent,
            relevant_tables=relevant_tables,
            table_columns=table_columns,
            lessons=combined_lessons,
            error_history=error_message
        )

        system_prompt = assembled.system_prompt
        user_prompt   = assembled.user_prompt

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=SelfCorrectorOutput,
            )
            # Apply Dialect Sanitizers (Generic)
            for sanitizer in self.dialect_loader.get_sanitizers(self.dialect):
                search = sanitizer.get("search")
                replace = sanitizer.get("replace")
                if search:
                    result.sql = re.sub(re.escape(search), replace, result.sql, flags=re.IGNORECASE)
            self._validate_syntax(result.sql)
            logger.log_parsed_data("Correction Output", result)
            return result
        except Exception:
            logger.error("Self-correction failed.")
            raise
        finally:
            logger.reset_agent()
