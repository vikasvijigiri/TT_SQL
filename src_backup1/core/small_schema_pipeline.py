import json
import asyncio
from typing import Dict, Any, List, Optional
from src.utils.logger import logger
from src.utils.llm import LLMService
from src.utils.schema_formatter import format_schema_to_str
from src.utils.data_iq import analyze_result
from src.utils.prompt_loader import PromptLoader
from src.validation.sql_validator import SQLValidator
import os

class SmallSchemaPipeline:
    """
    High-performance pipeline for small schemas using iterative loops.
    """
    def __init__(self, db_name: str, db_connector, llm: LLMService, schema_with_samples: Dict[str, Any], dialect: str = "snowflake"):
        self.db_name = db_name
        self.db = db_connector
        self.llm = llm
        self.dialect = dialect
        self.schema_with_samples = schema_with_samples
        self.compressed_schema = format_schema_to_str(schema_with_samples, mode="compressed")
        
        # Dialect specific instructions
        self.dialect_instructions = ""
        dialect_yaml = os.path.join("src", "prompts", "small_schema", f"{dialect}.yaml")
        if os.path.exists(dialect_yaml):
            try:
                msgs = PromptLoader.load(dialect_yaml, variables={})
                self.dialect_instructions = msgs[0]["content"] if msgs else ""
            except: pass
            
        self.sql_validator = SQLValidator(db_connector, db_name=self.db_name)

    async def run(self, question: str, intent: Dict[str, Any], external_knowledge: str = "") -> Dict[str, Any]:
        """Runs the small schema pipeline with Planning and SQL Generation loops."""
        logger.info("Running Small Schema Pipeline...")
        
        # 1. Planning Loop [Query Planner -> Query Critic]
        plan_data = await self._planning_loop(question, intent, external_knowledge=external_knowledge)
        intent["plan_data"] = plan_data
        
        # 2. Generation Loop [SQL Generator -> SQL Validator -> SQL Executor -> SQL Critic -> Data IQ]
        final_result = await self._generation_loop(question, intent, external_knowledge=external_knowledge)
        
        return final_result

    async def _planning_loop(self, question: str, intent: Dict[str, Any], external_knowledge: str = "") -> Dict[str, Any]:
        MAX_REFINEMENTS = 2
        current_plan_str = "None"
        feedback = "None"
        last_plan_data = {}
        
        planner_path = os.path.join("src", "prompts", "small_schema", "query_planner.yaml")
        critic_path = os.path.join("src", "prompts", "small_schema", "query_critic.yaml")

        for i in range(MAX_REFINEMENTS):
            logger.info(f"Planning Attempt {i+1}...")
            
            # 1a. Plan Generation
            vars = {
                "USER_QUERY": question,
                "INTENT": json.dumps(intent, indent=2),
                "DIALECT_INSTRUCTIONS": self.dialect_instructions,
                "SCHEMA": self.compressed_schema,
                "PREVIOUS_ACTION_PLAN": current_plan_str,
                "FEEDBACK_ON_PREVIOUS_ACTION_PLAN": feedback,
                "RESOLVED_ELEMENTS": "[]",
                "EXTERNAL_KNOWLEDGE": external_knowledge,
                "REFERENCE_DATE": "2024-05-06"
            }
            
            messages = PromptLoader.load(planner_path, variables=vars)
            plan_data = self.llm.get_json_completion(messages, agent_name="QueryPlanner")
            
            if not plan_data:
                logger.error("Planner failed to produce JSON.")
                continue
            
            if not isinstance(plan_data, dict):
                logger.error(f"Planner returned non-dict: {type(plan_data)}")
                continue
            
            last_plan_data = plan_data
            current_plan_str = json.dumps(plan_data.get("strategies", {}).get("primary", []), indent=2)
            
            # 1b. Query Critic
            critic_vars = {
                "USER_QUERY": question,
                "INTENT": json.dumps(intent, indent=2),
                "SCHEMA": self.compressed_schema,
                "ACTION_PLAN": current_plan_str,
                "PREVIOUS_ACTION_PLAN": "None",
                "EXTERNAL_KNOWLEDGE": external_knowledge,
                "REFERENCE_DATE": "2024-05-06"
            }
            critic_msgs = PromptLoader.load(critic_path, variables=critic_vars)
            critic_res = self.llm.get_json_completion(critic_msgs, agent_name="QueryCritic")
            
            if critic_res and critic_res.get("is_valid"):
                logger.info("Plan approved by critic.")
                break
            else:
                feedback = critic_res.get("feedback", "Improve logic.") if critic_res else "Invalid JSON output."
                logger.warning(f"Plan rejected: {feedback}")
                
        return last_plan_data

    async def _generation_loop(self, question: str, intent: Dict[str, Any], external_knowledge: str = "") -> Dict[str, Any]:
        MAX_ATTEMPTS = 3
        feedback = "None"
        previous_sql = "None"
        
        gen_path = os.path.join("src", "prompts", "small_schema", "sql_builder.yaml")
        critic_path = os.path.join("src", "prompts", "small_schema", "sql_critic.yaml")

        for i in range(MAX_ATTEMPTS):
            logger.info(f"Generation Attempt {i+1}...")
            
            # 2a. SQL Generation
            gen_vars = {
                "USER_QUERY": question,
                "INTENT": json.dumps(intent, indent=2),
                "SCHEMA": self.compressed_schema,
                "STRATEGIES": json.dumps(intent.get("plan_data", {}).get("strategies", {}).get("primary", []), indent=2),
                "PREVIOUS_SQL": previous_sql,
                "FEEDBACK": feedback,
                "DIALECT_INSTRUCTIONS": self.dialect_instructions,
                "DIALECT_CONSTRAINTS": "None",
                "FAILURE_HISTORY": "None",
                "VARIANT_SOURCES": "None",
                "REQUIRED_ACTIONS": "None",
                "REFERENCE_DATE": "2024-05-06",
                "EXTERNAL_KNOWLEDGE": external_knowledge
            }
            
            messages = PromptLoader.load(gen_path, variables=gen_vars)
            gen_res = self.llm.get_json_completion(messages, agent_name="SQLGenerator")
            sql = gen_res.get("sql") if gen_res else None
            
            if not sql:
                logger.error("Failed to generate SQL.")
                continue
                
            # 2b. Execution & Validation (Shared Logic)
            sql = sql.strip().rstrip(";")
            validation = self.sql_validator.validate_and_execute(type('obj', (object,), {'sql': sql, 'dialect': self.dialect}), intent)
            
            # 2c. Data IQ
            iq_res = analyze_result(validation.rows)
            
            # 2d. SQL Critic
            audit_context = {
                "sql": validation.final_sql,
                "execution": {
                    "status": "success" if validation.is_valid else "error",
                    "error_message": validation.warnings[0] if validation.warnings else "None",
                    "row_count": validation.row_count_estimate
                },
                "dataiq": iq_res
            }
            critic_vars = {
                "USER_QUERY": question,
                "SCHEMA": self.compressed_schema,
                "DIALECT_INSTRUCTIONS": self.dialect_instructions,
                "DIALECT_CONSTRAINTS": "None",
                "STRATEGIES": json.dumps(intent.get("plan_data", {}).get("strategies", {}).get("primary", []), indent=2),
                "PREVIOUS_SQL": previous_sql,
                "AUDIT_CONTEXT": json.dumps(audit_context, indent=2),
                "REFERENCE_DATE": "2024-05-06",
                "EXTERNAL_KNOWLEDGE": external_knowledge
            }
            critic_msgs = PromptLoader.load(critic_path, variables=critic_vars)
            critic_res = self.llm.get_json_completion(critic_msgs, agent_name="SQLCritic")
            
            if critic_res and critic_res.get("is_valid") and validation.is_valid:
                logger.info("SQL approved.")
                return {
                    "sql": validation.final_sql,
                    "rows": validation.rows,
                    "row_count": validation.row_count_estimate,
                    "confidence": iq_res["confidence_score"],
                    "status": "success"
                }
            else:
                feedback = critic_res.get("feedback", "SQL has errors or poor results.") if critic_res else "Execution failed."
                previous_sql = sql
                logger.warning(f"SQL rejected: {feedback}")
                
        return {
            "status": "failed",
            "warnings": ["Failed to generate valid SQL after max attempts."]
        }
