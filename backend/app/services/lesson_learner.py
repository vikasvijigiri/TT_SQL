import json
import os
import logging
from typing import List, Dict, Tuple
from pathlib import Path

from backend.app.core.config import MEMORY_DIR, LOGS_DIR

class DynamicRuleLearner:
    def __init__(self, dialect: str = "snowflake"):
        self.dialect = dialect.lower()
        self.dialect_memory_dir = MEMORY_DIR / "dialects"
        self.reasoning_memory_dir = MEMORY_DIR / "reasoning"
        self.major_failures_log = LOGS_DIR / "major_failures.log"
        
        self.dialect_memory_dir.mkdir(parents=True, exist_ok=True)
        self.reasoning_memory_dir.mkdir(parents=True, exist_ok=True)
        self.major_failures_log.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup major failure logger
        self.major_logger = logging.getLogger("MAJOR_FAILURES")
        if not self.major_logger.handlers:
            handler = logging.FileHandler(str(self.major_failures_log))
            handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
            self.major_logger.addHandler(handler)
            self.major_logger.setLevel(logging.INFO)

    def analyze_and_learn(self, instance_id: str, error: str, correction_thought: str, attempts: int):
        """Analyzes a correction and categorizes the lesson into the correct folder."""
        is_minor, category, is_dialect_specific = self._classify_error(error)
        
        if is_minor:
            self._add_rule(category, correction_thought, is_dialect_specific)
        else:
            self._log_major_failure(instance_id, error, correction_thought, attempts)

    def _classify_error(self, error: str) -> Tuple[bool, str, bool]:
        """Classifies error: (is_minor, category, is_dialect_specific)"""
        error_lower = error.lower()
        
        # Dialect-Specific Minor Errors
        dialect_keywords = ["identifier", "ambiguous", "syntax", "unexpected", "date", "timestamp", "flatten", "variant"]
        if any(kw in error_lower for kw in dialect_keywords):
            return True, "Dialect Rule", True
            
        # Reasoning-Specific Minor Errors
        if "data quality fail" in error_lower or "0 rows" in error_lower:
            return True, "Reasoning Pattern", False
            
        return False, "Major Failure", False

    def _add_rule(self, category: str, fix_thought: str, is_dialect: bool):
        """Saves rule to appropriate folder."""
        sub_dir = self.dialect_memory_dir if is_dialect else self.reasoning_memory_dir
        file_name = f"{self.dialect}.json" if is_dialect else "generic.json"
        target_file = sub_dir / file_name
        
        if not target_file.exists():
            with open(target_file, 'w', encoding='utf-8') as f: json.dump([], f)
            
        with open(target_file, 'r', encoding='utf-8') as f:
            try:
                rules = json.load(f)
            except:
                rules = []
            
        rule_text = f"[{category}] {fix_thought.split('.')[0]}."
        if any(r['rule'] == rule_text for r in rules):
            return
            
        rules.append({"rule": rule_text})
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(rules[-10:], f, indent=2)

    def _log_major_failure(self, instance_id: str, error: str, thought: str, attempts: int):
        self.major_logger.info(f"INSTANCE: {instance_id} | ERROR: {error[:150]} | FIX: {thought[:150]}")

    def get_dynamic_context(self) -> str:
        """Retrieves and combines dynamic rules for prompt injection."""
        dialect_rules = self._load_from_file(self.dialect_memory_dir / f"{self.dialect}.json")
        reasoning_rules = self._load_from_file(self.reasoning_memory_dir / "generic.json")
        
        context = ""
        if dialect_rules:
            context += "DYNAMIC DIALECT RULES:\n" + "\n".join([f"- {r['rule']}" for r in dialect_rules]) + "\n"
        if reasoning_rules:
            context += "DYNAMIC REASONING PATTERNS:\n" + "\n".join([f"- {r['rule']}" for r in reasoning_rules]) + "\n"
            
        return context if context else "No dynamic context yet."

    def _load_from_file(self, path: Path) -> List[Dict]:
        if not path.exists(): return []
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return []
