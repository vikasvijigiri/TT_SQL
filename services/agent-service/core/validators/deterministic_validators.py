"""
V4 Validation Engine

Contains lightweight deterministic validators that enforce the typed contracts.
If deterministic validation fails, the rejection is handled immediately without LLM calls.
"""
from typing import Optional, Any
from core.contracts.schemas import (
    QuestionValidatorOutput, PlanValidatorOutput, SchemaValidatorOutput,
    JoinValidatorOutput, SQLValidatorOutput, ExecutionValidatorOutput,
    ResultValidatorOutput, EvidenceValidatorOutput, AnswerabilityValidatorOutput
)
from core.utils.logger import logger
import sqlglot

class DeterministicValidators:
    """Lightweight Python-based validations to save LLM tokens where possible."""

    @staticmethod
    def validate_question(analysis: Any) -> QuestionValidatorOutput:
        if analysis.confidence < 0.2:
            return QuestionValidatorOutput(is_valid=False, rejection_reason="Confidence too low to proceed.")
        if not analysis.question_type:
            return QuestionValidatorOutput(is_valid=False, rejection_reason="Question type classification missing.")
        return QuestionValidatorOutput(is_valid=True)

    @staticmethod
    def validate_plan(plan: Any) -> PlanValidatorOutput:
        if not plan.goal:
            return PlanValidatorOutput(is_valid=False, rejection_reason="Semantic plan missing a concrete goal.")
        return PlanValidatorOutput(is_valid=True)

    @staticmethod
    def validate_schema(schema_linker_output: Any) -> SchemaValidatorOutput:
        score = getattr(schema_linker_output, "coverage_score", 1.0)
        selected = [c.lower() for c in schema_linker_output.selected_columns]
        
        if score < 0.8:
            return SchemaValidatorOutput(
                is_valid=False, 
                rejection_reason=f"Coverage score {score} is below threshold.", 
                coverage_score=score
            )
            
        only_ids = all("id" in c.split(".")[-1] or "key" in c.split(".")[-1] for c in selected)
        if only_ids and selected:
            return SchemaValidatorOutput(
                is_valid=False, 
                rejection_reason="Schema Validation Failed: ONLY ID columns selected.", 
                coverage_score=score
            )
            
        return SchemaValidatorOutput(is_valid=True, coverage_score=score)

    @staticmethod
    def validate_join_plan(join_plan: Any, required_tables: list) -> JoinValidatorOutput:
        """Heuristically check if the join graph leaves tables disconnected."""
        connected_tables = set(t.lower() for t in join_plan.tables_in_graph)
        req_tables = set(t.lower() for t in required_tables)
        
        missing = req_tables - connected_tables
        if missing:
            return JoinValidatorOutput(
                is_valid=False, 
                rejection_reason=f"Disconnected Join Graph: Missing {missing} in join plan."
            )
            
        if len(connected_tables) > 1 and not join_plan.joins:
            return JoinValidatorOutput(
                is_valid=False,
                rejection_reason="Cartesian Risk: Multiple tables selected but 0 joins provided."
            )
            
        return JoinValidatorOutput(is_valid=True)

    @staticmethod
    def validate_sql_syntax(sql: str, dialect: str = "snowflake") -> SQLValidatorOutput:
        """Syntax-only check. Semantic check happens via SQL_CRITIC."""
        if not sql.strip():
            return SQLValidatorOutput(is_valid=False, rejection_reason="SQL string is empty.")
        try:
            sqlglot.parse_one(sql, read=dialect)
            return SQLValidatorOutput(is_valid=True)
        except Exception as e:
            return SQLValidatorOutput(is_valid=False, rejection_reason=f"SQL Syntax Error: {e}")

    @staticmethod
    def validate_execution_safety(sql: str) -> ExecutionValidatorOutput:
        """Basic heuristic check for dangerous queries (e.g., unqualified deletes)."""
        upper_sql = sql.upper()
        if "DELETE FROM" in upper_sql and "WHERE" not in upper_sql:
            return ExecutionValidatorOutput(is_valid=False, rejection_reason="Unqualified DELETE detected.", estimated_cost=9999.0)
        if "DROP TABLE" in upper_sql:
            return ExecutionValidatorOutput(is_valid=False, rejection_reason="DROP TABLE detected.", estimated_cost=9999.0)
            
        return ExecutionValidatorOutput(is_valid=True, estimated_cost=10.0)

    @staticmethod
    def validate_results(rows: list) -> ResultValidatorOutput:
        if len(rows) > 10000:
            return ResultValidatorOutput(is_valid=False, rejection_reason="Result explosion: over 10,000 rows returned. Probable cartesian product.")
        return ResultValidatorOutput(is_valid=True)

    @staticmethod
    def validate_answerability(confidence: float) -> AnswerabilityValidatorOutput:
        if confidence < 0.6:
            return AnswerabilityValidatorOutput(is_valid=False, rejection_reason=f"Answerability confidence {confidence} is too low. Need more evidence.")
        return AnswerabilityValidatorOutput(is_valid=True)
