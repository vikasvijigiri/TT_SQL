from backend.app.utils.llm import LLMClient
from backend.app.utils.prompt_loader import PromptLoader
from backend.app.models.schemas import QueryClassifierOutput, SchemaLinkerOutput
from backend.app.utils.logger import logger

from backend.app.core.config import get_prompt_path
PROMPT_PATH = get_prompt_path("query_classifier.yaml")


class QueryClassifier:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def classify(self, user_query: str, linked_schema: SchemaLinkerOutput) -> QueryClassifierOutput:
        logger.set_agent("CLASSIFIER")
        logger.info("Classifying query complexity...")

        messages = PromptLoader.load(PROMPT_PATH, variables={
            "USER_QUERY":       user_query,
            "REQUIRED_TABLES":  ", ".join(linked_schema.selected_tables),
            "REQUIRED_COLUMNS": ", ".join(linked_schema.selected_columns),
        })

        system_prompt = next(m["content"] for m in messages if m["role"] == "system")
        user_prompt   = next(m["content"] for m in messages if m["role"] == "user")

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=QueryClassifierOutput,
            )
            logger.log_parsed_data("Classification", result)
            return result
        except Exception:
            logger.error("Query classification failed.")
            raise
        finally:
            logger.reset_agent()
