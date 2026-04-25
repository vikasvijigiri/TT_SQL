from core.agent_base import AgentState, BaseAgent
from core.llm_service import LLMService
from core.prompt_loader import PromptLoader
from core.logger import Logger

class GenericAgent(BaseAgent):
    """
    A unified, template-driven agent that can perform any task based on a prompt.
    """

    def __init__(self, step_id: str, prompt_name: str, output_key: str = None, state_field: str = None, llm_service: LLMService = None, max_tokens: int = None):
        super().__init__(name=step_id)
        self.prompt_name = prompt_name
        self.output_key = output_key # None means whole dictionary
        self.state_field = state_field
        self.llm = llm_service
        self.max_tokens = max_tokens
        self.prompt_loader = PromptLoader()

    def run(self, state: AgentState) -> AgentState:
        Logger.log_call(f"GenericAgent({self.name}).run", {"prompt": self.prompt_name})
        
        # Limit tool loops to prevent infinite cycles
        MAX_TOOL_LOOPS = 2
        current_loop = 0
        
        from core.tool_registry import ToolRegistry
        tools_map = ToolRegistry.get_tools_map()

        while current_loop < MAX_TOOL_LOOPS:
            # 1. Load prompt with automatic meta-variable injection
            messages = self.prompt_loader.load_prompt(self.prompt_name, state=state)
            
            # 2. Get JSON completion
            response = self.llm.get_json_completion(messages, state=state, agent_name=self.name, max_tokens=self.max_tokens)
            
            if not response or not isinstance(response, dict):
                self.log(state, "Critical: Received malformed or empty response.", level="ERROR")
                state.is_result_valid = False
                break

            # 3. Check for Tool Execution Request
            tool_name = response.get("tool")
            if tool_name and tool_name in tools_map:
                current_loop += 1
                params = response.get("params", {})
                self.log(state, f"Executing Tool: {tool_name} with params {params}")
                
                # Run the tool
                tool_func = tools_map[tool_name]
                try:
                    tool_result = tool_func(state) if not params else tool_func(state, params=params)
                    self.log(state, f"Tool Result: {tool_result}")
                    Logger.log_status_banner(f"Tool: {tool_name}", True)
                    # Exit loop after tool execution to avoid double-calling LLM for fixed orchestrators
                    break 
                except Exception as e:
                    self.log(state, f"Tool Execution Failed: {e}", level="ERROR")
                    Logger.log_status_banner(f"Tool: {tool_name}", False, str(e))
                    break
            
            # 4. Standard Response Mapping
            if self.state_field:
                val = response.get(self.output_key) if self.output_key else response
                
                if val is not None:
                    setattr(state, self.state_field, val)
                    
                    # Log success banner
                    Logger.log_status_banner(f"Agent: {self.name}", True, f"Produced: {self.state_field}")

                    # --- [SIDE EFFECTS]: Automatic Persistance ---
                    from core.utils import write_sql_to_file, write_plan_to_file
                    if self.state_field == "chosen_query":
                        sql_clean = str(val).replace("```sql", "").replace("```", "").strip()
                        write_sql_to_file(state.instance_id, state.db_name, sql_clean, state.model_name)
                    elif self.state_field == "step_by_step_plan" and isinstance(val, list):
                        write_plan_to_file(state.instance_id, state.db_name, val, state.model_name)

                else:
                    self.log(state, f"Warning: Key '{self.output_key}' not found in LLM response.", level="WARN")
                    Logger.log_status_banner(f"Agent: {self.name}", False, f"Missing key: {self.output_key}")
            
            break # Exit loop if no tool call

        return state
