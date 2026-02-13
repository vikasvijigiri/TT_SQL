"""
Narrator Agent — LLM-powered, domain-aware pipeline narrator.
Provides professional streaming commentary + data visualization in the Streamlit UI.
"""
import json
import streamlit as st
from tt_sql.core.llm_service import LLMService
from tt_sql.core.prompt_loader import PromptLoader


class NarratorAgent:
    """
    LLM-powered narrator that provides professional, domain-aware commentary
    and auto-generates appropriate visualizations for query results.
    """

    def __init__(self, llm_service: LLMService):
        self.llm = llm_service
        self.prompt_loader = PromptLoader()

    def _narrate(self, stage: str, user_question: str, context_data: str) -> str:
        """Call the LLM to generate a narration for the given pipeline stage."""
        try:
            messages = self.prompt_loader.load_prompt(
                "narrator",
                stage=stage,
                user_question=user_question,
                context_data=context_data,
            )
            response = self.llm.get_completion(messages, temperature=0.3, max_tokens=512)
            if not response:
                if stage in ["Wrapping Up", "Conclusion Summary", "FINAL_SILENT_SUMMARY"]:
                    return ""
                return f"**{stage}**\n\n*Processing...*\n\n---"
            
            # CLEANER: strip out any headers the LLM might have generated anyway
            text = response.strip()
            import re
            
            # 1. Remove leading stage name variations specific to this stage
            pattern = r'(?i)^\s*(\**|#+)?\s*' + re.escape(stage) + r'[:\s\**]*\s*\n*'
            text = re.sub(pattern, '', text)
            
            # 2. Aggressive search & destroy for ending stage headers
            text = re.sub(r'(?i)^\s*(\**|#+)?\s*(Wrapping\s+Up|Conclusion\s+Summary|Final\s+Answer|Summary)\s*[:\s\**]*\s*$', '', text, flags=re.MULTILINE)
            
            # 3. Remove ANY markdown header lines (lines starting with #)
            text = re.sub(r'^\s*#+.*$', '', text, flags=re.MULTILINE)
            
            # 4. Remove Setext style headers (lines consisting only of --- or ===)
            text = re.sub(r'^\s*[-=]{3,}\s*$', '', text, flags=re.MULTILINE)
            
            text = text.strip()

            # Guard: ensure completion
            if text and not text.endswith(('---', '.', '!', '?', '*', '`')):
                text += "."
            
            # PREPEND STAGE NAME PROGRAMMATICALLY (Except for Ending Stages)
            if stage in ["Wrapping Up", "Conclusion Summary", "FINAL_SILENT_SUMMARY"]:
                final_text = text
            else:
                final_text = f"**{stage}**\n\n{text}"
            return final_text
        except Exception as e:
            # Fallback: never crash the pipeline over narration
            from tt_sql.core.logger import Logger
            Logger.log(f"Narrator Error: {e}", level="ERROR")
            if "KeyError" in str(e):
                 Logger.log("Hint: Prompt formatting failed. Check for unescaped curly braces in content.", level="ERROR")
            return f"**{stage}**\n\n*Analyzing data... (Error: {str(e)})*\n\n---"

    # ─── STAGE NARRATIONS ─────────────────────────────────────

    def narrate_opening(self, question: str) -> str:
        """Opening narration — what the question is about."""
        return self._narrate(
            stage="Asking nQuirer",
            user_question=question,
            context_data="Opening stage. Identify the business domain, explain the goal, and set expectations for the stakeholder.",
        )

    def narrate_schema(self, schema_info: dict, db_name: str) -> str:
        """After schema analysis."""
        table_names = list(schema_info.keys()) if schema_info else []
        ctx = f"Database: {db_name}\nTables found ({len(table_names)}): {', '.join(table_names[:20])}"
        if len(table_names) > 20:
            ctx += f" ... and {len(table_names) - 20} more"
        return self._narrate(
            stage="Finding Data",
            user_question="",
            context_data=ctx,
        )

    def narrate_intent(self, intent: str, complexity: str) -> str:
        """After intent classification."""
        ctx = f"Intent: {intent}\nComplexity: {complexity}"
        return self._narrate(
            stage="Understanding Intent",
            user_question="",
            context_data=ctx,
        )

    def narrate_tables(self, relevant_tables: list) -> str:
        """After context enrichment."""
        ctx = f"Relevant tables selected: {', '.join(relevant_tables)}" if relevant_tables else "No specific tables identified."
        return self._narrate(
            stage="Selecting Sources",
            user_question="",
            context_data=ctx,
        )

    def narrate_plan(self, plan_steps: list) -> str:
        """After step-by-step planning."""
        if plan_steps:
            steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan_steps))
            ctx = f"Action plan:\n{steps_text}"
        else:
            ctx = "No explicit plan — proceeding with direct SQL generation."
        return self._narrate(
            stage="Planning",
            user_question="",
            context_data=ctx,
        )

    def narrate_sql(self, sql: str, attempt: int = 1) -> str:
        """After SQL generation."""
        if not sql or sql.startswith("ERROR:"):
            ctx = f"Working on the query — this is attempt {attempt}."
        else:
            # Focus on what the query does, not technical details
            ctx = f"The query has been built. It's designed to find the information you need from the database."
        return self._narrate(
            stage="Building Answer",
            user_question="",
            context_data=ctx,
        )

    def narrate_execution(self, execution_result) -> str:
        """After SQL execution — includes a result preview."""
        if not execution_result:
            return "*Executing query...*"
        if execution_result.error_message:
            ctx = f"Execution ERROR: {execution_result.error_message[:300]}"
        else:
            row_count = len(execution_result.rows) if execution_result.rows else 0
            col_count = len(execution_result.columns) if execution_result.columns else 0
            ctx = f"Rows: {row_count}, Columns: {col_count}, Execution time: {execution_result.execution_time_ms:.1f}ms"
            # Add preview
            if execution_result.rows and execution_result.columns:
                ctx += f"\nColumns: {execution_result.columns}"
                ctx += f"\nTop rows: {execution_result.rows[:3]}"
        return self._narrate(
            stage="Getting Results",
            user_question="",
            context_data=ctx,
        )

    def narrate_critic(self, is_valid: bool, feedback: str, attempt: int) -> str:
        """After critic validation."""
        if is_valid:
            ctx = f"Validation: PASSED on attempt {attempt}"
        else:
            ctx = f"Validation: FAILED on attempt {attempt}\nFeedback: {feedback[:300]}"
        return self._narrate(
            stage="Quality Check",
            user_question="",
            context_data=ctx,
        )

    def narrate_final(self, sql: str, execution_result, elapsed: float, is_valid: bool) -> str:
        """Final summary narration."""
        row_count = len(execution_result.rows) if execution_result and execution_result.rows else 0
        status = "Validated ✅" if is_valid else "Best effort ⚠️"
        ctx = f"Status: {status}\nTotal time: {elapsed:.1f}s\nResult rows: {row_count}\nSQL length: {len(sql or '')} chars\n\nInstruction: Conclude by asking if they want any more analytics, like plotting or exploratory analysis."
        return self._narrate(
            stage="FINAL_SILENT_SUMMARY",
            user_question="",
            context_data=ctx,
        )

    # ─── DATA VISUALIZATION ──────────────────────────────────

    def assess_visualization_needs(self, execution_result, user_question: str) -> dict:
        """
        Analyzes results to see if they should be visualized.
        Returns dict with keys: 'recommended' (bool), 'chart_type' (str), 'reason' (str).
        """
        if not execution_result or not execution_result.rows or not execution_result.columns:
            return {"recommended": False, "reason": "No data"}

        import pandas as pd
        cols = execution_result.columns
        rows = execution_result.rows
        df = pd.DataFrame(rows, columns=cols)

        # Skip visualization for single-value results or very wide tables
        if len(df) < 2:
             return {"recommended": False, "reason": "Too few rows"}
        if len(df.columns) > 15:
             return {"recommended": False, "reason": "Too many columns"}

        # Ask LLM what chart type to use
        chart_type = self._pick_chart_type(df, user_question)
        
        if chart_type and chart_type != "table":
            return {"recommended": True, "chart_type": chart_type, "reason": f"Data suitable for {chart_type} chart"}
        
        return {"recommended": False, "reason": "Table preferred"}

    def generate_plot_for_ui(self, execution_result, user_question: str, container):
        """
        Renders the visualization immediately (for use after user approval).
        """
        if not execution_result: return
        
        import pandas as pd
        df = pd.DataFrame(execution_result.rows, columns=execution_result.columns)
        
        # We re-run pick chart type or trust the caller? 
        # For safety, let's re-assess briefly or just default to bar/line smarts
        chart_type = self._pick_chart_type(df, user_question)
        
        try:
            if chart_type == "bar":
                self._render_bar_chart(df, container)
            elif chart_type == "line":
                self._render_line_chart(df, container)
            elif chart_type == "pie":
                self._render_pie_chart(df, container)
            else:
                self._render_styled_table(df, container)
        except Exception:
            self._render_styled_table(df, container)

    def _pick_chart_type(self, df, user_question: str) -> str:
        """Use LLM to pick the best visualization type."""
        import pandas as pd

        # Build a compact data summary for the LLM
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

        summary = (
            f"Question: {user_question}\n"
            f"Columns: {list(df.columns)}\n"
            f"Numeric columns: {numeric_cols}\n"
            f"Category columns: {non_numeric_cols}\n"
            f"Row count: {len(df)}\n"
            f"Sample row: {df.iloc[0].to_dict()}"
        )

        messages = [
            {"role": "system", "content": (
                "You are a data visualization expert. Given a query result, pick the BEST chart type. "
                "Reply with EXACTLY ONE word: bar, line, pie, or table. "
                "Rules:\n"
                "- bar: for comparing categories or ranked items\n"
                "- line: for time series or trends\n"
                "- pie: for proportions (only when <=8 categories)\n"
                "- table: when data is text-heavy or has many columns\n"
                "Reply with ONLY the chart type word, nothing else."
            )},
            {"role": "user", "content": summary},
        ]

        try:
            response = self.llm.get_completion(messages, temperature=0.0, max_tokens=10)
            chart = response.strip().lower().split()[0] if response else "table"
            if chart in ("bar", "line", "pie", "table"):
                return chart
            return "table"
        except Exception:
            return "table"

    def _render_bar_chart(self, df, container):
        """Render a Plotly bar chart."""
        import plotly.express as px
        import pandas as pd

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

        if not numeric_cols:
            self._render_styled_table(df, container)
            return

        x_col = non_numeric_cols[0] if non_numeric_cols else df.columns[0]
        y_col = numeric_cols[0]

        # Limit to top 20 for readability
        plot_df = df.head(20)

        fig = px.bar(
            plot_df, x=x_col, y=y_col,
            color_discrete_sequence=["#667eea"],
            title=f"{y_col} by {x_col}",
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
            margin=dict(l=40, r=20, t=50, b=40),
        )
        container.plotly_chart(fig, use_container_width=True)

    def _render_line_chart(self, df, container):
        """Render a Plotly line chart."""
        import plotly.express as px
        import pandas as pd

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

        if not numeric_cols:
            self._render_styled_table(df, container)
            return

        x_col = non_numeric_cols[0] if non_numeric_cols else df.index
        y_col = numeric_cols[0]

        fig = px.line(
            df, x=x_col, y=y_col,
            markers=True,
            color_discrete_sequence=["#764ba2"],
            title=f"{y_col} over {x_col}",
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
            margin=dict(l=40, r=20, t=50, b=40),
        )
        container.plotly_chart(fig, use_container_width=True)

    def _render_pie_chart(self, df, container):
        """Render a Plotly pie chart."""
        import plotly.express as px
        import pandas as pd

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

        if not numeric_cols or not non_numeric_cols:
            self._render_styled_table(df, container)
            return

        names_col = non_numeric_cols[0]
        values_col = numeric_cols[0]

        plot_df = df.head(8)  # Pie charts should be <=8 slices

        fig = px.pie(
            plot_df, names=names_col, values=values_col,
            title=f"{values_col} Distribution",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
        )
        container.plotly_chart(fig, use_container_width=True)

    def _render_styled_table(self, df, container):
        """Render a nicely styled dataframe."""
        container.dataframe(df, use_container_width=True, hide_index=True)
