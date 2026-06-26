import json
from pydantic import BaseModel, Field

from agent.services.llm import LLMClient
from agent.services.logger import logger
from agent.app.core.prompts.prompt_assembler import PromptAssembler
from agent.app.core.learning.sqlite_memory import SQLiteMemoryDB

class MetaLearnerOutput(BaseModel):
    new_permanent_rules: list[str] = Field(description="Rules that should be permanently added to the system prompts")
    prompt_improvements: dict[str, str] = Field(description="Suggested improvements keyed by agent name")
    identified_anti_patterns: list[str] = Field(description="Common pitfalls the system is repeatedly hitting")

class MetaLearnerAgent:
    """
    Executes periodically or at the end of a batch of queries.
    Analyzes the learning.db SQLite memory (successes, failures, SQL repairs)
    and generates long-term structural improvements.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.db = SQLiteMemoryDB()
        self.assembler = PromptAssembler(stage="META_LEARNER")
        self.agent_name = "META_LEARNER"

    def run_meta_learning_cycle(self) -> MetaLearnerOutput:
        logger.set_agent(self.agent_name)
        logger.info("Starting Meta-Learning Analysis Cycle...")
        
        # Pull recent failures
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT failure_type, root_cause, fix, prevention_rule FROM failure_patterns ORDER BY id DESC LIMIT 50")
            failures = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT question_pattern, successful_strategy FROM success_patterns ORDER BY id DESC LIMIT 50")
            successes = [dict(row) for row in cursor.fetchall()]

        if not failures and not successes:
            logger.info("Not enough data for meta-learning. Skipping.")
            return MetaLearnerOutput(new_permanent_rules=[], prompt_improvements={}, identified_anti_patterns=[])

        payload = {
            "recent_failures": failures,
            "recent_successes": successes
        }
        
        assembled = self.assembler.assemble(
            user_query="Run Meta-Learning Optimization",
            agent_type=self.agent_name,
            context=json.dumps(payload, indent=2),
            intent=None
        )

        response, _ = self.llm_client.generate(
            system_prompt=assembled.system_prompt,
            user_prompt=assembled.user_prompt
        )

        try:
            clean = response.strip()
            if clean.startswith("```json"): clean = clean[7:]
            if clean.endswith("```"): clean = clean[:-3]
            
            data = json.loads(clean.strip())
            output = MetaLearnerOutput(**data)
            
            logger.success(f"MetaLearner generated {len(output.new_permanent_rules)} new permanent rules.")
            return output
        except Exception as e:
            logger.error(f"Failed to parse MetaLearner output: {e}")
            return MetaLearnerOutput(new_permanent_rules=[], prompt_improvements={}, identified_anti_patterns=[])
