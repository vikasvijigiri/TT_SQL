from typing import Dict, Any, List
from src.utils.logger import logger

class IntentValidationError(Exception):
    """Raised when an intent is too broken to proceed."""
    pass

class IntentValidator:
    """
    Upgraded IntentValidator with 9 specific validation checks and IR mutation.
    """
    
    def __init__(self, schema_graph):
        self.schema_graph = schema_graph

    def validate(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs all 9 checks on the intent and mutates it to fix or flag issues.
        """
        logger.info("Running Intent Validation...")
        
        intent = self._check_complexity(intent)          # CHECK 1
        intent = self._check_select_inference(intent)    # CHECK 2
        intent = self._check_operator_sanity(intent)      # CHECK 3
        intent = self._check_join_inference(intent)      # CHECK 4
        intent = self._check_null_conflict(intent)       # CHECK 5
        intent = self._check_ambiguity(intent)           # CHECK 6
        intent = self._check_duplicate_detection(intent) # CHECK 7
        intent = self._check_confidence_bug(intent)      # CHECK 8
        intent = self._check_unresolved_halt(intent)     # CHECK 9
        
        return intent

    def _check_complexity(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 1: Complexity re-evaluation."""
        conditions = self._get_all_conditions(intent)
        if len(conditions) > 4:
            intent["complexity"] = "high"
            logger.info("[Check 1] Complexity set to 'high' due to >4 conditions.")
        return intent

    def _check_select_inference(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 2: SELECT clause inference."""
        select = intent.get("select", {})
        if not select.get("columns") and not select.get("include_all"):
            select["include_all"] = True
            intent["select"] = select
            logger.warning("[Check 2] No explicit columns requested — defaulting to SELECT *")
        return intent

    def _check_operator_sanity(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 3: Operator sanity."""
        def walk(node):
            if node.get("type") == "condition":
                val = node.get("value")
                op = node.get("operator")
                
                # IS NOT NULL with a non-null value -> "="
                if op == "IS NOT NULL" and val is not None:
                    node["operator"] = "="
                    logger.info(f"[Check 3] Corrected {node['raw_field']} from IS NOT NULL to '=' because a value was provided.")
                
                # != with a list value -> "NOT IN"
                if op == "!=" and isinstance(val, list):
                    node["operator"] = "NOT IN"
                    logger.info(f"[Check 3] Corrected operator for {node['raw_field']} to 'NOT IN'")
                
                # LIKE without wildcards
                if op == "LIKE" and isinstance(val, str) and "%" not in val:
                    node["value"] = f"%{val}%"
                    logger.info(f"[Check 3] Added wildcards to LIKE value for {node['raw_field']}")
                    
            if node.get("type") == "group":
                for c in node.get("conditions", []): walk(c)
        
        walk(intent.get("filters", {}))
        return intent

    def _check_join_inference(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 4: Join inference (Stub for now, will be wired to JoinResolver)."""
        mapped_fields = intent.get("schema_mapping", {}).get("mapped_fields", [])
        tables = set()
        for f in mapped_fields:
            col_path = f.get("column", "")
            if "." in col_path:
                # DATABASE.SCHEMA.TABLE.COLUMN -> table is everything but the last part
                parts = col_path.split(".")
                table = ".".join(parts[:-1])
                tables.add(table)
        
        if len(tables) > 1:
            intent["source"] = intent.get("source", {})
            intent["source"]["requires_join"] = True
            intent["source"]["candidate_tables"] = list(tables)
            logger.info(f"[Check 4] Join required for tables: {tables}")
            # Actual JoinStep population will happen in Section 5
        return intent

    def _check_null_conflict(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 5: NULL handling vs clean_data conflict."""
        reqs = intent.get("output_requirements", {})
        if reqs.get("clean_data") and reqs.get("include_nulls"):
            reqs["include_nulls"] = False
            logger.info("[Check 5] NULL conflict: 'clean_data' is true, so 'include_nulls' set to false.")
        return intent

    def _check_ambiguity(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 6: Ambiguity with clarification."""
        amb = intent.get("ambiguity", {})
        if len(amb.get("fields", [])) > 3:
            intent["pipeline_status"] = "HALTED_NEEDS_CLARIFICATION"
            amb["clarification_needed"] = True
            logger.warning("[Check 6] Too many ambiguous fields (>3). Halting pipeline.")
        elif amb.get("fields"):
            amb["clarification_needed"] = True
            logger.info(f"[Check 6] Ambiguity flagged for: {amb['fields']}")
        return intent

    def _check_duplicate_detection(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 7: Duplicate condition detection."""
        # Simplified: check for identical (raw_field, operator, value)
        if "filters" in intent and intent["filters"].get("type") == "group":
            seen = set()
            new_conds = []
            for c in intent["filters"].get("conditions", []):
                key = (c.get("raw_field"), c.get("operator"), str(c.get("value")))
                if key not in seen:
                    seen.add(key)
                    new_conds.append(c)
                else:
                    logger.info(f"[Check 7] Removed duplicate condition: {key[0]}")
            intent["filters"]["conditions"] = new_conds
        return intent

    def _check_confidence_bug(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 8: Confidence computation (fix the 0.00 bug)."""
        mapping = intent.get("schema_mapping", {})
        mapped = mapping.get("mapped_fields", [])
        unresolved = mapping.get("unresolved_fields", [])
        
        if not mapped and not unresolved:
            intent["confidence"] = 0.0
            return intent
            
        scores = [f.get("confidence", 0.0) for f in mapped]
        avg_score = sum(scores) / len(scores) if scores else 1.0
        
        # Penalty for unresolved fields
        penalty = 0.5 ** len(unresolved)
        final_conf = avg_score * penalty
        
        intent["confidence"] = round(final_conf, 2)
        logger.info(f"[Check 8] Confidence computed: {intent['confidence']}")
        return intent

    def _check_unresolved_halt(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """CHECK 9: Unresolved field halt."""
        unresolved = intent.get("schema_mapping", {}).get("unresolved_fields", [])
        if len(unresolved) > 2:
            intent["pipeline_status"] = "HALTED_NEEDS_CLARIFICATION"
            logger.error(f"[Check 9] Halted due to {len(unresolved)} unresolved fields.")
            raise IntentValidationError(f"Too many unresolved fields: {', '.join(unresolved)}")
        return intent

    def _get_all_conditions(self, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Helper to flatten all conditions."""
        conds = []
        def walk(node):
            if node.get("type") == "condition": conds.append(node)
            if node.get("type") == "group":
                for c in node.get("conditions", []): walk(c)
        walk(intent.get("filters", {}))
        return conds
