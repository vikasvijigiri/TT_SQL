from typing import Optional, Any
from pydantic import BaseModel, Field

class PromptSection(BaseModel):
    """
    Modular representation of a prompt section for surgical token budgeting and dynamic assembly.
    """
    name: str = Field(description="Unique identifier for the section (e.g., 'dynamic_schema', 'dialect_rules').")
    content: str = Field(description="Raw text content of the section.")
    priority: int = Field(default=5, description="Priority rank: 1=highest (schema/joins/rules), 5=lowest (verbose examples/metadata).")
    estimated_tokens: int = Field(default=0, description="Estimated token count computed before assembly.")
    semantic_value: float = Field(default=1.0, description="Relevance score (0.0 to 1.0) derived from query context matching.")
    droppable: bool = Field(default=True, description="Whether this section can be trimmed or dropped if budget is exceeded.")
    is_mandatory: bool = Field(default=False, description="Legacy compatibility flag; if True, droppable is False.")

    def model_post_init(self, __context: Any) -> None:
        if self.is_mandatory:
            self.droppable = False
