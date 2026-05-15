import yaml
import os
import json
from backend.app.utils.llm import LLMClient
from backend.app.utils.logger import logger
from backend.app.core.config import PROMPTS_DIR, LOGS_DIR

class PromptEvolver:
    """
    An agent that continuously monitors logs and refines system prompts 
    by extracting generic, non-hardcoded reasoning patterns.
    """
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.prompt_dir = PROMPTS_DIR

    def evolve_prompts(self, log_file: str = None):
        if log_file is None:
            log_file = str(LOGS_DIR / "major_failures.log")
            
        logger.info(f"PromptEvolver: Analyzing logs from {log_file}...")
        
        if not os.path.exists(log_file):
            logger.warning("No log file found to evolve from.")
            return

        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            log_content = f.read()[-5000:] # Take last 5k chars for context

        # 1. Distill Generic Rules from Logs
        system_prompt = "You are a Lead Database Architect and Meta-Optimization Agent. Your goal is to extract high-level, generic reasoning rules from failure logs to harden the Text2SQL pipeline."
        user_prompt = f"""
        Analyze the following execution logs and extract GENERIC reasoning rules to prevent recurring failures.
        
        ### CONSTRAINTS:
        - NEVER hardcode specific database entities (table names, column names, or literal values).
        - ALLOWED: Dialect names (Snowflake, BigQuery, SQLite) and their specific technical functions (e.g., LATERAL FLATTEN, ILIKE).
        - ABSOLUTELY FORBIDDEN: Entity names like "PATENTS", "assignee", "SF_BQ...", or specific country codes.
        - ABSTRACTION: If a failure happened on a specific table, extract the STRUCTURAL REASON (e.g., "When handling JSON arrays, use the dialect-specific unnesting function") rather than naming the table.
        - Rules must be purely reasoning-based, architectural, and dialect-aware.
        
        ### LOGS:
        {log_content}
        
        ### OUTPUT FORMAT (JSON):
        {{
            "rules": [
                {{
                    "target_agent": "sql_generator|self_corrector|schema_linker",
                    "rule_description": "A concise, generic reasoning rule."
                }}
            ]
        }}
        """
        
        try:
            distilled = self.llm.generate_json(system_prompt, user_prompt)
            if distilled and "rules" in distilled:
                for item in distilled["rules"]:
                    rule = item["rule_description"]
                    
                    # 1. Hardcode-Detector Audit (Reasoning-aware)
                    audit_prompt = f"""
                    Determine if the following rule is DATA-AGNOSTIC or HARDCODED.
                    Respond in JSON format:
                    {{
                      "reasoning": "Why is this rule generic or hardcoded?",
                      "status": "GENERIC" or "HARDCODED"
                    }}
                    
                    RULE: {rule}
                    """
                    audit_raw = self.llm.generate("", audit_prompt).strip()
                    try:
                        import json
                        # Handle potential markdown wrapping
                        clean_json = audit_raw.replace("```json", "").replace("```", "").strip()
                        audit_data = json.loads(clean_json)
                        audit_status = audit_data.get("status", "HARDCODED")
                        audit_reason = audit_data.get("reasoning", "No reason provided.")
                    except:
                        audit_status = "GENERIC" if "GENERIC" in audit_raw.upper() else "HARDCODED"
                        audit_reason = "Fallback parsing used."
                    
                    if audit_status == "HARDCODED":
                        logger.warning(f"PromptEvolver: Rejected rule: {rule[:50]}... | Reason: {audit_reason}")
                        continue
                        
                    logger.success(f"PromptEvolver: Accepted rule: {rule[:50]}...")
                    self._apply_rule(item["target_agent"], rule)
        except Exception as e:
            logger.error(f"PromptEvolver failed to distill rules: {e}")

    def _apply_rule(self, agent: str, rule: str):
        prompt_path = self.prompt_dir / f"{agent}.yaml"
        if not prompt_path.exists(): return

        with open(prompt_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if 'messages' not in data or not data['messages']:
            return
            
        system_msg = data['messages'][0]['content']
        
        # 1. Basic String Match
        if rule.lower().strip() in system_msg.lower():
            return
            
        # 2. Semantic De-duplication Check
        dedup_prompt = f"""
        Does the following EXISTING SYSTEM PROMPT already contain or cover the meaning of the NEW RULE?
        Answer with "YES" if it is covered, or "NO" if it is a truly new addition.
        
        ### EXISTING PROMPT:
        {system_msg} 
        
        ### NEW RULE:
        {rule}
        
        Answer (YES/NO):
        """
        
        try:
            is_covered = self.llm.generate("", dedup_prompt).strip().upper()
            if "YES" in is_covered:
                logger.info(f"PromptEvolver: Rule already covered semantically in {agent}.yaml. Skipping.")
                return
        except: pass

        learning_header = "\n### DYNAMIC LEARNINGS (AUTONOMOUSLY EVOLVED):\n"
        if learning_header not in system_msg:
            new_content = system_msg + learning_header + f"- {rule}\n"
        else:
            new_content = system_msg + f"- {rule}\n"
            
        data['messages'][0]['content'] = new_content
        
        with open(prompt_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)
            
        logger.info(f"PromptEvolver: Updated {agent}.yaml with new rule: {rule}")
