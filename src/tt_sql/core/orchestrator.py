from typing import List, Dict
import time
from .state import AgentState
from .agent_base import BaseAgent
from .logger import Logger
from .pipeline_config import PipelineConfig

class Orchestrator:
    """
    Manages the lifecycle of the Text-to-SQL generation process.
    Coordinates the execution of agents in a strict pipeline or dynamic graph.
    """
    
    def __init__(self, agent_registry: List[BaseAgent], config_path: str = None):
        self.all_agents = {agent.name: agent for agent in agent_registry}
        self.config = PipelineConfig(config_path)
        
        # Build execution order from config
        self.agents = []
        for agent_name in self.config.get_enabled_agents():
            if agent_name in self.all_agents:
                self.agents.append(self.all_agents[agent_name])
            else:
                Logger.log(f"Warning: Agent '{agent_name}' in config not found in registry", level="WARN")
        
    def run_pipeline(self, initial_state: AgentState) -> AgentState:
        """
        Runs the agents in sequence (for now). 
        Future versions could support DAGs or dynamic routing.
        """
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        
        current_state = initial_state
        start_time = time.time()
        
        Logger.log_section("Starting Orchestrator pipeline")
        current_state.add_log("Starting Orchestrator pipeline.")
        
        # We use a ThreadPoolExecutor for a watchdog timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            log_file_path = Logger._get_log_file()
            
            def log_wrapper(a, s, lf):
                Logger.bind_log_file(lf)
                return a.run(s)

            for agent in self.agents:
                try:
                    # Skip RefinementLoop header since it manages its own internal agent headers
                    if agent.name != "RefinementLoop":
                        Logger.log_section(f"Agent: {agent.name}")
                    
                    current_state.add_log(f"Starting Agent: {agent.name}")
                    # Update current step metadata
                    current_state.current_step = agent.name
                    
                    # Execute Agent with 240s timeout
                    future = executor.submit(log_wrapper, agent, current_state, log_file_path)
                    try:
                        current_state = future.result(timeout=240)
                    except TimeoutError:
                        timeout_msg = f"CRITICAL: Agent {agent.name} timed out after 240 seconds."
                        current_state.add_log(timeout_msg)
                        current_state.error_message = timeout_msg
                        Logger.log(timeout_msg, level="ERROR")
                        break
                    
                    current_state.add_log(f"Finished Agent: {agent.name}")
                    
                    # Optional: Check for critical failures in state and halt if needed
                    if current_state.error_message and "CRITICAL" in current_state.error_message: 
                         current_state.add_log("Critical error detected. Halting pipeline.")
                         break
                         
                except Exception as e:
                    import traceback
                    error_msg = f"Orchestrator caught exception in {agent.name}: {str(e)}"
                    print(f"DEBUG ORCHESTRATOR ERROR: {error_msg}")
                    print(traceback.format_exc())
                    current_state.add_log(error_msg)
                    Logger.log(error_msg, level="ERROR")
                    break
                
        duration = time.time() - start_time
        current_state.add_log(f"Pipeline finished in {duration:.2f}s")
        return current_state

    def cleanup(self):
        """Clears high-memory references."""
        self.agents = []
