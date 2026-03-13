import json
from app.services.agents.base import BaseAgent
from app.models.agent_state import AgentState
from app.services.llm_service import LLMService
from app.services.prompt_loader import PromptLoader
from app.services.logger import Logger

class OrchestratorAgent(BaseAgent):
    """
    Final agent in the pipeline that provides a professional business summary.
    Analyzes the question, SQL, and results to explain insights in business context.
    In FINAL mode, outputs a structured JSON with markdown_summary + chart_config.
    """
    
class OrchestratorAgent(BaseAgent):
    """
    OrchestratorAgent is the final stage of the analysis pipeline. It synthesizes
    technical results (SQL execution data, logs) into a professional business
    summary and determines appropriate data visualizations.
    """
    def __init__(self, llm_service: LLMService, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="Orchestrator", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.llm = llm_service

    def run(self, state: AgentState, on_token: callable = None, mode: str = "FINAL") -> AgentState:
        """
        Generates a narrative summary based on the current pipeline mode.
        
        Args:
            state (AgentState): The current state of the analysis pipeline.
            on_token (callable, optional): Callback for real-time token streaming.
            mode (str): The operational mode (PLAN, RAG, MID, or FINAL).
            
        Returns:
            AgentState: The updated state with business_summary and chart_config.
        """
        loader = PromptLoader()
        recent_logs = "\n".join(state.logs[-10:]) if state.logs else "No recent activity logs available."
        
        # 1. Context Preparation
        try:
            if mode == "PLAN":
                prompt_name = "orchestrator_pre_strategy"
                strategy_text = "\n- ".join(state.step_by_step_plan) if state.step_by_step_plan else "Executing standard multi-stage SQL analysis."
                params = {"question": state.user_query, "strategy": strategy_text}
                self.log(state, "Mode: PLAN - Generating strategic roadmap narrative.")

            elif mode in ["RAG", "MID"]:
                prompt_name = "orchestrator_mid_findings"
                tables = set(col.get("table_name", "Unknown") for col in (state.rag_columns or []))
                scope_desc = f"analytical focus centered on {' and '.join(tables)} dataset" if tables else "core operational datasets"
                params = {"recent_logs": recent_logs, "logical_scope": scope_desc}
                self.log(state, f"Mode: {mode} - Generating contextual insight for scope: {scope_desc}.")

            else: # FINAL
                prompt_name = "orchestrator_final_synthesis"
                results_preview = "No data rows were retrieved from the database."
                if state.execution_result and state.execution_result.rows:
                    results_preview = (
                        f"Columns: {state.execution_result.columns}\n"
                        f"Total Count: {state.execution_result.row_count}\n"
                        f"Sample High-Impact Rows: {state.execution_result.rows[:5]}"
                    )
                params = {
                    "question": state.user_query, 
                    "results_preview": results_preview, 
                    "recent_logs": recent_logs
                }
                self.log(state, "Mode: FINAL - Synthesizing comprehensive business summary.")

            # 2. LLM Interaction & Streaming
            messages = loader.load_prompt(prompt_name, **params)
            full_summary_accumulator = state.business_summary or ""
            
            if mode == "FINAL":
                # Final synthesis requires structured JSON for summaries + charts
                raw_json = ""
                for token in self.llm.get_completion_stream(messages, agent_name=self.name):
                    raw_json += token
                
                # Robust extraction of JSON from potentially Markdown-wrapped LLM output
                cleaned_json = raw_json.strip()
                if "```json" in cleaned_json.lower():
                    cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned_json:
                    cleaned_json = cleaned_json.split("```")[1].strip()

                try:
                    parsed = json.loads(cleaned_json)
                    markdown_part = parsed.get("markdown_summary", "Analysis completed with no further summary.")
                    state.chart_config = parsed.get("chart_config")
                except json.JSONDecodeError:
                    self.log(state, "JSON Parsing Failure in Orchestrator. Falling back to raw text.", level="WARNING")
                    markdown_part = raw_json
                
                if full_summary_accumulator:
                    state.business_summary = full_summary_accumulator + "\n\n---\n\n" + markdown_part
                else:
                    state.business_summary = markdown_part

                if on_token and markdown_part:
                    if full_summary_accumulator: on_token("\n\n---\n\n")
                    for char in markdown_part: on_token(char)
            else:
                # PLAN and RAG modes stream fluid prose narration
                if on_token and full_summary_accumulator:
                    on_token("\n\n---\n\n")
                
                new_tokens = ""
                for token in self.llm.get_completion_stream(messages, agent_name=self.name):
                    if on_token: on_token(token)
                    new_tokens += token
                
                if full_summary_accumulator:
                    state.business_summary = full_summary_accumulator + "\n\n---\n\n" + new_tokens
                else:
                    state.business_summary = new_tokens

            self.log(state, f"Narrative stage '{mode}' completed successfully.")

        except Exception as e:
            self.log(state, f"Orchestrator Failure in stage {mode}: {str(e)}", level="ERROR")
            if mode == "FINAL" and not state.business_summary:
                state.business_summary = "Technical analysis complete. Please refer to results data below."

        return state
