from typing import Dict
from backend.app.core.query_analysis.capability_detector import QueryCapabilityProfile
from backend.app.utils.logger import logger

class AdaptiveBudgetManager:
    """
    Enterprise Adaptive Token Budgeting Engine.
    Dynamically scales token ceilings and section allocations based on query complexity
    and detected capability profiles.
    """

    BASE_STAGE_BUDGETS = {
        "SCHEMA_LINKER": 12000,
        "SQL_GENERATOR": 15000,
        "SELF_CORRECTOR": 14000,
        "DATA_IQ": 12000,
        "CRITIC": 10000,
        "DEFAULT": 15000
    }

    @classmethod
    def calculate_budget(
        cls,
        stage: str,
        query: str,
        profile: QueryCapabilityProfile
    ) -> Dict[str, int]:
        base_cap = cls.BASE_STAGE_BUDGETS.get(stage.upper(), cls.BASE_STAGE_BUDGETS["DEFAULT"])

        # Determine scaling factor
        scaling = 1.0
        if profile.requires_variants:
            scaling += 0.25 # Prioritize variant rules
        if profile.requires_windows and profile.requires_joins:
            scaling += 0.15
        if len(query.split()) > 25:
            scaling += 0.10

        hard_cap = int(base_cap * min(1.5, scaling))

        # Allocations within budget
        allocations = {
            "total_ceiling": hard_cap,
            "rules_ceiling": int(hard_cap * 0.15) if profile.requires_variants else int(hard_cap * 0.10),
            "schema_ceiling": int(hard_cap * 0.50),
            "templates_ceiling": int(hard_cap * 0.10),
            "lessons_ceiling": int(hard_cap * 0.15)
        }

        logger.debug(f"[AdaptiveBudgetManager][{stage}] Calculated dynamic budget: {allocations}")
        return allocations
