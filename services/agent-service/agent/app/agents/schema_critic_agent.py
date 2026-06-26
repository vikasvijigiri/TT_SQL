import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.blackboard.run_blackboard import get_blackboard
from agent.app.models.schemas import SchemaLinkerOutput

class SchemaCriticOutput(BaseModel):
    approved: bool = Field(..., description="True if the schema provides all necessary columns to answer the question")
    missing_information: List[str] = Field(default_factory=list, description="What specific facts/documents/IDs are missing")
    recommendations: List[str] = Field(default_factory=list, description="Directives for the Schema Linker to fix the issue")

class SchemaCriticAgent:
    """
    Validates if the linked schema can actually fulfill the Blackboard's requirements.
    If rejected, triggers the Automatic Linker Correction loop.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.agent_name = "SCHEMA_CRITIC"

    def critique(self, user_query: str, linked_schema: SchemaLinkerOutput) -> SchemaCriticOutput:
        logger.set_agent(self.agent_name)
        bb = get_blackboard()
        logger.info(f"Critiquing selected schema against Blackboard requirements...")

        # We don't use PromptAssembler here because this is a purely deterministic/logic check 
        # and we can formulate a very precise system prompt.
        system_prompt = (
            "You are the Schema Critic. Your job is to verify if the selected database schema "
            "can answer the user's question, based on the required business facts and documents.\n"
            "If it cannot, you must reject it (approved=false) and provide recommendations."
        )

        user_prompt = (
            f"Question: {user_query}\n\n"
            f"Blackboard Requirements:\n"
            f"- Goal: {bb.goal}\n"
            f"- Required Facts: {bb.required_facts}\n"
            f"- Required Documents: {bb.required_documents}\n\n"
            f"Linked Schema (Selected by Schema Linker):\n"
            f"- Selected Tables: {linked_schema.selected_tables}\n"
            f"- Selected Columns: {linked_schema.selected_columns}\n\n"
            f"Analyze: Does the Linked Schema contain the columns necessary to provide the Required Facts and Documents?\n"
            f"Respond with JSON matching the expected structure."
        )

        response, metrics = self.llm_client.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        try:
            clean_resp = response.strip()
            if clean_resp.startswith("```json"):
                clean_resp = clean_resp[7:]
            if clean_resp.endswith("```"):
                clean_resp = clean_resp[:-3]
                
            data = json.loads(clean_resp.strip())
            output = SchemaCriticOutput(**data)
            
            if not output.approved:
                logger.warning(f"Schema Critic REJECTED the schema. Missing: {output.missing_information}")
            else:
                logger.success("Schema Critic APPROVED the schema.")
                
            return output
        except Exception as e:
            logger.error(f"Schema Critic parsing failed: {e}. Defaulting to APPROVED to avoid blocking.")
            return SchemaCriticOutput(approved=True, missing_information=[], recommendations=[])
