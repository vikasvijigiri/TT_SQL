import streamlit as st
st.set_page_config(
    page_title="nQuiry - Premium",
    page_icon="🤖",
    layout="wide"
)
import os
import json
import time
import gc
from typing import Dict, Any
from dotenv import load_dotenv
import pandas as pd
import csv

# Load environment variables
load_dotenv()

# Configure AWS credentials programmatically from .env
# This is required for ChatBedrockConverse to work properly
bedrock_key_id = os.getenv("BEDROCK_ACCESS_KEY_ID")
bedrock_secret = os.getenv("BEDROCK_SECRET_ACCESS_KEY")
bedrock_region = os.getenv("BEDROCK_REGION", "us-east-1")

if bedrock_key_id and bedrock_secret:
    os.environ["AWS_ACCESS_KEY_ID"] = bedrock_key_id
    os.environ["AWS_SECRET_ACCESS_KEY"] = bedrock_secret
    os.environ["AWS_DEFAULT_REGION"] = bedrock_region

# Adjust path to import src modules if needed
import sys
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The above is safer as relative, but let's ensure it doesn't break.

# Initialize Session State
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "execution_times" not in st.session_state:
    st.session_state.execution_times = []
if "selected_task_id" not in st.session_state:
    st.session_state.selected_task_id = None
if "last_run_result" not in st.session_state:
    st.session_state.last_run_result = None # Stores (final_state, final_iter_count)
if "settings_model" not in st.session_state:
    st.session_state.settings_model = os.getenv("LLM_MODEL", "gpt-4o")
if "settings_skip_existing" not in st.session_state:
    st.session_state.settings_skip_existing = True
if "settings_rag" not in st.session_state:
    st.session_state.settings_rag = "None"
if "settings_enable_rag" not in st.session_state:
    st.session_state.settings_enable_rag = False
if "active_question" not in st.session_state:
    st.session_state.active_question = None
if "draft_question" not in st.session_state:
    st.session_state.draft_question = ""
if "evaluation_accuracy" not in st.session_state:
    st.session_state.evaluation_accuracy = None
# Initialize Chat History for Conversational Experience
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_task_id_widget" not in st.session_state:
    st.session_state.selected_task_id_widget = None


from tt_sql.core.logger import Logger
from tt_sql.core.llm_service import LLMService
from tt_sql.core.orchestrator import Orchestrator
from tt_sql.core.agent_base import AgentState
from tt_sql.core.file_coordinator import FileCoordinator
from tt_sql.core.ui_runner import run_analysis_pipeline

# Import Agents (Removed as they are now in ui_runner)
# from tt_sql.agents... 

# --- Configuration & Styling ---
# Already set at top

