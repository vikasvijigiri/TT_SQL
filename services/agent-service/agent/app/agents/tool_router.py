import json
from typing import Literal, List, Optional
from pydantic import BaseModel, Field
from agent.services.llm import LLMClient
from agent.services.logger import logger

class ToolRouteAction(BaseModel):
    action: Literal["WEB_SEARCH", "DB_PROBE", "REJECT", "IGNORE"] = Field(
        description="The action to take for the missing concept or term."
    )
    target_term: str = Field(
        description="The specific search query or database term to probe."
    )
    reasoning: str = Field(
        description="Explanation for why this tool was selected."
    )

class ToolRouteResponse(BaseModel):
    routes: List[ToolRouteAction] = Field(description="The list of tool routing actions to resolve the gaps.")

class ToolRouterAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def route_gaps(self, user_query: str, gap_summary: str, unclear_terms: List[str]) -> ToolRouteResponse:
        logger.set_agent("TOOL_ROUTER")
        logger.info("Analyzing gaps and unclear terms for intelligent tool routing...")
        
        system_prompt = """You are the Intelligent Tool Router for a Text-to-SQL Agentic Pipeline.
Your job is to analyze schema gaps (missing data) or unclear terms, and decide how the orchestrator should resolve them.

You have three tools available:
1. WEB_SEARCH: Use this for domain knowledge gaps, external mapping (e.g. mapping stock tickers to real world countries), or understanding business terminology not present in the schema.
2. DB_PROBE: Use this when the user's term is likely a messy string variation or misspelling of a value that exists in the database.
3. REJECT: Use this for unresolvable structural database flaws (e.g. the user asks for a completely missing table like 'users' and it cannot be solved via web search).
4. IGNORE: Use this if the term doesn't need resolving.

Respond with a JSON object containing a list of `routes`. Each route must contain `action`, `target_term`, and `reasoning`."""

        user_prompt = f"User Query: {user_query}\n\n"
        if gap_summary:
            user_prompt += f"Identified Schema Gaps:\n{gap_summary}\n\n"
        if unclear_terms:
            user_prompt += f"Unclear Terms detected in query:\n{json.dumps(unclear_terms)}\n\n"
            
        user_prompt += "Determine the best action for each gap and unclear term to help the SQL Generator succeed."

        try:
            result = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=ToolRouteResponse,
            )
            for r in result.routes:
                logger.info(f"[RouteDecision] {r.action} -> '{r.target_term}' | Reasoning: {r.reasoning}")
            return result
        except Exception as e:
            logger.error(f"ToolRouter failed: {e}")
            return ToolRouteResponse(routes=[])
        finally:
            logger.reset_agent()
