import json
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

from agent.services.logger import logger
from agent.services.llm import LLMClient
from agent.app.core.config import get_active_results_dir, get_active_evals_dir, get_active_knowledge_dir
from agent.app.core.rules.dynamic_rule_store import DynamicRuleStore

class SuggestedRule(BaseModel):
    rule_title: str = Field(description="A short, descriptive title for the rule.")
    generic_rule: str = Field(description="The generic rule text.")
    intent_pattern: str = Field(description="Regex pattern for when this rule applies.")
    category: str = Field(description="Category of the rule (e.g. schema, joins, filters).")

class Reflection(BaseModel):
    react_analysis: str = Field(description="Step-by-step reflection on what went wrong across the failures, why the pipeline struggled, and what core roadblocks exist.")
    overall_smartness_rating: float = Field(description="Rate the overall intelligence and adaptability of the pipeline out of 100 based on this batch run. Every failure is a setback. Penalize silly mistakes heavily.")
    identified_roadblocks: List[str] = Field(description="List of specific, recurring error patterns or conceptual roadblocks.")
    suggested_rules: List[SuggestedRule] = Field(description="List of new rules to inject.")

class PostBatchMetaLearner:
    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client or LLMClient(temperature=0.2)
        self.store = DynamicRuleStore()

    def run_post_batch_analysis(self) -> None:
        logger.info("\n==================================================")
        logger.info("Initializing Post-Batch Meta-Learner Reflection...")
        logger.info("==================================================")
        
        report_path = get_active_evals_dir() / "accuracy_report.json"
        if not report_path.exists():
            logger.error("No accuracy report found. Skipping Meta-Learner.")
            return

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
            
        failed_queries = []
        for db, db_data in report.get("per_dataset", {}).items():
            for qdata in db_data.get("queries", []):
                # We consider it a failure if it didn't pass at k
                if not qdata.get("passed_atk", False):
                    failed_queries.append({
                        "dataset": db,
                        "query_id": qdata["query_id"],
                        "error": qdata.get("reason", "Unknown error")
                    })

        if not failed_queries:
            logger.success("No failures to analyze! Pipeline achieved 100%.")
            return

        logger.info(f"Meta-Learner found {len(failed_queries)} failed queries. Preparing logs for analysis...")
        
        # Gather logs (up to 15 failures to avoid context overflow)
        logs_summary = []
        for fq in failed_queries[:15]:
            md_path = get_active_results_dir() / fq["dataset"] / f"query{fq['query_id']}.md"
            log_tail = ""
            if md_path.exists():
                with open(md_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                    log_tail = content[-6000:] # last 6k chars to capture ReAct and errors
            logs_summary.append(f"- FAILURE: {fq['dataset']} Q{fq['query_id']} ---\nError: {fq['error']}\nLog Tail:\n{log_tail}\n")

        system_prompt = (
            "You are the Post-Batch Meta-Learner for an advanced Text-to-SQL AI pipeline.\n"
            "The pipeline just completed a batch run. Several queries failed.\n"
            "Your job is to read the failure logs, reflect (ReAct) on the roadblocks, and extract actionable rules.\n"
            "You must rate the pipeline's overall smartness based on the severity of the failures (0-100).\n"
            "Every failure is a setback. If the pipeline made silly mistakes, score it negatively in that respect.\n"
            "Based on the score, we want it to only get better. Extract corrections/suggestions as new rules.\n"
            "Output your analysis in JSON format matching the requested schema."
        )

        user_prompt = "Here are the failure logs from the recent run:\n\n" + "\n".join(logs_summary)

        logger.info("Sending failure logs to LLM for Meta-Reflection...")
        try:
            reflection_obj = self.llm.generate_structured_output(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=Reflection
            )
        except AttributeError:
            # Fallback if the method name is actually generate_structured
            reflection_obj = self.llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=Reflection
            )
            
        logger.info(f"\n[META-LEARNER ReAct Analysis]\n{reflection_obj.react_analysis}")
        logger.info(f"\n[PIPELINE SMARTNESS RATING]: {reflection_obj.overall_smartness_rating}/100")
        
        # Save reflection to memory
        get_active_knowledge_dir().mkdir(parents=True, exist_ok=True)
        meta_log_path = get_active_knowledge_dir() / "meta_reflections.jsonl"
        with open(meta_log_path, "a", encoding="utf-8") as f:
            f.write(reflection_obj.model_dump_json() + "\n")
        logger.info(f"Saved Meta-Reflection to {meta_log_path}")
        
        # Inject Rules
        added_rules = 0
        for rule in reflection_obj.suggested_rules:
            # Ensure required fields are present
            title = rule.rule_title
            generic_rule = rule.generic_rule
            intent = rule.intent_pattern
            cat = rule.category
            
            lid = self.store.add_rule(
                rule_title=title,
                generic_rule=generic_rule,
                intent_pattern=intent,
                category=cat,
                source_failure="post_batch_meta_learner",
                db_name="ALL",
                llm_client=self.llm,
            )
            if lid:
                self.store.activate_candidates([lid])
                logger.success(f"Added new rule from Meta-Learner: {title}")
                added_rules += 1
                
        logger.info(f"Meta-Learner injected {added_rules} new rules into DynamicRuleStore.")
        
        self._update_dataset_error_ledgers(failed_queries)
        
        logger.info("==================================================\n")

    def _update_dataset_error_ledgers(self, failed_queries: List[dict]) -> None:
        from collections import defaultdict
        
        # Group failures by dataset
        failures_by_db = defaultdict(list)
        for fq in failed_queries:
            failures_by_db[fq["dataset"]].append(f"Q{fq['query_id']}: {fq['error']}")
            
        for db, errors in failures_by_db.items():
            ledger_path = get_active_knowledge_dir() / f"{db}_failures_ledger.md"
            existing_ledger = ""
            if ledger_path.exists():
                existing_ledger = ledger_path.read_text(encoding="utf-8")
                
            system_prompt = (
                f"You are the pipeline's memory consolidation module for the '{db}' database.\n"
                "Your job is to read the existing Failure Ledger for this specific database and weave in the new errors.\n"
                "Keep the ledger highly compressed (MAX 400 WORDS). Use concise bullet points.\n"
                "Focus purely on the exact technical roadblocks, schema quirks, and query pitfalls for THIS database.\n"
                "Remove redundant points and summarize efficiently. Output ONLY the raw markdown ledger."
            )
            
            user_prompt = (
                f"=== EXISTING {db.upper()} LEDGER ===\n{existing_ledger if existing_ledger else 'No existing ledger. This is the first run.'}\n\n"
                f"=== NEW FAILURES IN RECENT RUN ===\n" + "\n".join(errors) + "\n\n"
                "Please generate the updated, compressed Dataset Error Ledger."
            )
            
            try:
                logger.info(f"Updating Error Ledger for database: {db}...")
                updated_ledger = self.llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
                # Remove any <think> tags just in case
                import re
                updated_ledger = re.sub(r"<think>.*?</think>", "", updated_ledger, flags=re.S).strip()
                
                ledger_path.write_text(updated_ledger, encoding="utf-8")
                logger.success(f"Ledger updated and saved to {ledger_path}")
            except Exception as e:
                logger.error(f"Failed to update ledger for {db}: {e}")
