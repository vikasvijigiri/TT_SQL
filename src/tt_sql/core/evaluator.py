import os
import sys
import subprocess
import re
import streamlit as st

def run_evaluation(target_instance_id=None, show_ui=True, user_query=None, result_dir_override=None, model_name_override=None):
    """Runs the external evaluation script and returns the score."""
    try:
        # project_root is parent of src
        current_dir = os.path.dirname(os.path.abspath(__file__)) # src/tt_sql/core
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir))) 

        # Eval script is at gold/evaluate.py
        eval_script = os.path.join(project_root, "gold", "evaluate.py")
        
        cmd = [sys.executable, eval_script]
        
        if result_dir_override:
             # Batch runner temporary eval
             cmd.extend(["--result_dir", result_dir_override, "--mode", "exec_result", "--gold_dir", os.path.join(project_root, "gold")])
        else:
             # Full model evaluation (Calc Final Accuracy button)
             model_arg = model_name_override or st.session_state.get("settings_model", "default_model")
             res_dir = os.path.join(project_root, "results", model_arg.replace("/", "_").replace(":", "_"), "csv")
             cmd.extend(["--result_dir", res_dir, "--mode", "exec_result", "--gold_dir", os.path.join(project_root, "gold")])
             
             if show_ui:
                 st.info(f"Running evaluation for model: {model_arg}")

        # Run command
        result = subprocess.run(
            cmd, 
            cwd=project_root, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace'
        )
        
        score = 0.0
        if result.returncode == 0:
            # Extract score using Regex from gold/evaluate.py output: "Final score: 0.XXXXXXXX"
            match = re.search(r"Final score:\s*([0-9.]+)", result.stdout)
            
            if match:
                # Convert fraction to percentage
                score = float(match.group(1)) * 100.0
                
                # --- RAG Learning Logic ---
                if score == 100 and target_instance_id and user_query:
                    try:
                        # Optional: Trigger RAG learning
                        # This creates circular imports if we import agents here.
                        # Move this logic OUT of the evaluator if possible, or keep purely local import.
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
