import json
import os
import re
from typing import List, Dict, Any, Optional
from core.paths import METADATA_DIR
from core.logger import Logger

DIALECT_CONSTRAINTS_FILE = METADATA_DIR / "dialect_constraints.json"
SAFE_PATTERNS_FILE = METADATA_DIR / "safe_patterns.json"

DIALECT_CAPABILITIES = {
    "sqlite": {
        "allow_alias_in_having": False,
        "allow_alias_in_group_by": True,
        "supports_qualify": False,
        "supports_window_functions": True,
        "identifier_quote": '"'
    },
    "snowflake": {
        "allow_alias_in_having": True,
        "allow_alias_in_group_by": True,
        "supports_qualify": True,
        "supports_variant": True,
        "identifier_quote": '"'
    },
    "bigquery": {
        "allow_alias_in_having": True,
        "allow_alias_in_group_by": True,
        "supports_qualify": True,
        "supports_struct": True,
        "identifier_quote": "`"
    },
    "postgres": {
        "allow_alias_in_having": False,
        "allow_alias_in_group_by": False,
        "supports_window_functions": True,
        "identifier_quote": '"'
    }
}

class DialectConstraint:
    def __init__(self, 
                 rule: str, 
                 scope: str = "general", 
                 pattern: Optional[str] = None, 
                 confidence: str = "medium", 
                 occurrences: int = 1,
                 overgeneralized: bool = False,
                 active: bool = True,
                 enforcement: str = "advisory"):
        self.rule = rule
        self.scope = scope
        self.pattern = pattern
        self.confidence = confidence # low, medium, high
        self.occurrences = occurrences
        self.overgeneralized = overgeneralized
        self.active = active
        self.enforcement = enforcement # blocking, advisory

    def to_dict(self):
        return {
            "rule": self.rule,
            "scope": self.scope,
            "pattern": self.pattern,
            "confidence": self.confidence,
            "occurrences": self.occurrences,
            "overgeneralized": self.overgeneralized,
            "active": self.active,
            "enforcement": self.enforcement
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            rule=data["rule"],
            scope=data.get("scope", data.get("category", "general")).lower(),
            pattern=data.get("pattern"),
            confidence=data.get("confidence", "medium"),
            occurrences=data.get("occurrences", 1),
            overgeneralized=data.get("overgeneralized", False),
            active=data.get("active", True),
            enforcement=data.get("enforcement", "advisory")
        )

class DialectManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DialectManager, cls).__new__(cls)
            cls._instance._load_memory()
        return cls._instance

    def _load_memory(self):
        self.memory: Dict[str, List[DialectConstraint]] = {}
        self.safe_patterns: Dict[str, List[str]] = {}
        
        if DIALECT_CONSTRAINTS_FILE.exists():
            try:
                with open(DIALECT_CONSTRAINTS_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                    for dialect, constraints in data.items():
                        self.memory[dialect] = [DialectConstraint.from_dict(c) for c in constraints]
            except Exception:
                self.memory = {}
        
        if SAFE_PATTERNS_FILE.exists():
            try:
                with open(SAFE_PATTERNS_FILE, encoding="utf-8") as f:
                    self.safe_patterns = json.load(f)
            except Exception:
                self.safe_patterns = {}

    def _save_memory(self):
        data = {dialect: [c.to_dict() for c in constraints] for dialect, constraints in self.memory.items()}
        DIALECT_CONSTRAINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DIALECT_CONSTRAINTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        with open(SAFE_PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.safe_patterns, f, indent=2)

    def get_capabilities(self, dialect: str) -> Dict[str, Any]:
        """Returns the capabilities for a given dialect, or default if unknown."""
        return DIALECT_CAPABILITIES.get(dialect.lower(), {
            "allow_alias_in_having": False,
            "allow_alias_in_group_by": False,
            "identifier_quote": '"'
        })

    def learn_from_error(self, dialect: str, error_msg: str, sql: str, llm_service: Any):
        """Learns atomic dialect constraints from an error message using an LLM decomposition."""
        if not llm_service or not error_msg:
            return

        # Use a decomposition-focused prompt
        messages = [
            {"role": "system", "content": """You are a Dialect Constraint Architect.
Analyze a SQL execution error and decompose it into ATOMIC structural constraints.

RULES:
1. If the error mentions multiple issues (e.g., uses 'or', 'and', or multiple clauses), SPLIT them into separate rules.
2. Formulate generic rules that target the structural pattern (e.g., 'LATERAL + ON clause').
3. Assign a SCOPE: 'join_predicate', 'join_type', 'function_usage', 'aggregation', 'identifier', or 'general'.
4. Assign ENFORCEMENT: 'blocking' if the violation is known to always fail, 'advisory' if unsure.
5. Assign CONFIDENCE:
   - 'low': if the error contains 'or', is ambiguous, or has multiple possible causes.
   - 'medium': if the error is explicit and clear.
6. Provide a Regex pattern that detects the structural violation.

OUTPUT FORMAT (JSON List):
[
  {
    "scope": "string",
    "pattern": "regex_pattern",
    "rule": "generic rule string",
    "confidence": "low | medium",
    "enforcement": "blocking | advisory"
  }
]"""},
            {"role": "user", "content": f"DIALECT: {dialect}\nERROR: {error_msg}\nSQL: {sql}"}
        ]
        
        try:
            resp_text = llm_service.get_completion(messages, agent_name="DialectManager")
            json_match = re.search(r"(\[.*\])", resp_text, re.DOTALL)
            if json_match:
                constraints = json.loads(json_match.group(1))
                for data in constraints:
                    rule = data.get("rule")
                    pattern = data.get("pattern")
                    scope = data.get("scope", "general").lower()
                    confidence = data.get("confidence", "medium")
                    enforcement = data.get("enforcement", "advisory")
                    
                    if rule:
                        self.add_constraint(dialect, rule, pattern, scope, confidence, enforcement)
                
                Logger.log(f"🧠 [DialectManager] Decomposed {len(constraints)} constraints for {dialect}")
        except Exception as e:
            Logger.log(f"⚠️ [DialectManager] Failed to decompose error: {str(e)}")

    def add_constraint(self, dialect: str, rule: str, pattern: Optional[str] = None, scope: str = "general", confidence: str = "medium", enforcement: str = "advisory"):
        if dialect not in self.memory:
            self.memory[dialect] = []
        
        # Check if rule already exists
        for c in self.memory[dialect]:
            if c.rule == rule:
                c.occurrences += 1
                if c.occurrences >= 2:
                    c.confidence = "high"
                self._save_memory()
                return
        
        # Add new constraint
        new_c = DialectConstraint(rule=rule, pattern=pattern, scope=scope, confidence=confidence, enforcement=enforcement)
        self.memory[dialect].append(new_c)
        self._save_memory()
        Logger.log(f"🧠 [DialectManager] Learned Constraint [{scope}]: {rule} (Confidence: {confidence})")

    def get_constraints(self, dialect: str, group_by_category: bool = False, active_only: bool = True) -> Any:
        constraints = self.memory.get(dialect, [])
        if active_only:
            constraints = [c for c in constraints if c.active]
            
        if not group_by_category:
            return [c.rule for c in constraints]
        
        grouped = {}
        for c in constraints:
            scope = c.scope.upper()
            if scope not in grouped: grouped[scope] = []
            grouped[scope].append(c.rule)
        return grouped

    def detect_aggregation_type(self, expression: str) -> str:
        """Task 1: Detects if an aggregation target is a scalar column or a complex object."""
        # JSON path (e.g., value:"field"), variant reference, or object-like structure
        if ":" in expression or "VALUE" in expression.upper() or "{" in expression:
            return "object"
        return "scalar"

    def validate_sql_aggregations(self, sql: str) -> List[Dict[str, Any]]:
        """Task 2 & 3: Analyzes COUNT(DISTINCT) usages in SQL for stability."""
        issues = []
        # Find all COUNT(DISTINCT ...) patterns
        # Note: This is a heuristic regex-based parser
        matches = re.finditer(r"COUNT\s*\(\s*DISTINCT\s+([^)]+)\)", sql, re.IGNORECASE)
        
        has_multiple_flattens = len(re.findall(r"LATERAL\s+FLATTEN", sql, re.IGNORECASE)) > 1

        for match in matches:
            expr = match.group(1).strip()
            agg_type = self.detect_aggregation_type(expr)
            Logger.log(f"🧠 [DialectManager] Aggregation Type Detected for '{expr}': {agg_type}")
            
            if agg_type == "object":
                issues.append({
                    "type": "aggregation_object_error",
                    "expression": expr,
                    "message": f"COUNT(DISTINCT {expr}) is invalid. Extract a scalar field first (e.g., value:'id').",
                    "severity": "high"
                })
                Logger.log(f"🛑 [DialectManager] COUNT(DISTINCT) rejected due to object usage: '{expr}'")
            else:
                # Task 3: If multiple flattens exist, check if we are using a scalar ID
                if has_multiple_flattens:
                    Logger.log(f"✨ [DialectManager] COUNT(DISTINCT) validated as SAFE with multiple flattens: '{expr}'")
                else:
                    Logger.log(f"✨ [DialectManager] COUNT(DISTINCT) validated as SAFE: '{expr}'")

        # Task 3: Check for risky COUNT(*) with flattens
        if "LATERAL FLATTEN" in sql.upper() and "COUNT(*)" in sql.upper():
             issues.append({
                "type": "aggregation_duplication_risk",
                "expression": "COUNT(*)",
                "message": "COUNT(*) is risky when using LATERAL FLATTEN due to duplication. Prefer COUNT(DISTINCT <scalar_id>).",
                "severity": "medium"
            })

        return issues

    def evaluate_constraints(self, sql: str, dialect: str) -> Dict[str, List[Any]]:
        """Task 8: Refined constraint evaluation separating violations and warnings."""
        violations = []
        warnings = []
        
        # 2. Safe Pattern Override
        if self.is_safe_pattern(sql, dialect):
            Logger.log("🛡️ [DialectManager] Safe Pattern Detected → overriding potential constraints")
            return {"violations": [], "warnings": []}

        constraints = self.memory.get(dialect, [])
        for c in constraints:
            if not c.active or not c.pattern:
                continue

            # 1. Pattern Match (MANDATORY)
            if not self.pattern_matches(sql, c.pattern):
                continue

            # 3. Enforcement Decision Logic
            if c.scope == "join_predicate":
                # Hard rule → always block
                violations.append(c.to_dict())
                Logger.log(f"🛑 [DialectManager] Violation Applied (join_predicate): {c.rule}")
            
            elif c.scope == "join_type":
                if c.confidence == "high":
                    violations.append(c.to_dict())
                    Logger.log(f"🛑 [DialectManager] Violation Applied (join_type): {c.rule}")
                else:
                    warnings.append(c.to_dict())
                    Logger.log(f"⚠️ [DialectManager] Warning Applied (join_type): {c.rule}")
            
            else:
                if c.confidence == "high":
                    violations.append(c.to_dict())
                    Logger.log(f"🛑 [DialectManager] Violation Applied ({c.scope}): {c.rule}")
                elif c.confidence == "medium":
                    warnings.append(c.to_dict())
                    Logger.log(f"⚠️ [DialectManager] Warning Applied ({c.scope}): {c.rule}")
                else:
                    warnings.append(c.to_dict())
                    Logger.log(f"📝 [DialectManager] Advisory Applied ({c.scope}): {c.rule}")

        return {
            "violations": violations,
            "warnings": warnings
        }

    def pattern_matches(self, sql: str, pattern: str) -> bool:
        """Helper to match SQL against patterns (regex or simplified tokens)."""
        sql_u = sql.upper()
        
        # Specific structural patterns requested by user
        if pattern == "LATERAL + ON":
            return ("LATERAL" in sql_u) and (" ON " in sql_u)
        
        if pattern == "OUTER JOIN + LATERAL":
            outer_join = ("LEFT JOIN" in sql_u or "RIGHT JOIN" in sql_u or "FULL JOIN" in sql_u)
            return outer_join and ("LATERAL" in sql_u)
            
        # Fallback to existing regex logic for learned patterns
        try:
            return bool(re.search(pattern, sql, re.IGNORECASE | re.DOTALL))
        except:
            return False

    def is_safe_pattern(self, sql: str, dialect: str) -> bool:
        """Checks if the SQL matches a known safe pattern."""
        # Task 7 & Core Function: Safe Patterns (Learned or explicit)
        safe_list = [
            "LEFT JOIN LATERAL FLATTEN(input =>",
            "CROSS JOIN LATERAL FLATTEN(input =>"
        ]
        
        sql_u = sql.upper()
        for p in safe_list:
            if p.upper() in sql_u:
                return True
                
        patterns = self.safe_patterns.get(dialect, [])
        for p in patterns:
            try:
                if re.search(p, sql, re.IGNORECASE | re.DOTALL):
                    return True
            except: continue
        return False

    def record_success(self, sql: str, dialect: str):
        """Task 6 & 7: Records a successful execution to decay constraints and store safe patterns."""
        if dialect not in self.safe_patterns:
            self.safe_patterns[dialect] = []
            
        # 1. Decay Constraints
        affected = False
        for c in self.memory.get(dialect, []):
            if not c.active or not c.pattern or c.pattern == "null":
                continue
            
            try:
                if re.search(c.pattern, sql, re.IGNORECASE | re.DOTALL):
                    # Contradiction: SQL succeeded but matched a 'violation' pattern
                    c.overgeneralized = True
                    # Decay confidence
                    if c.confidence == "high":
                        c.confidence = "medium"
                    elif c.confidence == "medium":
                        c.confidence = "low"
                    else:
                        c.active = False # Disable if repeatedly failing
                    
                    affected = True
                    Logger.log(f"📉 [DialectManager] Constraint Confidence Reduced: '{c.rule}' (SQL succeeded despite pattern match)")
            except: continue
            
        # 2. Extract and Store Safe Pattern (Heuristic-based simplified extraction)
        # For simplicity, we store the whole SQL as a literal-ish pattern or specific structural parts
        # In a real system, we'd use an LLM or AST to extract the 'safe structural pattern'
        # Here we'll just store the SQL if it's unique enough or use a placeholder
        # For now, let's store the successful SQL if it's not too long
        if len(sql) < 1000:
            sql_p = re.escape(sql).replace(r"\ ", r"\s+")
            if sql_p not in self.safe_patterns[dialect]:
                self.safe_patterns[dialect].append(sql_p)
                affected = True
                Logger.log("🌟 [DialectManager] Safe Pattern Registered from success")

        if affected:
            self._save_memory()