# Custom CSS for Premium Look
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .main-header {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        color: #ffffff;
        font-size: 1.4rem;
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .question-box {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 12px;
        border-left: 6px solid #4b6cb7;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .question-text {
        font-size: 1.0rem;
        color: #e0e0e0;
        font-family: 'Roboto Mono', monospace;
    }
    .step-container {
        background-color: #262730;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #363945;
    }
    .stStatusWidget > div {
        background-color: #1a1c24 !important;
        border: 1px solid #4b6cb7 !important;
    }
    .action-card {
        background: linear-gradient(135deg, #1e2130 0%, #262a3d 100%);
        padding: 15px 20px;
        border-radius: 12px;
        border-left: 5px solid #3498db;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        transition: transform 0.2s ease;
    }
    .action-card:hover {
        transform: translateX(5px);
        border-left-color: #1abc9c;
    }
    .action-index {
        background: #3498db;
        color: white;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        margin-right: 15px;
        flex-shrink: 0;
        font-size: 0.9rem;
    }
    .action-text {
        color: #ffffff;
        font-size: 0.85rem;
        font-weight: 500;
        line-height: 1.4;
    }
    .phase-container {
        border: 1px solid rgba(255, 255, 255, 0.1);
        background: rgba(40, 44, 60, 0.4);
        backdrop-filter: blur(10px);
        padding: 20px;
        border-radius: 16px;
        margin-bottom: 25px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }
    .phase-header {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        font-weight: 600;
        color: #3498db;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .phase-header::after {
        content: "";
        flex-grow: 1;
        height: 1px;
        background: linear-gradient(90deg, #3498db, transparent);
        margin-left: 15px;
        opacity: 0.3;
    }
    /* Centering Main Content */
    [data-testid="stMain"] > div {
        max-width: 1100px;
        margin-left: auto;
        margin-right: auto;
    }
    
    /* ChatGPT Light Theme Reconstruction */
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
    }
    [data-testid="stHeader"] {
        background-color: #ffffff !important;
    }
    
    /* Typography - Apply to body and content, but exclude icons */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Preserve Streamlit Icons */
    .st-emotion-cache-1v0yc4i, .st-icon, [class*="st-icon"] {
        font-family: "Source Sans Pro", sans-serif !important;
    }
    
    .chat-user-msg {
        color: #0d0d0d;
        font-size: 1rem;
        line-height: 1.6;
        margin-bottom: 20px;
        width: 100%;
    }
    .chat-bot-msg {
        color: #0d0d0d;
        font-size: 1rem;
        line-height: 1.6;
        width: 100%;
        margin-bottom: 25px;
    }
    .chat-small-text {
        font-size: 0.85rem;
        color: #676767;
        line-height: 1.5;
        margin-bottom: 8px;
    }
    .agent-header {
        font-size: 0.75rem;
        font-weight: 700;
        color: #8e8e93;
        margin-top: 15px;
        margin-bottom: 5px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Code Blocks ChatGPT Style */
    .stCodeBlock {
         background-color: #f9f9f9 !important;
         border-radius: 8px !important;
         border: 1px solid #e5e5e5 !important;
    }
    
    /* High-Fidelity Native Chat Input Styling */
    [data-testid="stChatInput"] {
        max-width: 1100px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        background-color: transparent !important;
    }
    [data-testid="stChatInput"] > div {
        background-color: #f4f4f4 !important;
        border-radius: 20px !important;
        border: 1px solid #e5e5e5 !important;
        padding-left: 15px !important; /* Reset padding - no icon */
        min-height: 70px !important; 
        display: flex !important;
        align-items: center !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
    }
    [data-testid="stChatInput"] textarea {
        background-color: transparent !important;
        border: none !important;
        color: #0d0d0d !important;
        font-size: 1.05rem !important;
        line-height: 1.5 !important;
    }
    
    /* Native Send Button - Circular Black */
    [data-testid="stChatInput"] button {
        background-color: #0d0d0d !important;
        color: #ffffff !important;
        border-radius: 50% !important;
        width: 32px !important;
        height: 32px !important;
        border: none !important;
    }
    
    /* Overlay for File Uploader - Removed as per user request */
    [data-testid="stFileUploadDropzone"], .stFileUploader label, .stFileUploader small {
        display: none !important;
    }
    
    /* Sidebar ChatGPT Style */
    [data-testid="stSidebar"] {
        background-color: #f9f9f9 !important;
        border-right: 1px solid #e5e5e5 !important;
    }
    [data-testid="stSidebarNav"] {
        background-color: #f9f9f9 !important;
    }
    
    /* Hide scrollbar for cleaner look */
    ::-webkit-scrollbar {
        width: 8px;
    }
    ::-webkit-scrollbar-thumb {
        background: #373737;
        border-radius: 10px;
    }
    
    /* Ensure Sidebar Widgets have contrast */
    [data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] .stText, [data-testid="stSidebar"] label {
        color: #0d0d0d !important;
    }
    
    /* Sidebar Button Styling for Visibility */
    [data-testid="stSidebar"] button {
        background-color: #ffffff !important;
        border: 1px solid #e5e5e5 !important;
        color: #0d0d0d !important;
        transition: all 0.2s !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #f4f4f4 !important;
        border-color: #d1d1d1 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    }
    
    /* Specific Primary Button Style in Sidebar */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #0d0d0d !important;
        color: #ffffff !important;
        border: none !important;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        background-color: #2f2f2f !important;
    }

    /* Colorful Nquiry Table Styling */
    .nquiry-table-container {
        width: 100%;
        overflow-x: auto;
        margin-top: 15px;
        margin-bottom: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid #e5e5e5;
    }
    .nquiry-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
        background-color: white;
    }
    .nquiry-table th {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white;
        text-align: left;
        padding: 14px 20px;
        font-weight: 600;
        font-size: 0.95rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .nquiry-table td {
        padding: 12px 20px;
        border-bottom: 1px solid #f0f0f0;
        color: #333;
        font-size: 0.9rem;
    }
    .nquiry-table tr:last-child td {
        border-bottom: none;
    }
    .nquiry-table tr:nth-child(even) {
        background-color: #fcfcfc;
    }
    .nquiry-table tr:hover {
        background-color: #f1f4f9;
        transition: background-color 0.2s ease;
    }
</style>
""", unsafe_allow_html=True)

# --- Functions ---

def display_styled_dataframe(df, container=None):
    """Refined helper to display a colorful, premium HTML table."""
    if container is None:
        container = st
        
    if df is None or df.empty:
        container.info("No data returned.")
        return

    # Convert to HTML
    html = df.to_html(index=False, classes='nquiry-table')
    
    # Wrap in container
    styled_html = f'<div class="nquiry-table-container">{html}</div>'
    
    container.markdown(styled_html, unsafe_allow_html=True)

def load_tasks(jsonl_path):
    tasks = []
    if os.path.exists(jsonl_path):
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    tasks.append(json.loads(line))
    return tasks


def run_evaluation(target_instance_id=None, show_ui=True, user_query=None, result_dir_override=None):
    """Runs the external evaluation script and returns the score."""
    import subprocess
    import re
    import os # Added import for os module
    
    try:
        # Paths (Keeping hardcoded as per original requirement for the user environment)
        eval_venv_python = r"C:\Users\VikasVijigiri\Documents\Spider2\spider2-lite\evaluation_suite\.venv\Scripts\python.exe"
        eval_script = r"C:\Users\VikasVijigiri\Documents\Spider2\spider2-lite\evaluation_suite\evaluate.py"
        eval_cwd = r"C:\Users\VikasVijigiri\Documents\Spider2\spider2-lite\evaluation_suite"
        
        if result_dir_override:
             csv_dir = result_dir_override
        else:
             base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
             csv_dir = os.path.join(base_dir, "results", "csv")
        
        if not os.path.exists(csv_dir):
            if show_ui: st.error(f"Results directory not found at {csv_dir}")
            return 0.0

        cmd = [
            eval_venv_python,
            eval_script,
            "--result_dir", csv_dir,
            "--mode", "exec_result"
        ]
        
        # Run command
        result = subprocess.run(
            cmd, 
            cwd=eval_cwd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace'
        )
        
        score = 0.0
        if result.returncode == 0:
            # Extract score using Regex
            # Pattern: "Final score: 0.0"
            match = re.search(r"Final score:\s*([0-9.]+)", result.stdout)
            
            if match:
                # Convert to percentage and round to nearest integer
                score = round(float(match.group(1)) * 100)
                
                # --- RAG Learning Logic ---
                if score == 100 and target_instance_id and user_query:
                    try:
                        from tt_sql.rag.vector_store import VectorStoreAgent
                        from tt_sql.core.file_coordinator import FileCoordinator
                        
                        # Load generating query and final SQL
                        coord = FileCoordinator()
                        final_sql = coord.read_sql(target_instance_id)
                        
                        # Get user query from the original state or disk if target_instance_id is provided
                        # For simplicity, we assume we have access to the context if we are running eval
                        # In this app, score is calculated after run_analysis_pipeline
                        
                        # We need the user query. If single task, it's easier.
                        # For now, let's try to get it from session state or similar
                        pass 
                    except Exception as e:
                        pass
                
                if show_ui:
                    st.success(f"Evaluation Completed! Score: {score}%")
            elif show_ui:
                st.warning("Evaluation finished, but could not parse 'Final score'.")
                
            if show_ui:
                with st.expander("View Full Evaluation Logs"):
                    st.text_area("Output", result.stdout, height=200)
            
            return score # Always return score, even if not showing UI
        elif show_ui:
            st.error("Evaluation Failed")
            st.text_area("Error Output", result.stderr + "\n" + result.stdout, height=200)
            
        return score

    except Exception as e:
        if show_ui: st.error(f"Failed to run evaluation: {str(e)}")
        return 0.0


def run_batch_sequence(tasks_to_run, model_name, rag_source="qdrant"):
    """Runs a batch of tasks sequentially and sorts results."""
    import shutil
    from tt_sql.core.vector_store import VectorStoreAgent
    passed_count = 0
    failed_count = 0
    skipped_count = 0
    
    # Metrics tracking
    task_times = []
    total_context_chars = 0
    batch_start = time.time()
    
    # Progress + status in sidebar, details in main area
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_csv = os.path.join(base_dir, "results", "csv")
    passed_dir = os.path.join(base_dir, "results", "passed_examples")
    failed_dir = os.path.join(base_dir, "results", "failed_examples")
    
    os.makedirs(passed_dir, exist_ok=True)
    os.makedirs(failed_dir, exist_ok=True)
    
    # Temp dir for isolated evaluation
    temp_eval_dir = os.path.join(base_dir, "results", "temp_batch_eval")
    os.makedirs(temp_eval_dir, exist_ok=True)

    for i, task in enumerate(tasks_to_run):
        iid = task['instance_id']
        
        # Check for existing results to skip
        exists_passed = os.path.exists(os.path.join(passed_dir, f"{iid}.csv"))
        exists_failed = os.path.exists(os.path.join(failed_dir, f"{iid}.csv"))
        exists_raw = os.path.exists(os.path.join(results_csv, f"{iid}.csv"))
        
        if exists_passed or exists_failed or exists_raw:
            status_text.text(f"Skipping {i+1}/{len(tasks_to_run)}: {iid} (Already Exists)")
            progress_bar.progress((i + 1) / len(tasks_to_run))
            skipped_count += 1
            continue

        db = task['db']
        q = task['question']
        
        status_text.text(f"Processing {i+1}/{len(tasks_to_run)}: {iid}")
        
        task_start = time.time()
        
        # Run Pipeline
        with st.expander(f"Details: {iid}", expanded=False):
            container = st.container()
            final_state, _, is_fatal, _ = run_analysis_pipeline(
                question=q,
                db_name=db,
                instance_id=iid,
                model_name=model_name,
                rag_source=rag_source,
                output_container=container
            )
        
        task_elapsed = time.time() - task_start
        task_times.append(task_elapsed)
        
        # Track context length from final SQL
        if final_state and final_state.chosen_query:
            total_context_chars += len(final_state.chosen_query)
        
        # Evaluate
        target_csv = os.path.join(results_csv, f"{iid}.csv")
        score = 0.0
        
        if os.path.exists(target_csv):
            # Isolate File for Eval
            temp_target = os.path.join(temp_eval_dir, f"{iid}.csv")
            # Clean temp dir first
            for f in os.listdir(temp_eval_dir):
                try:
                    os.remove(os.path.join(temp_eval_dir, f))
                except: pass
            
            shutil.copy2(target_csv, temp_target)
            
            # Run Eval on Temp Dir
            score = run_evaluation(show_ui=False, result_dir_override=temp_eval_dir)
        
        # Categorize
        if score == 100:
            dest_dir = passed_dir
            passed_count += 1
            
            # --- Auto-Learning: Upsert to Qdrant ---
            if rag_source == "qdrant":
                try:
                    # Initialize Qdrant (Lazy load)
                    qdrant_agent = VectorStoreAgent()
                    if final_state and final_state.chosen_query:
                         qdrant_agent.upsert_correct_pair(q, final_state.chosen_query, instance_id=iid)
                except Exception as e:
                    print(f"Auto-Upsert failed for {iid}: {e}")
        else:
            dest_dir = failed_dir
            failed_count += 1
            
        # Move Artifacts
        if os.path.exists(target_csv):
             shutil.copy2(target_csv, os.path.join(dest_dir, f"{iid}.csv"))
        
        exec_sql = os.path.join(base_dir, "results", "execution", f"{iid}.sql")
        if os.path.exists(exec_sql):
             shutil.copy2(exec_sql, os.path.join(dest_dir, f"{iid}.sql"))

        log_md = os.path.join(base_dir, "results", "logs", f"{iid}.md")
        if os.path.exists(log_md):
             shutil.copy2(log_md, os.path.join(dest_dir, f"{iid}.md"))

        progress_bar.progress((i + 1) / len(tasks_to_run))
    
    # --- Batch Summary Metrics ---
    total_latency = time.time() - batch_start
    processed_count = len(task_times)
    avg_time = sum(task_times) / processed_count if processed_count > 0 else 0
    
    status_text.success(f"Batch Complete! ✅ {passed_count} | ❌ {failed_count} | ⏭ {skipped_count}")
    
    st.markdown("---")
    st.subheader("📊 Batch Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tasks Processed", processed_count)
    col2.metric("Avg Time / Task", f"{avg_time:.1f}s")
    col3.metric("Total Latency", f"{total_latency:.1f}s")
    col4.metric("Total SQL Chars", f"{total_context_chars:,}")
    
    col5, col6, col7, _ = st.columns(4)
    col5.metric("✅ Passed", passed_count)
    col6.metric("❌ Failed", failed_count)
    col7.metric("⏭ Skipped", skipped_count)
    
    if processed_count > 0:
        accuracy = (passed_count / processed_count) * 100
        st.progress(accuracy / 100)
        st.caption(f"Batch Accuracy: **{accuracy:.1f}%** ({passed_count}/{processed_count})")
    
    st.balloons()


# --- Main App ---
st.markdown('<h1 class="main-header">nQuiry</h1>', unsafe_allow_html=True)
st.caption("Advanced Agentic SQL Generation with Automated Refinement")

with st.expander("ℹ️ About nQuiry"):
    st.markdown("""
    **nQuiry** is an agentic text-to-SQL engine that turns natural language questions into executable SQL queries.
    
    ### Inputs
    - **Mandatory**:
        - **Question**: A clear, specific question about your data (e.g., *"Show me the top 5 players by run count"*).
        - **Database**: The target SQLite database to query.
    
    - **Optional**:
        - **Instance ID**: Specific task ID for benchmarking (if using Spider dataset).
        - **Model**: Choose between GPT-4o, Claude 3.5 Sonnet, etc.
        - **Knowledge Base (RAG)**: Enable external knowledge from Qdrant/Bedrock to help with domain-specific terms.
    
    ### How it works
    The system uses a multi-agent pipeline (Planner, Generator, Refiner) to explore the schema, plan the query, and self-correct errors before showing you the result.
    """)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(f"**{message['content']}**")
            if "iid" in message:
                st.caption(f"Task ID: {message['iid']} | DB: {message['db']}")
        else:
            with st.container():
                st.markdown(message["content"])
                # SQL display removed as per user request
                # if "sql" in message and message["sql"]:
                #     st.code(message["sql"], language="sql")
                
                if "data" in message and message["data"] is not None:
                    display_styled_dataframe(message["data"])
                if "is_error" in message and message["is_error"]:
                    st.error(message["content"])
                
                # Render interactive chart if present
                if message.get("has_chart"):
                    from tt_sql.agents.narrator_agent import NarratorAgent
                    # Use a cached or lightweight LLM service wrapper if possible, 
                    # but for now init is cheap enough.
                    ls = LLMService(model=st.session_state.settings_model)
                    narrator = NarratorAgent(ls)
                    # The message needs 'chart_data' (ExecutionResult) and 'query'
                    if "chart_data" in message:
                        narrator.generate_plot_for_ui(message["chart_data"], message.get("query", ""), st.container())

# --- Pipeline Execution ---
# Sidebar Pipeline Controls
with st.sidebar:
    st.markdown("### 🔗 Links")
    st.markdown("[![GitHub](https://img.shields.io/badge/GitHub-Repo-181717?style=for-the-badge&logo=github)](https://github.com/vikasv-ngenux/txt2sql-Nakul)")
    
    st.title("⚙️ Configuration")
    
    jsonl_path = "spider2-lite.jsonl" 
    tasks = load_tasks(jsonl_path)
    
    st.divider()
    st.subheader("🎯 Spider2 Examples")
    task_options = {t.get("instance_id", "Unknown"): t for t in tasks}
    
    # Ensure selected_task_id is valid
    if st.session_state.selected_task_id not in task_options:
        st.session_state.selected_task_id = list(task_options.keys())[0] if tasks else None
    
    # Initial population of draft question if empty
    if st.session_state.selected_task_id in task_options and not st.session_state.draft_question:
        q = task_options[st.session_state.selected_task_id].get("question", "")
        st.session_state.draft_question = q
        
    def on_task_change():
        if "active_question" in st.session_state:
            st.session_state.active_question = None
        
        # Pre-fill draft question safely
        task_id = st.session_state.get("selected_task_id_widget")
        if task_id and task_id in task_options:
            q = task_options[task_id].get("question", "")
            st.session_state.draft_question = q

    selected_id = st.selectbox(
        "Select Instance ID", 
        list(task_options.keys()),
        index=list(task_options.keys()).index(st.session_state.selected_task_id) if st.session_state.selected_task_id else 0,
        key="selected_task_id_widget",
        on_change=on_task_change
    )
    st.session_state.selected_task_id = selected_id
    selected_task = task_options.get(selected_id)
    
    
    st.divider()
    st.subheader("🏆 Spider Evaluation")
    if st.button("📊 Calc Final Accuracy", type="secondary", width='stretch'):
        with st.spinner("Evaluating..."):
            acc = run_evaluation(show_ui=False)
            st.session_state.evaluation_accuracy = acc
    
    if st.session_state.evaluation_accuracy is not None:
         st.markdown(f"""
         <div style="padding: 10px; background-color: #3498db22; border: 1px solid #3498db; border-radius: 8px; text-align: center; margin-top: 10px;">
            <div style="font-size: 0.8rem; color: #888;">Spider Accuracy</div>
            <div style="font-size: 1.5rem; font-weight: bold; color: #3498db;">{st.session_state.evaluation_accuracy}%</div>
         </div>
         """, unsafe_allow_html=True)

    st.divider()
    st.subheader("⚙️ Settings")
    model_options = [
        "gpt-4o-mini",
        "gpt-4o", 
        "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
        "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
    ]
    # Ensure default model from .env is in options if not already
    env_model = os.getenv("LLM_MODEL", "gpt-4o")
    if env_model not in model_options:
        model_options.append(env_model)
        
    model_name = st.selectbox(
        "Model", 
        model_options, 
        index=model_options.index(st.session_state.settings_model) if st.session_state.settings_model in model_options else 0,
        key="settings_model"
    )
    # RAG Configuration
    st.write("### 🧠 RAG Configuration")
    rag_option = st.radio(
        "Knowledge Source",
        ["Qdrant (Local)", "Amazon Bedrock KB", "None"],
        index=["Qdrant (Local)", "Amazon Bedrock KB", "None"].index(st.session_state.settings_rag),
        key="settings_rag",
        help="Choose the RAG source for context enrichment."
    )
    
    rag_source_map = {
        "Qdrant (Local)": "qdrant",
        "Amazon Bedrock KB": "bedrock", 
        "None": "none"
    }
    selected_rag_source = rag_source_map[rag_option]
    
    st.divider()
    if st.button("🚀 Run Full Batch Sequence", type="primary"):
        if not tasks:
            st.error("No tasks loaded.")
        else:
            st.session_state["_batch_trigger"] = {
                "tasks": tasks,
                "model": st.session_state.settings_model,
                "rag": selected_rag_source
            }

# --- Batch Execution (runs in main page context) ---
if "_batch_trigger" in st.session_state and st.session_state["_batch_trigger"]:
    batch_cfg = st.session_state.pop("_batch_trigger")
    run_batch_sequence(batch_cfg["tasks"], batch_cfg["model"], batch_cfg["rag"])

# Main Content Logic
if selected_task:
    # Pipeline Run logic (Triggered by st.chat_input below)
    if st.session_state.is_running == "single":
        instance_id = st.session_state.selected_task_id
        db_name = task_options[instance_id].get("db")
        
        # Robust Retrieval & Validation
        display_question = st.session_state.get("active_question", "")
        if not display_question or not isinstance(display_question, str) or not display_question.strip():
            st.warning("⚠️ No active question found in session. Please submit your query again.")
            st.session_state.is_running = False
            st.stop()
            
        model_name = st.session_state.settings_model
        run_start = time.time()
        
        # Run Pipeline with Sequential Stream
        with st.chat_message("assistant"):
            chat_container = st.container()
            
            # Run the pipeline, streaming output to this container
            final_state, final_iter_count, is_fatal, captured_transcript = run_analysis_pipeline(
                question=display_question, 
                db_name=db_name, 
                instance_id=instance_id, 
                model_name=model_name, 
                rag_source=selected_rag_source,
                output_container=chat_container
            )
        run_end = time.time()
        
        # Reset state
        st.session_state.is_running = False
        st.session_state.last_run_result = (final_state, final_iter_count)
        
        # Add to history
        if final_state and not is_fatal:
            duration = run_end - run_start
            st.session_state["execution_times"].append(duration)
            
            # Use the captured transcript as the base content
            assistant_content = captured_transcript
            
            # Additional fallback if transcript is empty but we have content
            if not assistant_content:
                assistant_content = final_state.chosen_query or "No output generated."

            msg_entry = {
                "role": "assistant",
                "content": assistant_content,
                "sql": final_state.chosen_query
            }
            
            # Prep Data Preview
            if final_state.execution_result and final_state.execution_result.rows:
                if hasattr(final_state.execution_result, "columns") and final_state.execution_result.columns:
                    cols = final_state.execution_result.columns
                else:
                    cols = [f"Col {i}" for i in range(len(final_state.execution_result.rows[0]))]
                msg_entry["data"] = pd.DataFrame(final_state.execution_result.rows, columns=cols)
            
            st.session_state.messages.append(msg_entry)
            st.rerun() # Refresh to show in history
        else:
            # Capture specific error if possible
            err_text = "Analysis failed or encountered a fatal error."
            if final_state and final_state.error_message:
                err_text = f"❌ Error: {final_state.error_message}"
            elif final_state and final_state.chosen_query and "ERROR:" in final_state.chosen_query:
                err_text = f"❌ {final_state.chosen_query}"
            
            # Display error inline WITHOUT rerunning to preserve the "Thinking..." logs
            st.error(err_text)
            
            # Also store in session for history
            st.session_state.messages.append({
                "role": "assistant",
                "content": err_text,
                "is_error": True
            })
            # DO NOT rerun here - let the logs remain visible

    # INTERACTIVE VISUALIZATION BUTTON
    # Check if the last run produced a recommendation
    persisted_res = st.session_state.get("last_run_result")
    if persisted_res and not st.session_state.is_running:
        final_state, _ = persisted_res
        # Only show button if we haven't shown it yet (how to track? see if last msg has chart?)
        # Better: check if final_state has valid recommendation
        if final_state and getattr(final_state, "viz_recommendation", None):
            rec = final_state.viz_recommendation
            if rec.get("recommended"):
                st.markdown("---")
                col1, col2 = st.columns([0.2, 0.8])
                if col1.button("📊 Show Chart", key=f"viz_btn_{final_state.instance_id}", type="primary"):
                    # Append chart message to history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Here is the **{rec.get('chart_type', 'chart')}** visualization you requested.",
                        "has_chart": True,
                        "chart_data": final_state.execution_result,
                        "query": final_state.user_query
                    })
                    # Clear recommendation so button disappears on rerun
                    final_state.viz_recommendation = None
                    st.rerun()

# --- Chat Input for Single Task ---
if not st.session_state.is_running:
    
    # Display selected question for reference (since chat_input can't be pre-filled)
    if st.session_state.get("draft_question"):
        st.info(f"**Selected Question**: {st.session_state.draft_question}")
        
    if prompt := st.chat_input("Ask anything"):
        # Use prompt directly
        instance_id = st.session_state.selected_task_id
        db_name = task_options.get(instance_id, {}).get("db", "unknown")
        
        # Add to history
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt.strip(),
            "iid": instance_id,
            "db": db_name
        })
        
        st.session_state.active_question = prompt.strip()
        st.session_state.is_running = "single"
        st.rerun()
