import streamlit as st
import json
import os
import glob
import pandas as pd
import io
from pathlib import Path

# Custom styles for comparison
st.markdown("""
<style>
    .comparison-header {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 1.2rem;
        margin-bottom: 15px;
        padding-bottom: 8px;
        border-bottom: 2px solid #3498db;
        color: #3498db;
    }
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e5e5e5;
    }
</style>
""", unsafe_allow_html=True)

def find_latest_log():
    log_dir = Path(__file__).resolve().parent.parent.parent / "JSON_logs"
    if not log_dir.exists():
        return None
    files = glob.glob(str(log_dir / "failures_detailed_*.json"))
    if not files:
        return None
    # Sort by modification time to get the latest
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def load_log(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def safe_read_csv(csv_str):
    if not csv_str or not isinstance(csv_str, str) or csv_str.strip() == "":
        return None
    try:
        df = pd.read_csv(io.StringIO(csv_str))
        # Strip whitespace from column names
        df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
        return df
    except Exception:
        return None

def display_styled_df(df, container=None):
    if container is None:
        container = st
        
    if df is not None:
        # Convert to HTML with colorful styling
        html = df.to_html(index=False, classes='nquiry-table')
        styled_html = f"""
        <style>
            .nquiry-table-container {{
                width: 100%;
                overflow-x: auto;
                margin-top: 10px;
                margin-bottom: 20px;
                border-radius: 12px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.05);
                border: 1px solid #e5e5e5;
            }}
            .nquiry-table {{
                width: 100%;
                border-collapse: collapse;
                font-family: 'Inter', sans-serif;
                background-color: white;
            }}
            .nquiry-table th {{
                background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
                color: white;
                text-align: left;
                padding: 12px 15px;
                font-weight: 600;
                font-size: 0.85rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .nquiry-table td {{
                padding: 10px 15px;
                border-bottom: 1px solid #f0f0f0;
                color: #333;
                font-size: 0.8rem;
            }}
            .nquiry-table tr:last-child td {{
                border-bottom: none;
            }}
            .nquiry-table tr:nth-child(even) {{
                background-color: #fcfcfc;
            }}
            .nquiry-table tr:hover {{
                background-color: #f1f4f9;
            }}
        </style>
        <div class="nquiry-table-container">{html}</div>
        """
        container.markdown(styled_html, unsafe_allow_html=True)
    else:
        container.info("No data available.")

st.title("🔍 Failure Analysis Dashboard")
st.caption("Side-by-side comparison of generated results vs. ground truth.")

latest_log_path = find_latest_log()

if not latest_log_path:
    st.warning("No failure logs found. Please run the collection utility.")
    st.stop()

# Load data
log_data = load_log(latest_log_path)
log_filename = os.path.basename(latest_log_path)

# Sidebar
st.sidebar.title("Navigation")
st.sidebar.markdown(f"**Log File**: `{log_filename}`")

# Create lookup map
failure_map = {item['instance_id']: item for item in log_data}
task_ids = list(failure_map.keys())

# --- Summary Table ---
st.markdown("### 📊 Failure Summary")
summary_df = pd.DataFrame([
    {"ID": item['instance_id'], "Question": item['question'], "DB": item.get('db', 'Spider')} 
    for item in log_data
])
st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.divider()

# Selector
selected_id = st.sidebar.selectbox("Jump to Instance ID", task_ids)
item = failure_map[selected_id]

# Information Section
st.markdown(f"### 📋 Analysis: {selected_id}")
st.info(item.get('question', 'N/A'))

# SQL Comparison
st.markdown('<div class="comparison-header">📜 SQL Comparison</div>', unsafe_allow_html=True)
sql_col1, sql_col2 = st.columns(2)

with sql_col1:
    st.subheader("🤖 Generated SQL")
    if item.get('generated_sql'):
        st.code(item['generated_sql'], language="sql")
    else:
        st.error("No SQL generated.")

with sql_col2:
    st.subheader("🏆 Gold SQL")
    if item.get('gold_sql'):
        st.code(item['gold_sql'], language="sql")
    else:
        st.warning("Gold SQL missing.")

st.divider()

# Data Comparison
st.markdown('<div class="comparison-header">📊 Data Comparison</div>', unsafe_allow_html=True)
data_col1, data_col2 = st.columns(2)

gen_df = safe_read_csv(item.get('csv_result'))
gold_df = safe_read_csv(item.get('gold_csv_result'))

with data_col1:
    st.subheader("🤖 Generated Output")
    display_styled_df(gen_df)
    if gen_df is not None:
        st.caption(f"Rows: {len(gen_df)}")

with data_col2:
    st.subheader("🏆 Ground Truth")
    display_styled_df(gold_df)
    if gold_df is not None:
        st.caption(f"Rows: {len(gold_df)}")

# Stats in sidebar
st.sidebar.divider()
st.sidebar.metric("Total Failures", len(log_data))
if st.sidebar.button("🔄 Refresh"):
    st.rerun()
