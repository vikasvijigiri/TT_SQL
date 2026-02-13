import os
import time
import json
import re
import streamlit as st
from tt_sql.core.logger import Logger
from tt_sql.core.llm_service import LLMService
from tt_sql.core.agent_base import AgentState
from tt_sql.core.paths import initialize_directories, InstancePaths

# Import Agents
from tt_sql.agents.input_layer import SQLiteFileLoaderAgent, SchemaAnalyzerAgent, QueryIntentClassifierAgent, ContextEnrichmentAgent
from tt_sql.agents.planning_layer import RelationshipGraphBuilderAgent, StepByStepPlannerAgent
from tt_sql.agents.loop_layer import RefinementLoopAgent
from tt_sql.agents.execution_layer import SQLiteExecutorAgent

def get_agents(llm_service):
    """Factory to create agents with the given LLM service."""
    return [
        SQLiteFileLoaderAgent(),
        SchemaAnalyzerAgent(), 
        QueryIntentClassifierAgent(llm_service),
        ContextEnrichmentAgent(llm_service),
        RelationshipGraphBuilderAgent(),
        StepByStepPlannerAgent(llm_service),
        RefinementLoopAgent(llm_service),
        SQLiteExecutorAgent()
    ]

class StreamCapturer:
    """Proxies Streamlit container calls to capture text for history."""
    def __init__(self, container):
        self._container = container
        self.captured_text = ""
        
    def markdown(self, text, *args, **kwargs):
        if self._container: self._container.markdown(text, *args, **kwargs)
        self.captured_text += f"{text}\n\n"
        
    def caption(self, text, *args, **kwargs):
        if self._container: self._container.caption(text, *args, **kwargs)
        self.captured_text += f"_{text}_\n\n" 
        
    def info(self, text, *args, **kwargs):
        if self._container: self._container.info(text, *args, **kwargs)
        self.captured_text += f"ℹ️ {text}\n\n"
        
    def code(self, text, *args, **kwargs):
        if self._container: self._container.code(text, *args, **kwargs)
        self.captured_text += f"```\n{text}\n```\n\n"
        
    def error(self, text, *args, **kwargs):
        if self._container: self._container.error(text, *args, **kwargs)
        self.captured_text += f"❌ **{text}**\n\n"

# ============================================================
# CLEAN TERMINAL PRINTER
# ============================================================
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

def _print_header(agent_name):
    """Print a clean agent header."""
    print(f"\n{BLUE}{'─'*60}{RESET}")
    print(f"{BOLD}{CYAN}  ▸ {agent_name}{RESET}")
    print(f"{BLUE}{'─'*60}{RESET}")

def _print_tables(table_names):
    """Print table names in a clean grid."""
    cols = 4
    for i in range(0, len(table_names), cols):
        row = table_names[i:i+cols]
        print(f"  {', '.join(row)}")

def _print_sql(sql_str):
    """Print SQL in a clean copyable block."""
    print(f"\n{GREEN}┌{'─'*58}┐{RESET}")
    for line in sql_str.strip().split('\n'):
        # Truncate long lines
        display = line[:56]
        print(f"{GREEN}│{RESET} {display}")
    print(f"{GREEN}└{'─'*58}┘{RESET}")

def _print_bullets(items):
    """Print items as bullet points."""
    for item in items:
        item_str = str(item).strip()
        if item_str:
            print(f"  • {item_str}")

def _print_metrics(latency_ms, content_length):
    """Print latency and context length."""
    lat_s = latency_ms / 1000.0 if latency_ms else 0
    print(f"{DIM}  ⏱ {lat_s:.2f}s latency  |  📦 {content_length} chars{RESET}")


