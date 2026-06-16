import re
from typing import List, Optional
from pydantic import BaseModel, Field
from agent.app.utils.llm import LLMClient
from agent.app.utils.logger import logger

# Patterns that strongly signal a multi-hop / multi-aggregation question requiring
# query decomposition into sequential CTE steps.
_COMPLEX_PATTERNS = [
    re.compile(r"\b(for each|per|by each)\b", re.IGNORECASE),
    re.compile(r"\b(rank|ranking|top \d+|bottom \d+|nth|first \d+)\b", re.IGNORECASE),
    re.compile(
        r"\b(compared to|vs\.?|versus|relative to|ratio of|proportion of)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(cumulative|running total|running sum|rolling|year.over.year|month.over.month)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(then|after that|next|subsequently|following that)\b", re.IGNORECASE
    ),
    re.compile(
        r"\b(who (has|have|had) (the most|the highest|the lowest|more than|fewer than))\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(group.+by.+and.+also)\b", re.IGNORECASE),
    re.compile(r"\b(percentage|percent|share) of (total|all|overall)\b", re.IGNORECASE),
    re.compile(r"\b(having|where).+\b(and|or)\b.+(having|where)\b", re.IGNORECASE),
    re.compile(r"\b(pivot|cross.tab|matrix)\b", re.IGNORECASE),
]

# Patterns that strongly signal a simple query Ã¢â‚¬â€ skip decomposition even if some
# complex patterns also match (e.g. "How many orders per customer" is simple).
_SIMPLE_PATTERNS = [
    re.compile(r"^(how many|count|list|show|find|get|what is the)\b", re.IGNORECASE),
    re.compile(r"^(select|give me)\b", re.IGNORECASE),
]

_SIMPLE_WORD_LIMIT = 12  # queries under this word count are treated as simple


class CTEStep(BaseModel):
    cte_name: str = Field(..., description="Name for this CTE, e.g. 'filtered_orders'")
    purpose: str = Field(
        ..., description="One sentence describing what this CTE computes"
    )
    depends_on: List[str] = Field(
        default_factory=list, description="Names of CTEs this step depends on"
    )


class DecompositionPlan(BaseModel):
    is_complex: bool = Field(
        ..., description="True if the question requires multi-step decomposition"
    )
    reasoning: str = Field(
        ..., description="One sentence explaining why decomposition is or is not needed"
    )
    steps: List[CTEStep] = Field(
        default_factory=list, description="Ordered CTE steps; empty if is_complex=False"
    )


_DECOMPOSER_SYSTEM = """## Role
SQL query planner. Decide whether a question needs CTE decomposition and if so, produce the step plan.

## Rules
| Rule | Detail |
|---|---|
| Decompose only when needed | Multi-hop aggregations, rankings, self-joins Ã¢â‚¬â€ not simple filters or counts |
| Snake_case CTE names | Name after what each step computes: `monthly_revenue`, `ranked_users` |
| Explicit dependencies | `depends_on: ["step_name"]` for every step that uses a prior step |
| 2Ã¢â‚¬â€œ5 steps max | Never over-engineer. `is_complex=false` Ã¢â€ â€™ `steps=[]` |

## Output Ã¢â‚¬â€ valid JSON only, no markdown"""

_DECOMPOSER_USER_TEMPLATE = """**Question:** {query}

**Available tables:** {table_names}

Return decomposition plan. Simple questions Ã¢â€ â€™ `is_complex: false, steps: []`."""


class QueryDecomposerAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    @staticmethod
    def _is_complex_question(query: str) -> bool:
        """
        Heuristic pre-filter: returns True only when the query exhibits clear multi-hop
        analytical patterns.  Runs in microseconds Ã¢â‚¬â€ no LLM call.

        Simple queries bypass the decomposer entirely, saving one full LLM round-trip
        per pipeline execution.
        """
        words = query.split()
        if len(words) <= _SIMPLE_WORD_LIMIT:
            return False
        if any(p.search(query) for p in _SIMPLE_PATTERNS) and len(words) < 20:
            return False
        return any(p.search(query) for p in _COMPLEX_PATTERNS)

    def decompose(
        self, query: str, selected_tables: List[str]
    ) -> Optional[DecompositionPlan]:
        """
        Analyse the question and return a CTE decomposition plan if the question is complex.

        Returns None (not an empty plan) when the heuristic short-circuits Ã¢â‚¬â€ callers should
        treat None as "proceed with standard single-pass generation."
        """
        if not self._is_complex_question(query):
            logger.debug(
                "[QueryDecomposer] Query classified as simple Ã¢â‚¬â€ skipping decomposition."
            )
            return None

        logger.set_agent("DECOMPOSER")
        try:
            table_names_str = (
                ", ".join(selected_tables) if selected_tables else "(none yet)"
            )
            user_prompt = _DECOMPOSER_USER_TEMPLATE.format(
                query=query,
                table_names=table_names_str,
            )
            plan: DecompositionPlan = self.llm.generate_structured(
                system_prompt=_DECOMPOSER_SYSTEM,
                user_prompt=user_prompt,
                response_model=DecompositionPlan,
            )
            if plan and plan.is_complex and plan.steps:
                logger.info(
                    f"[QueryDecomposer] Decomposed into {len(plan.steps)} CTE steps."
                )
            else:
                logger.info(
                    "[QueryDecomposer] LLM confirmed query is simple Ã¢â‚¬â€ no decomposition."
                )
            return plan
        except Exception as e:
            logger.warning(
                f"[QueryDecomposer] Decomposition failed ({e}) Ã¢â‚¬â€ proceeding without plan."
            )
            return None
        finally:
            logger.reset_agent()

    @staticmethod
    def format_plan_for_prompt(plan: Optional[DecompositionPlan]) -> str:
        """
        Format a decomposition plan as a concise injection block for the SQL generator prompt.
        Returns an empty string when there is nothing to inject.
        """
        if not plan or not plan.is_complex or not plan.steps:
            return ""

        lines = [
            "[QUERY DECOMPOSITION BLUEPRINT Ã¢â‚¬â€ implement each step as a named CTE]:"
        ]
        for i, step in enumerate(plan.steps, 1):
            dep_str = (
                f" (uses: {', '.join(step.depends_on)})" if step.depends_on else ""
            )
            lines.append(f"  Step {i}: {step.cte_name}{dep_str}")
            lines.append(f"    Ã¢â€ â€™ {step.purpose}")
        lines.append("  Final SELECT: combine the above CTEs to produce the answer.")
        return "\n".join(lines)
