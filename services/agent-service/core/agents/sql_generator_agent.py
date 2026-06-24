import typing

import sqlglot

import re

from typing import List

from core.utils.llm import LLMClient

from core.utils.dialect_loader import DialectLoader

from core.retrieval.hierarchical_retriever import HierarchicalRetriever

from core.contracts.schemas import SQLGeneratorOutput, SchemaLinkerOutput

from core.retrieval.semantic_engine import SemanticContextEngine

from core.blackboard.dynamic_rules import FailureMemory

from core.validators.deterministic_validators import DeterministicValidators



from config.config import get_prompt_path



PROMPT_PATH = get_prompt_path("sql_generator.yaml")



# Structural approach directives for diverse candidate generation.

# Each directive forces a genuinely different SQL shape so the critic can pick the best grain.

_DIVERSITY_APPROACHES = [

    (

        "Use named CTEs -- one CTE per logical step, each named after what it computes. "

        "This is the baseline approach."

    ),

    (

        "HARD CONSTRAINT: ABSOLUTELY NO CTEs (no WITH clause at all). "

        "Write a single SELECT using only inline subqueries in FROM or WHERE. "

        "If your SQL starts with WITH or contains 'AS (SELECT', you have violated this directive."

    ),

    (

        "Start from the final output row: decide exactly what one output row represents, "

        "then write window functions (ROW_NUMBER, RANK, or DENSE_RANK) to derive it directly. "

        "Use QUALIFY or a wrapping SELECT with a WHERE on the window result. No CTEs."

    ),

]





