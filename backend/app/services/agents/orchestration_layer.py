import json
from typing import Dict, Any, List
from app.services.agents.base import BaseAgent
from app.services.schemas.agent_state import AgentState
from app.services.engines.llm_service import LLMService
from app.services.utils.prompt_loader import PromptLoader
from app.services.utils.logger import Logger

class OrchestratorAgent(BaseAgent):
    """
    OrchestratorAgent is the final stage of the analysis pipeline. It synthesizes
    technical results (SQL execution data, logs) into a professional business
    summary and determines appropriate data visualizations.
    
    If multiple candidate results exist (from parallel schema analysis), 
    it evaluates them to present the most coherent insight.
    """
    def __init__(self, llm_service: LLMService, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None):
        super().__init__(name="Orchestrator", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir)
        self.llm = llm_service

    def run(self, state: AgentState, on_token: callable = None, mode: str = "FINAL") -> AgentState:
        """
        Generates a narrative summary based on the current pipeline mode.
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
                
                results_preview = "Preliminary metrics are being gathered..."
                if state.execution_result and state.execution_result.rows:
                    results_preview = (
                        f"Initial Findings Count: {state.execution_result.row_count}\n"
                        f"Sample Values: {state.execution_result.rows[:3]}"
                    )
                
                params = {
                    "recent_logs": recent_logs, 
                    "logical_scope": scope_desc,
                    "results_preview": results_preview
                }
                self.log(state, f"Mode: {mode} - Generating dynamic insight for scope: {scope_desc}.")

            else: # FINAL
                prompt_name = "orchestrator_final_synthesis"
                
                # Format candidate results if available for multi-perspective evaluation
                candidates_text = ""
                if hasattr(state, "candidate_results") and state.candidate_results:
                    candidates_text = "\n\n### Candidate Solutions from Multiple Schema Perspectives:\n"
                    for i, cand in enumerate(state.candidate_results):
                        status = "✅ VALID" if cand.get("valid") else "❌ INVALID"
                        candidates_text += f"\nCandidate {i+1} ({cand['set_name']}): {status}\n"
                        candidates_text += f"SQL: {cand['sql']}\n"
                        if cand.get("result") and hasattr(cand["result"], "rows") and cand["result"].rows:
                            candidates_text += f"Results Preview (first 2 rows): {cand['result'].rows[:2]}\n"
                        else:
                            candidates_text += "Results: (No data returned or error)\n"
                
                results_preview = "No data rows were retrieved from the database."
                if state.execution_result and state.execution_result.rows:
                    results_preview = (
                        f"Columns: {state.execution_result.columns}\n"
                        f"Total Count: {state.execution_result.row_count}\n"
                        f"Sample High-Impact Rows: {state.execution_result.rows[:5]}"
                    )
                
                params = {
                    "question": state.user_query, 
                    "results_preview": results_preview + candidates_text, 
                    "recent_logs": recent_logs
                }
                self.log(state, "Mode: FINAL - Synthesizing comprehensive business summary from multiple sets.")

            # 2. LLM Interaction & Streaming
            messages = loader.load_prompt(prompt_name, **params)
            full_summary_accumulator = state.business_summary or ""
            
            # --- Elite Streaming Implementation ---
            import time
            raw_response = ""
            markdown_part = ""
            metadata_part = ""
            seen_delimiter = False
            delimiter = "###METADATA###"
            
            self.log(state, f"Beginning live stream for mode: {mode}")
            
            for token in self.llm.get_completion_stream(messages, agent_name=self.name):
                raw_response += token
                
                # Check for delimiter context
                if delimiter in raw_response and not seen_delimiter:
                    seen_delimiter = True
                    # Everything before first delimiter is markdown
                    parts = raw_response.split(delimiter, 1)
                    markdown_part = parts[0]
                    # Don't stream the delimiter or JSON to on_token
                
                if not seen_delimiter:
                    # Stream the token to UI if we haven't hit the metadata yet
                    if on_token:
                        # Pacing: 'slow and beautiful' token-wise reveal
                        # 0.02s delay creates a high-end typing feel
                        for char in token:
                            on_token(char)
                            time.sleep(0.01) # Ultra-smooth character-wise pacing
                
                # If we've seen delimiter, we just accumulate the rest for JSON parsing
            
            # Post-processing after stream finishes
            if delimiter in raw_response:
                parts = raw_response.split(delimiter, 1)
                markdown_part = parts[0].strip()
                metadata_part = parts[1].strip()
            else:
                markdown_part = raw_response.strip()
            
            # Handle JSON Metadata (chart_config) in FINAL mode
            if mode == "FINAL" and metadata_part:
                try:
                    # Clean potential markdown fences from metadata if LLM ignored instructions
                    cleaned_json = metadata_part
                    if "```json" in cleaned_json.lower():
                        cleaned_json = cleaned_json.split("```json")[1].split("```")[0].strip()
                    elif "```" in cleaned_json:
                        cleaned_json = cleaned_json.split("```")[1].strip()
                        
                    parsed = json.loads(cleaned_json)
                    state.chart_config = parsed.get("chart_config")
                except json.JSONDecodeError:
                    self.log(state, "Failed to parse metadata JSON at end of stream.", level="WARNING")

            # Final state update
            if full_summary_accumulator:
                state.business_summary = full_summary_accumulator + "\n\n---\n\n" + markdown_part
            else:
                state.business_summary = markdown_part

            self.log(state, f"Narrative stage '{mode}' completed successfully.")

        except Exception as e:
            import traceback
            Logger.log(f"Orchestrator Failure: {traceback.format_exc()}", level="ERROR")
            if mode == "FINAL" and not state.business_summary:
                state.business_summary = "Technical analysis complete. Please refer to results data below."

        return state
