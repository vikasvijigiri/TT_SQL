import os
import json
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as plt_sns
import matplotlib
matplotlib.use('Agg')  # For headless execution without crashing on GUI threads

from agent.app.utils.logger import logger
from agent.app.core.config import DAB_RESULTS_DIR

PLOTS_DIR = DAB_RESULTS_DIR / "plots"

def generate_analytics_report(results: List[Dict[str, Any]]) -> None:
    """
    Consumes the pipeline evaluation results, generates matplotlib charts,
    and updates the dynamic markdown analytics dashboard.
    """
    if not results:
        return
        
    try:
        PLOTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Enrich results with PipelineRun database records to get accurate smartness/attempts metrics
        try:
            from agent.app.db.database import SessionLocal
            from agent.app.db.models import PipelineRun
            db = SessionLocal()
            try:
                for r in results:
                    instance_id = r.get("instance_id") or f"{r['dataset']}_q{r['query_id']}"
                    # Load the latest PipelineRun for this instance
                    run_record = db.query(PipelineRun).filter(
                        PipelineRun.instance_id == instance_id,
                        PipelineRun.dataset == r["dataset"]
                    ).order_by(PipelineRun.timestamp.desc()).first()
                    if run_record:
                        r.setdefault("attempts", run_record.total_attempts)
                        r.setdefault("score", run_record.smartness_score)
                        r.setdefault("verdict", run_record.final_verdict)
                        r.setdefault("latency", run_record.total_latency_s)
                        # Parse error_categories if they exist, e.g. from evolution_json
                        try:
                            if run_record.evolution_json:
                                ev_list = json.loads(run_record.evolution_json)
                                errors = [
                                    step.get("error_category")
                                    for step in ev_list
                                    if step.get("error_category")
                                ]
                                if errors:
                                    r.setdefault("error_categories", errors)
                        except Exception:
                            pass
            finally:
                db.close()
        except Exception as db_err:
            logger.warning(f"Failed to enrich results with database PipelineRun info: {db_err}")

        # Fallback mappings for standard keys
        for r in results:
            if "elapsed_s" in r:
                r.setdefault("latency", r["elapsed_s"])
            if "status" in r:
                r.setdefault("verdict", r["status"])

        # 1. Prepare Data
        df = pd.DataFrame(results)
        
        # Ensure standard columns exist even if some runs crashed early
        for col in ["latency", "attempts", "score", "verdict", "error_categories", "passed", "dataset"]:
            if col not in df.columns:
                df[col] = None if col in ["verdict", "error_categories"] else 0
                
        df['passed'] = df['passed'].fillna(False).astype(bool)
        df['latency'] = pd.to_numeric(df['latency'], errors='coerce').fillna(0)
        df['attempts'] = pd.to_numeric(df['attempts'], errors='coerce').fillna(0)
        df['score'] = pd.to_numeric(df['score'], errors='coerce').fillna(0)
        
        # 2. Generate Plots
        plt_sns.set_theme(style="whitegrid", palette="pastel")
        
        # Plot A: Latency Distribution (Passed vs Failed)
        plt.figure(figsize=(8, 5))
        pal = {True: "#2ecc71", False: "#e74c3c", "True": "#2ecc71", "False": "#e74c3c"}
        plt_sns.boxplot(x="passed", y="latency", hue="passed", data=df, palette=pal, legend=False)
        plt.title("Latency Distribution: Success vs. Failure", fontsize=14)
        plt.xlabel("Query Passed", fontsize=12)
        plt.ylabel("Latency (Seconds)", fontsize=12)
        latency_plot_path = PLOTS_DIR / "latency_dist.png"
        plt.tight_layout()
        plt.savefig(latency_plot_path, dpi=150)
        plt.close()
        
        # Plot B: Fallback Attempts Distribution
        plt.figure(figsize=(8, 5))
        attempts_counts = df.groupby(['attempts', 'passed']).size().unstack(fill_value=0)
        # Ensure both True and False columns exist for plotting
        if True not in attempts_counts.columns: attempts_counts[True] = 0
        if False not in attempts_counts.columns: attempts_counts[False] = 0
        attempts_counts.plot(kind='bar', stacked=True, color={True: "#2ecc71", False: "#e74c3c"}, ax=plt.gca())
        plt.title("Fallback Attempts Utilized", fontsize=14)
        plt.xlabel("Number of Attempts", fontsize=12)
        plt.ylabel("Number of Queries", fontsize=12)
        plt.legend(title="Passed", labels=["Failed", "Passed"])
        attempts_plot_path = PLOTS_DIR / "attempts_dist.png"
        plt.tight_layout()
        plt.savefig(attempts_plot_path, dpi=150)
        plt.close()
        
        # Plot C: Smartness Score Distribution
        plt.figure(figsize=(8, 5))
        plt_sns.histplot(df['score'], bins=10, kde=True, color="#3498db")
        plt.title("Smartness Score Distribution", fontsize=14)
        plt.xlabel("Smartness Score (0-100)", fontsize=12)
        plt.ylabel("Frequency", fontsize=12)
        score_plot_path = PLOTS_DIR / "score_dist.png"
        plt.tight_layout()
        plt.savefig(score_plot_path, dpi=150)
        plt.close()
        
        # Plot D: Error Category Breakdown
        plt.figure(figsize=(8, 5))
        all_errors = []
        for errors in df['error_categories'].dropna():
            if isinstance(errors, list):
                all_errors.extend(errors)
        
        if all_errors:
            error_series = pd.Series(all_errors).value_counts()
            plt.pie(error_series, labels=error_series.index, autopct='%1.1f%%', colors=plt_sns.color_palette("rocket"))
            plt.title("Error Categories Encountered", fontsize=14)
            error_plot_path = PLOTS_DIR / "error_dist.png"
            plt.tight_layout()
            plt.savefig(error_plot_path, dpi=150)
            plt.close()
        else:
            error_plot_path = None
            
        # Plot E: Success Rate by Dataset
        plt.figure(figsize=(10, 6))
        dataset_rates = df.groupby('dataset')['passed'].mean() * 100
        plt_sns.barplot(x=dataset_rates.index, y=dataset_rates.values, palette="viridis")
        plt.title("Pass Rate by Dataset", fontsize=14)
        plt.xlabel("Dataset", fontsize=12)
        plt.ylabel("Pass Rate (%)", fontsize=12)
        plt.xticks(rotation=45)
        dataset_plot_path = PLOTS_DIR / "dataset_rates.png"
        plt.tight_layout()
        plt.savefig(dataset_plot_path, dpi=150)
        plt.close()

        # 3. Generate Markdown Dashboard
        overall_pass_rate = df['passed'].mean() * 100
        total_queries = len(df)
        avg_latency = df['latency'].mean()
        avg_score = df['score'].mean()
        
        dashboard_md = f"""# Pipeline Analytics Dashboard

> [!NOTE]
> This dashboard is dynamically generated by the `AnalyticsEngine` after every execution. It provides a highly detailed, data-driven overview of the pipeline's performance.

## Key Performance Indicators (KPIs)
- **Total Queries Executed:** {total_queries}
- **Overall Pass Rate:** {overall_pass_rate:.1f}%
- **Average Latency:** {avg_latency:.2f} seconds
- **Average Smartness Score:** {avg_score:.1f}/100

---

## 1. Success Rate by Dataset
Are there specific databases the agent struggles with?
![Pass Rate by Dataset]({dataset_plot_path.resolve().as_uri()})

## 2. Latency Analysis
Does the agent take longer when it fails?
![Latency Distribution]({latency_plot_path.resolve().as_uri()})

## 3. Fallback Attempts (Self-Corrector)
How many times did the `SELF_CORRECTOR` loop engage before a query succeeded or stagnated?
![Fallback Attempts]({attempts_plot_path.resolve().as_uri()})

## 4. Smartness Scoring
The Orchestrator's internal confidence scoring spread across the batch.
![Smartness Distribution]({score_plot_path.resolve().as_uri()})
"""
        
        if error_plot_path:
            dashboard_md += f"""
## 5. Error Breakdown
What exact categories (Execution, Hallucination, Quality) are failing the queries?
![Error Distribution]({error_plot_path.resolve().as_uri()})
"""

        dashboard_path = DAB_RESULTS_DIR / "pipeline_analytics_dashboard.md"
        with open(dashboard_path, "w", encoding="utf-8") as f:
            f.write(dashboard_md)
            
        logger.success(f"Dynamic Analytics Dashboard generated at: {dashboard_path}")
        
    except Exception as e:
        logger.error(f"AnalyticsEngine failed to generate report: {e}")
