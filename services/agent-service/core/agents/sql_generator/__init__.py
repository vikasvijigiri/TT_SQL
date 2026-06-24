"""
SQL_GENERATOR -- Agent Package
Generates dialect-correct SQL using Blackboard context and schema mappings.
"""
from core.agents.sql_generator.agent import SQLGeneratorAgent
from core.agents.sql_generator.contract import SQLGeneratorOutput

__all__ = ["SQLGeneratorAgent", "SQLGeneratorOutput"]