class SQLGeneratorAgent:

    def __init__(

        self,

        llm_client: LLMClient,

        semantic_engine: SemanticContextEngine,

        dialect: str = "snowflake",

    ):

        self.llm = llm_client

        self.semantic_engine = semantic_engine

        self.dialect = dialect.lower()

        self.dialect_loader = DialectLoader()



    def _validate_syntax(self, sql: str, strategy: str = "SQL_ONLY") -> bool:

        if strategy == "RETRIEVAL_ONLY" or not sql.strip():

            return True

        try:

            sqlglot.parse_one(sql, read=self.dialect)

            return True

        except Exception as e:

            logger.warning(f"SQLGlot syntax validation failed: {e}")

            return False



    def _format_value_mappings(self, linked_schema: SchemaLinkerOutput) -> str:

        if not linked_schema.value_mappings:

            return "None"

        lines = []

        for m in linked_schema.value_mappings:

            lines.append(

                f"  - User said '{m.user_term}' -> use '{m.db_value}' in column {m.column}"

            )

        return "\n".join(lines)



    def _build_table_columns_map(self, linked_schema: SchemaLinkerOutput) -> dict:

        """Pre-compute {table_fqn: [col_name, ...]} from schema linker output."""

        table_columns_map: dict[str, typing.Any] = {}

        for fqn in linked_schema.selected_columns:

            if "." in fqn:

                parts = fqn.split(".")

                table_name = ".".join(parts[:-1])

                col_name = parts[-1]

                if table_name not in table_columns_map:

                    table_columns_map[table_name] = []

                table_columns_map[table_name].append(col_name)

        return table_columns_map



    def _build_prompt(

        self,

        user_query: str,

        linked_schema: SchemaLinkerOutput,

        combined_lessons: str,

        intent,

        table_columns_map: dict,

    ):

        """Assemble the system + user prompt for SQL generation."""

        from core.prompts.engine.prompt_assembler import PromptAssembler



        assembler = PromptAssembler(dialect=self.dialect, stage="SQL_GENERATOR")

        assembled = assembler.assemble(

            user_query=user_query,

            agent_type="SQL_GENERATOR",

            context=self.semantic_engine.context,

            intent=intent,

            relevant_tables=linked_schema.selected_tables,

            table_columns=table_columns_map,

            lessons=combined_lessons,

        )

        return assembled.system_prompt, assembled.user_prompt



    def _call_llm_and_sanitize(

        self, system_prompt: str, user_prompt: str

    ) -> SQLGeneratorOutput:

        """Call LLM and apply dialect-specific post-processing sanitizers."""

        result = self.llm.generate_structured(

            system_prompt=system_prompt,

            user_prompt=user_prompt,

            response_model=SQLGeneratorOutput,

        )

        

        # Enforce planning decision constraints

        if result.sql_vs_retrieval_decision == "RETRIEVAL_ONLY":

            result.sql = ""

            

        for sanitizer in self.dialect_loader.get_sanitizers(self.dialect):

            search = sanitizer.get("search")

            replace = sanitizer.get("replace")

            if search and result.sql:

                result.sql = re.sub(

                    re.escape(search), replace, result.sql, flags=re.IGNORECASE

                )

        return result



    # ------------------------------------------------------------------

    # Public API

    # ------------------------------------------------------------------



    def generate(

        self,

        user_query: str,

        linked_schema: SchemaLinkerOutput,

        lessons: str = "",

        intent=None,

    ) -> SQLGeneratorOutput:

        """Single-attempt SQL generation (backward-compatible)."""

        logger.set_agent("SQL_GENERATOR")

        if intent is None:

            intent = HierarchicalRetriever().analyze_intent(user_query)

            

        from core.blackboard.run_blackboard import get_blackboard

        bb = get_blackboard()

        blackboard_context = ""

        if bb.temporary_rules or bb.failed_sql_strategies or bb.execution_errors:

            blackboard_context = (

                f"- DYNAMIC BLACKBOARD KNOWLEDGE ---\n"

                f"Temporary Rules to Follow: {[r['rule'] for r in bb.temporary_rules]}\n"

                f"Failed SQL Strategies to Avoid (DO NOT REPEAT THESE):\n"

                + "\n".join([f"  - {s}" for s in bb.failed_sql_strategies]) + "\n"

                f"Recent Failures to Fix: {[e['root_cause'] for e in bb.execution_errors]}\n"

                f"----------------------------------\n\n"

            )



        val_mappings_str = f"VALUE MAPPINGS FROM SCHEMA LINKER:\n{self._format_value_mappings(linked_schema)}"

        combined_lessons = (

            f"{blackboard_context}{val_mappings_str}\n\n{lessons}" if lessons else f"{blackboard_context}{val_mappings_str}"

        )

        table_columns_map = self._build_table_columns_map(linked_schema)

        system_prompt, user_prompt = self._build_prompt(

            user_query, linked_schema, combined_lessons, intent, table_columns_map

        )

        try:

            result = self._call_llm_and_sanitize(system_prompt, user_prompt)

            

            # Deterministic Syntax Validation Gate

            val_result = DeterministicValidators.validate_sql_syntax(result.sql, self.dialect)

            if not val_result.is_valid and result.sql_vs_retrieval_decision != "RETRIEVAL_ONLY":

                FailureMemory.record_failure(

                    failure_type="Validation Rejection (SQL Syntax)",

                    root_cause=val_result.rejection_reason or "Unknown",

                    impact="SQL cannot be executed.",

                    prevention_rule=f"Fix the syntax error: {val_result.rejection_reason}"

                )

                raise ValueError(f"SQL Syntax validation failed: {val_result.rejection_reason}")



            logger.log_parsed_data("Generation Output", result)

            return result

        except Exception:

            logger.error("SQL generation failed.")

            raise

        finally:

            logger.reset_agent()



    def generate_diverse(

        self,

        user_query: str,

        linked_schema: SchemaLinkerOutput,

        lessons: str = "",

        intent=None,

        n: int = 3,

    ) -> List[SQLGeneratorOutput]:

        """

        Generate N structurally diverse SQL candidates concurrently by providing a

        different structural approach directive to each LLM call. Duplicate SQL strings

        are filtered.

        """

        logger.set_agent("SQL_GENERATOR")

        if intent is None:

            intent = HierarchicalRetriever().analyze_intent(user_query)

        val_mappings_str = f"VALUE MAPPINGS FROM SCHEMA LINKER:\n{self._format_value_mappings(linked_schema)}"

        base_lessons = (

            f"{val_mappings_str}\n\n{lessons}" if lessons else val_mappings_str

        )

        table_columns_map = self._build_table_columns_map(linked_schema)



        import concurrent.futures

        from core.utils.llm import reset_token_counters, get_tokens, add_tokens



        # Task runner for threads

        def _gen_candidate_task(i, approach):

            reset_token_counters()

            directive_header = (

                f"=== MANDATORY STRUCTURAL DIRECTIVE (candidate {i + 1}/{n}) ===\n"

                f"{approach}\n"

                f"You MUST follow this directive. Violating it produces a useless duplicate.\n"

                f"=== END DIRECTIVE ===\n\n"

            )

            try:

                system_prompt, user_prompt = self._build_prompt(

                    user_query,

                    linked_schema,

                    base_lessons,

                    intent,

                    table_columns_map,

                )

                user_prompt = directive_header + user_prompt

                result = self._call_llm_and_sanitize(system_prompt, user_prompt)

                in_t, out_t = get_tokens()

                return result, in_t, out_t, i

            except Exception as e:

                logger.warning(

                    f"[SQLGenerator] Candidate {i + 1} generation failed: {e}"

                )

                return None



        candidates_by_index: list[tuple[SQLGeneratorOutput, int]] = []

        seen_sql: set = set()



        try:

            with concurrent.futures.ThreadPoolExecutor(max_workers=n) as executor:

                futures = [

                    executor.submit(_gen_candidate_task, i, approach)

                    for i, approach in enumerate(_DIVERSITY_APPROACHES[:n])

                ]

                for future in concurrent.futures.as_completed(futures):

                    res = future.result()

                    if res:

                        result, in_t, out_t, index = res

                        add_tokens(in_t, out_t)  # Add tokens back to parent thread

                        if result and result.sql:

                            norm = " ".join(result.sql.split()).upper()

                            if norm not in seen_sql:

                                seen_sql.add(norm)

                                candidates_by_index.append((result, index))



            # Re-sort to preserve original priority order

            candidates_by_index.sort(key=lambda x: x[1])

            candidates = [c for c, idx in candidates_by_index]



            if not candidates:

                logger.warning(

                    "[SQLGenerator] All diverse attempts failed - falling back to standard generate()."

                )

                logger.reset_agent()

                fallback = self.generate(

                    user_query, linked_schema, lessons=lessons, intent=intent

                )

                return [fallback] if fallback else []



            logger.info(

                f"[SQLGenerator] Diverse generation complete: {len(candidates)} unique candidates."

            )

            return candidates

        finally:

            logger.reset_agent()

