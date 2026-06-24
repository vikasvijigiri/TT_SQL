from typing import List, Tuple
from core.prompts.engine.prompt_ast import PromptAST
from core.tokenization.final_tokenizer import FinalTokenizer
from core.context.context_value_ranker import ContextValueRanker


class FinalBudgetEnforcer:
    """
    Enterprise Final Token Budget Enforcer.
    Trims prompt AST nodes after rendering based on Context Value Scoring
    (lowest value: lessons, examples -> highest value: schema, syntax rules)
    to enforce hard token ceilings without breaking critical context.
    """

    STAGE_BUDGETS = {
        "SCHEMA_LINKER":   15000,  # was 12000
        "COLUMN_PRUNER":   10000,  # was 8000
        "TABLE_PRUNER":    12000,  # was 10000
        "SQL_GENERATOR":   20000,  # was 16000
        "SELF_CORRECTOR":  18000,  # was 14000
        "DATA_IQ":         15000,  # was 12000
        "CRITIC":          13000,  # was 10000
        "DEFAULT":         18000,  # was 15000
    }

    @classmethod
    def enforce_budget(
        cls,
        ast: PromptAST,
        system_tokens: int,
        stage: str = "DEFAULT",
        custom_cap: int | None = None,
    ) -> Tuple[PromptAST, List[str]]:
        cap = (
            custom_cap
            if custom_cap is not None
            else cls.STAGE_BUDGETS.get(stage.upper(), cls.STAGE_BUDGETS["DEFAULT"])
        )

        # Calculate current total
        rendered_nodes = [(node, node.render()) for node in ast.root_nodes]
        user_tokens = sum(
            FinalTokenizer.count_user_tokens(rn[1]) for rn in rendered_nodes
        )
        total_tokens = system_tokens + user_tokens

        if total_tokens <= cap:
            return ast, []

        max_user_budget = max(1000, cap - system_tokens)
        retained_nodes, dropped_names = ContextValueRanker.rank_and_trim(
            ast.root_nodes,
            max_budget=max_user_budget,
            token_estimator=lambda x: FinalTokenizer.count_user_tokens(
                x if isinstance(x, str) else str(x)
            ),
        )

        trimmed_ast = PromptAST()
        for node in retained_nodes:
            trimmed_ast.add_node(node)

        return trimmed_ast, dropped_names
