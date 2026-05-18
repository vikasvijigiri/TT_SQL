from typing import List, Dict, Any, Tuple, Optional
from backend.app.core.pipeline_config import PipelineModeConfig, BALANCED_CONFIG
from backend.app.core.prompts.prompt_sections import PromptSection
from backend.app.utils.logger import logger

class TokenBudgetManager:
    """
    Enterprise token budgeting engine. Enforces strict stage-specific token ceilings
    by estimating section token consumption and dynamically trimming or dropping lower-priority
    sections (verbose examples -> metadata -> samples) before prompt compilation.
    """
    
    STAGE_BUDGETS = {
        "SCHEMA_LINKER": 12000,
        "COLUMN_PRUNER": 8000,
        "TABLE_PRUNER": 10000,
        "SQL_GENERATOR": 16000,
        "SELF_CORRECTOR": 14000,
        "DATA_IQ": 12000,
        "CRITIC": 10000,
        "DEFAULT": 15000
    }

    def __init__(self, config: PipelineModeConfig = BALANCED_CONFIG, stage: str = "DEFAULT"):
        self.config = config
        self.stage = stage.upper()
        # Derive ceiling from stage budget or config fallback
        self.hard_cap = self.STAGE_BUDGETS.get(self.stage, self.STAGE_BUDGETS["DEFAULT"])

    def estimate_tokens(self, text: str) -> int:
        """Estimates token count (~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def rank_prompt_sections(self, sections: List[PromptSection]) -> List[PromptSection]:
        """
        Sorts sections by inclusion priority:
        Mandatory / non-droppable first, then by priority ascending (1=highest, 5=lowest),
        then by semantic value descending.
        """
        for sec in sections:
            sec.estimated_tokens = self.estimate_tokens(sec.content)
            
        return sorted(
            sections,
            key=lambda x: (0 if not x.droppable else 1, x.priority, -x.semantic_value)
        )

    def trim_to_budget(self, sections: List[PromptSection], max_budget: int = None) -> Tuple[List[PromptSection], List[str]]:
        """
        Iterates through ranked sections and keeps as many as fit under max_budget.
        Returns the retained sections (in original structural order) and a list of dropped section names.
        """
        cap = max_budget if max_budget is not None else self.hard_cap
        ranked = self.rank_prompt_sections(sections)
        
        total_tokens = 0
        included_names = set()
        dropped_names = []
        
        for sec in ranked:
            cost = sec.estimated_tokens
            if not sec.droppable:
                included_names.add(sec.name)
                total_tokens += cost
            elif total_tokens + cost <= cap:
                included_names.add(sec.name)
                total_tokens += cost
            else:
                dropped_names.append(sec.name)
                logger.warning(f"[TokenBudgeter][{self.stage}] Dropped section '{sec.name}' (Cost: {cost}, Prio: {sec.priority}) to respect {cap} token ceiling.")
                
        # Reconstruct in original input order to maintain proper reading flow
        retained = [s for s in sections if s.name in included_names]
        return retained, dropped_names

    def assemble_and_budget(self, sections: List[PromptSection]) -> Tuple[str, int, List[str]]:
        """Legacy compatibility wrapper for PromptAssembler."""
        retained, dropped = self.trim_to_budget(sections)
        final_text = "\n\n".join(s.content for s in retained).strip()
        final_tokens = self.estimate_tokens(final_text)
        return final_text, final_tokens, dropped