def run_analysis_pipeline(question, db_name, instance_id, model_name, rag_source="qdrant", output_container=None):
    """
    Pipeline execution with LLM-powered narrator commentary and auto-visualization.
    Runs agents stage-by-stage, narrating after each stage for a live-streaming feel.
    Returns: (final_state, iter_count, is_fatal, captured_transcript)
    """
    from tt_sql.agents.narrator_agent import NarratorAgent

    # Wrap container to capture output
    output = StreamCapturer(output_container)

    # Paths - Use centralized, OS-independent path
    db_path_absolute = str(InstancePaths.database(db_name))

    if not os.path.exists(db_path_absolute):
        output.error(f"Database not found at {db_path_absolute}")
        # Try to list available databases to help debugging
        try:
            available = [f.name for f in InstancePaths.database("").parent.glob("*.sqlite")]
            output.info(f"Available databases in {InstancePaths.database('').parent}: {available}")
        except:
            pass
        return None, 0, True, output.captured_text

    # Initialize directories with model-specific subfolders
    initialize_directories(model_name)

    # Initialize Components
    llm_service = LLMService(model=model_name)
    agents_list = get_agents(llm_service)
    narrator = NarratorAgent(llm_service)

    # Build agent map for stage-by-stage execution
    agent_map = {agent.name: agent for agent in agents_list}

    # State
    state = AgentState(
        user_query=question,
        db_path=db_path_absolute,
        instance_id=instance_id,
        rag_source=rag_source,
        model_name=model_name
    )

    start_time = time.time()

    # --- Listener Setup (terminal only) ---
    fatal_error_found = False
    all_logs = []
    last_metrics = {'latency': 0, 'tokens': 0}
    tables_list = []

    def direct_listener(message, msg_type):
        nonlocal fatal_error_found, all_logs, last_metrics
        # Log everything for file output, but don't print to terminal
        all_logs.append(f"[{msg_type}] {message}")

        if "ERROR:" in message:
            fatal_error_found = True
            return

        # Capture metrics silently
        if "Response metadata structure" in message:
            try:
                lat_match = re.search(r"'latencyMs':\s*\[(\d+)\]", message)
                if lat_match:
                    last_metrics['latency'] = int(lat_match.group(1))
                tok_match = re.search(r"'content-length':\s*'(\d+)'", message)
                if tok_match:
                    last_metrics['tokens'] = int(tok_match.group(1))
            except:
                pass
            return

    Logger.clear_listeners()
    Logger.register_listener(direct_listener)

    # Helper: stream narrator text into the UI + transcript
    def narrate(text):
        if text:
            if output_container:
                output_container.markdown(text)
            output.captured_text += f"{text}\n\n"

    try:
        # ═══════════════════════════════════════════════════════════
        # STAGE-BY-STAGE EXECUTION WITH LLM NARRATOR
        # ═══════════════════════════════════════════════════════════

        # 🎬 Opening narration
        narrate(narrator.narrate_opening(question))

        # --- Stage 1: File Loader ---
        if "SQLiteFileLoader" in agent_map:
            state = agent_map["SQLiteFileLoader"].run(state)

        # --- Stage 2: Schema Analyzer ---
        if "SchemaAnalyzer" in agent_map:
            state = agent_map["SchemaAnalyzer"].run(state)
            if state.schema_info:
                narrate(narrator.narrate_schema(state.schema_info, db_name))

        # --- Stage 3: Intent Classifier ---
        if "QueryIntentClassifier" in agent_map:
            state = agent_map["QueryIntentClassifier"].run(state)
            intent = state.query_intent or "GENERAL"
            complexity = state.complexity_score or "MEDIUM"
            narrate(narrator.narrate_intent(intent, complexity))

        # --- Stage 4: Context Enrichment ---
        if "ContextEnrichment" in agent_map:
            state = agent_map["ContextEnrichment"].run(state)
            rel_tables = state.relevant_tables or []
            tables_list = rel_tables
            narrate(narrator.narrate_tables(rel_tables))

        # --- Stage 5: Relationship Graph ---
        if "RelationshipGraphBuilder" in agent_map:
            state = agent_map["RelationshipGraphBuilder"].run(state)

        # --- Stage 6: Step-by-Step Planner ---
        if "StepByStepPlanner" in agent_map:
            state = agent_map["StepByStepPlanner"].run(state)
            narrate(narrator.narrate_plan(state.step_by_step_plan))

        # --- Stage 7: Refinement Loop (Generate → Execute → Critic) ---
        if "RefinementLoop" in agent_map:
            state = agent_map["RefinementLoop"].run(state)

            # Narrate SQL
            if state.chosen_query and "ERROR:" not in (state.chosen_query or ""):
                narrate(narrator.narrate_sql(state.chosen_query))
                # SQL is explained by narrator — raw code not shown in UI

            # Narrate execution
            if state.execution_result:
                narrate(narrator.narrate_execution(state.execution_result))

            # Narrate critic verdict
            if state.is_result_valid:
                narrate(narrator.narrate_critic(True, "", 0))
            elif state.critic_feedback:
                narrate(narrator.narrate_critic(False, state.critic_feedback, 0))

        # --- Stage 8: Final Executor ---
        if "SQLiteExecutor" in agent_map:
            state = agent_map["SQLiteExecutor"].run(state)

        elapsed = time.time() - start_time

        # ─── FINAL NARRATION ───
        narrate(narrator.narrate_final(
            state.chosen_query,
            state.execution_result,
            elapsed,
            state.is_result_valid
        ))

        # ─── INTERACTIVE VISUALIZATION OFFER ───
        if state.execution_result and state.execution_result.rows:
            rec = narrator.assess_visualization_needs(state.execution_result, question)
            state.viz_recommendation = rec
            
            if rec.get("recommended"):
                chart_type = rec.get("chart_type", "chart")
                offer_text = f"I have the results ready. I can visualize them as a **{chart_type}** for better clarity. Shall I generate the chart?"
                narrate(f"**Visualization**\n\n{offer_text}\n\n---")
            else:
                # Narrate standard completion if no viz needed
                pass

        # --- Save logs ---
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_file_path = os.path.join(logs_dir, f"{instance_id}.md")
        with open(log_file_path, "w", encoding="utf-8") as log_file:
            log_file.write(f"# Analysis Log: {instance_id}\n\n")
            log_file.write(f"**Question:** {question}\n\n")
            log_file.write(f"**Database:** {db_name}\n\n")
            log_file.write("---\n\n")
            log_file.write("## Detailed Execution Log\n\n")
            for log_entry in all_logs:
                log_file.write(f"{log_entry}\n")

        # Check Fatal Errors
        if (state.chosen_query and "ERROR:" in state.chosen_query) or \
           (state.error_message and "ERROR:" in state.error_message):
            fatal_error_found = True
            err_text = state.chosen_query if (state.chosen_query and "ERROR:" in state.chosen_query) else state.error_message
            output.error(f"⚠️ FATAL ERROR: {err_text}")

        state.relevant_tables = tables_list
        return state, 0, fatal_error_found, output.captured_text

    except Exception as e:
        print(f"{RED}  ✖ Critical Error: {str(e)}{RESET}")
        output.error(f"Critical Error: {str(e)}")
        return None, 0, True, output.captured_text

