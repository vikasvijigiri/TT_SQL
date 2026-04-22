import pytest
from agents.planner import ContextEnrichmentAgent, StepByStepPlannerAgent
from agents.selector import TableSelectorAgent
from agents.builder import SQLBuilderAgent

def test_agent_initialization(mock_llm):
    """Verify that agents can be initialized without errors."""
    enricher = ContextEnrichmentAgent()
    planner = StepByStepPlannerAgent(mock_llm)
    selector = TableSelectorAgent(mock_llm)
    builder = SQLBuilderAgent(mock_llm)
    
    assert enricher.name == "ContextEnrichment"
    assert planner.name == "QueryPlanner"
    assert selector.name == "TableSelector"
    assert builder.name == "SQLBuilder"

def test_planner_agent_run(sample_state, mock_llm):
    """Verify basic run logic of StepByStepPlannerAgent with mock LLM."""
    planner = StepByStepPlannerAgent(mock_llm)
    updated_state = planner.run(sample_state)
    
    # Mock returns SELECT 1 as sql which we put in step_by_step_plan for fail case 
    # but here StepByStepPlanner expects step_by_step_approach key
    assert len(updated_state.step_by_step_plan) > 0
