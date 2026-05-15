import json
import os
import re
import yaml
import logging
from typing import List, Dict, Tuple
from pathlib import Path
from backend.app.utils.logger import logger

from backend.app.utils.prompt_loader import PromptLoader
from backend.app.core.config import MEMORY_DIR, LOGS_DIR, get_prompt_path

PROMPT_PATH = get_prompt_path("lesson_learner.yaml")

class DynamicRuleLearner:
    def __init__(self, dialect: str = "snowflake"):
        self.dialect = dialect.lower()
        self.dialect_memory_dir = MEMORY_DIR / "dialects"
        self.reasoning_memory_dir = MEMORY_DIR / "reasoning"
        self.success_memory_dir = MEMORY_DIR / "success"
        self.major_failures_log = LOGS_DIR / "major_failures.log"
        
        self.dialect_memory_dir.mkdir(parents=True, exist_ok=True)
        self.reasoning_memory_dir.mkdir(parents=True, exist_ok=True)
        self.success_memory_dir.mkdir(parents=True, exist_ok=True)
        self.major_failures_log.parent.mkdir(parents=True, exist_ok=True)
        
        self.major_logger = logging.getLogger("MAJOR_FAILURES")
        if not self.major_logger.handlers:
            handler = logging.FileHandler(str(self.major_failures_log))
            handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
            self.major_logger.addHandler(handler)
            self.major_logger.setLevel(logging.INFO)

    def analyze_and_learn(self, instance_id: str, error: str, correction_thought: str, attempts: int):
        """Learns from correction loops by distilling a generic rule."""
        is_minor, category, is_dialect_specific = self._classify_error(error)
        if is_minor:
            # Instead of just adding the thought, we DISTILL it into a crisp rule
            distilled_rule = self._distill_rule(category, error, correction_thought)
            self._add_rule(category, distilled_rule, is_dialect_specific)
        else:
            self._log_major_failure(instance_id, error, correction_thought, attempts)

    def analyze_success(self, instance_id: str, sql: str, thought: str):
        """Distills patterns from a successful execution."""
        # Only distill if it's a high-quality reasoning pattern
        if "grain" in thought.lower() or "determinism" in thought.lower() or "parallel" in thought.lower():
            distilled_rule = self._distill_rule("Reasoning Pattern", "Success Case", thought)
            self._add_rule("Reasoning Pattern", distilled_rule, False)

    def _distill_rule(self, category: str, error: str, thought: str) -> str:
        """Uses an LLM pass to extract a crisp, generic rule from a specific instance."""
        from backend.app.utils.llm import LLMClient
        llm = LLMClient()
        
        try:
            variables = {
                "CATEGORY": category,
                "ERROR": error,
                "THOUGHT": thought
            }
            messages = PromptLoader.load(PROMPT_PATH, variables=variables)
            
            system_prompt = next(m["content"] for m in messages if m["role"] == "system")
            user_prompt   = next(m["content"] for m in messages if m["role"] == "user")
            
            # We use a simple generate call here to avoid circular dependencies with models
            # Use a slightly cheaper model for distillation if available, otherwise default
            distilled = llm.generate(system_prompt, user_prompt).strip()
            # Strict cleaning: remove any conversational preambles
            for preamble in ["So the rule is", "So output:", "Distilled rule:", "So:", "Thus answer:", "So final:"]:
                if preamble in distilled: distilled = distilled.split(preamble)[-1]
            
            # Extract only the [CATEGORY] part onwards using greedy match
            match = re.search(r"(\[.*?\] .*)", distilled)
            if match:
                distilled = match.group(1).strip()
            
            # Final sanity check: if it still has too much text or looks like a paragraph, it failed
            if len(distilled) > 250 or distilled.count('.') > 2:
                return None
            
            # Basic cleanup
            distilled = "".join(c for c in distilled if c.isprintable()).replace('"', '').strip()
            return distilled
        except Exception as e:
            logger.warning(f"Distillation failed: {e}. Returning None.")
            return None

    def _classify_error(self, error: str) -> Tuple[bool, str, bool]:
        error_lower = error.lower()
        dialect_keywords = ["identifier", "ambiguous", "syntax", "unexpected", "date", "flatten", "variant", "lateral", "parse", "compilation"]
        if any(kw in error_lower for kw in dialect_keywords):
            return True, "Reasoning Pattern", True
        if "data quality fail" in error_lower or "0 rows" in error_lower or "determinism" in error_lower:
            return True, "Reasoning Pattern", False
        return False, "Major Failure", False

    def _add_rule(self, category: str, rule_text: str, is_dialect: bool):
        if not rule_text or "Generic logical correction" in rule_text:
            return
        sub_dir = self.dialect_memory_dir if is_dialect else self.reasoning_memory_dir
        file_name = f"{self.dialect}.yaml" if is_dialect else "generic.yaml"
        target_file = sub_dir / file_name
        lock_file = str(target_file) + ".lock"

        import time
        start_wait = time.time()
        while os.path.exists(lock_file) and (time.time() - start_wait < 5):
            time.sleep(0.1)

        try:
            with open(lock_file, "w") as f: f.write(str(os.getpid()))
            if not target_file.exists():
                with open(target_file, 'w', encoding='utf-8') as f: yaml.safe_dump([], f)
            
            with open(target_file, 'r', encoding='utf-8') as f:
                rules = yaml.safe_load(f) or []
            
            # Simple deduplication based on prefix
            rule_prefix = rule_text.split('.')[0]
            if any(r.startswith(rule_prefix) for r in rules): 
                return
                
            rules.append(rule_text)
            # Keep top 20 most recent/relevant
            with open(target_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(rules[-20:], f, allow_unicode=True, default_flow_style=False)
        finally:
            if os.path.exists(lock_file):
                try: os.remove(lock_file)
                except: pass

    def _log_major_failure(self, instance_id: str, error: str, thought: str, attempts: int):
        self.major_logger.info(f"INSTANCE: {instance_id} | ERROR: {error[:150]} | FIX: {thought[:150]}")

    def get_dynamic_context(self) -> str:
        dialect_rules = self._load_from_file(self.dialect_memory_dir / f"{self.dialect}.yaml")
        reasoning_rules = self._load_from_file(self.reasoning_memory_dir / "generic.yaml")
        context = ""
        if dialect_rules:
            context += "DYNAMIC DIALECT RULES:\n" + "\n".join([f"- {r}" for r in dialect_rules]) + "\n"
        if reasoning_rules:
            context += "DYNAMIC REASONING PATTERNS:\n" + "\n".join([f"- {r}" for r in reasoning_rules]) + "\n"
        return context if context else "No dynamic context yet."

    def _load_from_file(self, path: Path) -> List[str]:
        if not path.exists(): return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or []
        except Exception as e:
            logger.warning(f"Failed to read dynamic rules from {path}: {e}")
            return []
