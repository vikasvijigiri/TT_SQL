from typing import Dict, Any, List
from decimal import Decimal
from app.schemas.agent_state import AgentState

class AnalysisFormatter:
    """Standardizes raw agent state into structured response payloads."""
    
    @staticmethod
    def format_final_result(state: AgentState) -> Dict[str, Any]:
        """Maps AgentState to a frontend-friendly dictionary."""
        results = []
        columns = state.execution_result.columns if state.execution_result else []
        
        if state.execution_result and state.execution_result.rows:
            # Format rows (Decimal/Date serialization handling)
            for row in state.execution_result.rows[:100]:
                json_row = {}
                for col, val in zip(columns, row):
                    if hasattr(val, 'isoformat'):
                        json_row[col] = val.isoformat()
                    elif isinstance(val, Decimal):
                        json_row[col] = float(val)
                    else:
                        json_row[col] = val
                results.append(json_row)

        return {
            "instance_id": state.instance_id,
            "sql": state.chosen_query,
            "results": results,
            "columns": columns,
            "total_count": state.execution_result.row_count if state.execution_result else 0,
            "logs": state.logs,
            "critic_feedback": state.critic_feedback,
            "business_summary": state.business_summary,
            "chart_config": state.chart_config,
            "token_usage": state.token_usage,
            "total_time": state.total_duration
        }
