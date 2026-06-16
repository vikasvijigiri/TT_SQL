from core.agent_base import AgentState, BaseAgent
from core.llm_service import LLMService
from core.prompt_loader import PromptLoader
from core.logger import Logger
import json

class GenericAgent(BaseAgent):
    """
    A unified, template-driven agent that can perform any task based on a prompt.
    """

    def __init__(self, step_id: str, prompt_name: str, output_key: str = None, state_field: str = None, llm_service: LLMService = None, max_tokens: int = None):
        super().__init__(name=step_id)
        self.prompt_name = prompt_name
        self.output_key = output_key # None means whole dictionary
        self.state_field = state_field
        self.llm = llm_service
        self.max_tokens = max_tokens
        self.prompt_loader = PromptLoader()

    def run(self, state: AgentState) -> AgentState:
        from core.tool_registry import ToolRegistry
        from core.utils import validate_json_response, normalize_confidence, modularize_ai_response
        
        MAX_RETRIES = 3
        tools_map = ToolRegistry.get_tools_map()
        prev_state_str = ""
        MAX_TOOL_TURNS = 5
        tool_turn = 0
        
        while tool_turn < MAX_TOOL_TURNS:
            tool_turn += 1
            
            # State-driven execution check
            if self.name in ("QueryPlanner", "QueryPlanning"):
                if not state.selected_tables and not state.schema_info:
                    Logger.log("🛑 Planner blocked due to missing schema.", level="ERROR")
                    state.schema_status = "FAILED"
                    break
            elif self.name in ("SQLBuilder", "SQLGeneration"):
                if not state.strategies:
                    Logger.log("🛑 Execution blocked due to invalid state (missing strategy).", level="ERROR")
                    break

            response = None
            messages = []
            
            # --- STRICT JSON & RETRY LOOP ---
            for attempt in range(MAX_RETRIES):
                try:
                    messages = self.prompt_loader.load_prompt(self.prompt_name, state=state)
                except ValueError as e:
                    Logger.log(f"Schema retrieval failed → pipeline stopped: {str(e)}", level="ERROR")
                    state.schema_status = "FAILED"
                    return state

                # Get Raw Completion (Strict Mode - No markdown/noise allowed)
                raw_content = self.llm.get_completion(messages, state=state, agent_name=self.name, max_tokens=self.max_tokens)
                
                # Relaxed Formatting Check: Allow Markdown blocks as long as JSON payload is extractable

                # Parse JSON
                try:
                    response = json.loads(raw_content.strip())
                except Exception as e_initial:
                    # Task: Robust JSON Repair
                    import re
                    parsed = False
                    current_content = raw_content.strip()
                    
                    # 1. Regex Fallback for JSON block
                    try:
                        json_match = re.search(r"(\{.*\})", current_content, re.DOTALL)
                        if json_match:
                            response = json.loads(json_match.group(1))
                            parsed = True
                    except Exception:
                        pass
                        
                    # 2. Repair Trailing Commas
                    if not parsed:
                        try:
                            repaired = re.sub(r',\s*([\]}])', r'\1', current_content)
                            json_match = re.search(r"(\{.*\})", repaired, re.DOTALL)
                            if json_match:
                                response = json.loads(json_match.group(1))
                                parsed = True
                        except Exception:
                            pass
                            
                    # 3. Repair Python literals (True, False, None)
                    if not parsed:
                        try:
                            repaired = re.sub(r'\bTrue\b', 'true', current_content)
                            repaired = re.sub(r'\bFalse\b', 'false', repaired)
                            repaired = re.sub(r'\bNone\b', 'null', repaired)
                            json_match = re.search(r"(\{.*\})", repaired, re.DOTALL)
                            if json_match:
                                response = json.loads(json_match.group(1))
                                parsed = True
                        except Exception:
                            pass
                            
                    if not parsed:
                        Logger.log(f"[Validator] {self.name} → FAIL (parse error): {str(e_initial)}. Raw content preview: {raw_content.strip()[:200]}...", level="WARN")
                        if attempt < MAX_RETRIES - 1:
                            Logger.log(f"[{self.name}] INVALID_JSON → retrying (attempt {attempt + 2}/{MAX_RETRIES})", level="WARN")
                        continue

                # Strict Contract Validation (Tasks 1, 2, 5, 9)
                validation = {"status": "SUCCESS"}
                if self.name in ("QueryPlanner", "QueryPlanning"):
                    validation = validate_json_response(
                        response, 
                        required_keys=["strategies", "concept_mapping", "confidence", "missing_elements", "expansion_required", "requested_tables"],
                        allowed_values={"confidence": ["high", "medium", "low"]}
                    )
                    # Normalize confidence (Task 9)
                    if response:
                        response["confidence"] = normalize_confidence(response.get("confidence"))
                elif self.name == "IntentAnalyzer":
                    validation = validate_json_response(
                        response,
                        required_keys=["entities", "metrics", "pre_filters", "post_filters", "filter_grain", "aggregation_steps", "aggregation_target", "answer_grain", "grouping_required", "join_required", "edge_cases", "ambiguities"]
                    )
                elif self.name == "QueryCritic":
                    validation = validate_json_response(
                        response,
                        required_keys=["is_valid", "logical_fit", "feedback", "missing_logical_steps", "grounding_errors", "suggested_fix"],
                        allowed_values={"logical_fit": ["pass", "pass_with_risk", "fail"]}
                    )
                elif self.name == "SQLCritic":
                    validation = validate_json_response(
                        response,
                        required_keys=["is_valid", "logical_fit", "feedback", "missing_logical_steps", "grounding_errors", "suggested_fix"],
                        allowed_values={"logical_fit": ["pass", "pass_with_risk", "fail"]}
                    )
                
                elif self.name == "MissingElementsResolver":
                    validation = validate_json_response(
                        response,
                        required_keys=["resolved_elements", "updated_missing_elements", "resolution_notes"]
                    )
                
                elif self.name == "TablePruner":
                    validation = validate_json_response(
                        response,
                        required_keys=["relevant_tables", "reasoning"]
                    )
                elif self.name == "SQLGenerator":
                    validation = validate_json_response(
                        response,
                        required_keys=["sql"]
                    )
                
                if validation["status"] == "SUCCESS":
                    Logger.log(f"[Validator] {self.name} → PASS")
                    break
                else:
                    Logger.log(f"[Validator] {self.name} → FAIL ({validation['reason']})", level="WARN")
                    if attempt < MAX_RETRIES - 1:
                        Logger.log(f"[{self.name}] INVALID_JSON → retrying (attempt {attempt + 2}/{MAX_RETRIES})", level="WARN")
                    response = None

            if not response:
                Logger.log(f"[PIPELINE] FAILED (invalid agent output: {self.name})", level="ERROR")
                state.pipeline_failure_reason = f"Agent {self.name} failed contract validation after {MAX_RETRIES} attempts."
                return state

            # --- PROCESS RESPONSE ---
            prompt_str = "\n".join([f"### {m['role'].upper()}\n{m['content']}" for m in messages])
            inputs = [{"desc": f"Agent Task: {self.name}", "status": "active"}]
            
            # Check for tool usage
            tool_name = response.get("tool")
            if tool_name and tool_name in tools_map:
                params = response.get("params", {})
                t_reason = response.get("reasoning", "N/A")
                Logger.log_agent_block(self.name, inputs, f"**Tool Requested**: `{tool_name}`", "success", prompt=prompt_str)
                
                try:
                    tool_func = tools_map[tool_name]
                    tool_func(state, params=params) if params else tool_func(state)
                    continue 
                except Exception as e:
                    Logger.log(f"Tool Execution Failed: {str(e)}", level="ERROR")
                    break

            # Standard State Mapping
            if self.state_field:
                val = response.get(self.output_key) if self.output_key else response
                if val is not None:
                    setattr(state, self.state_field, val)
                    
                    # Normalization side-effects
                    if self.state_field == "strategies" and isinstance(val, dict):
                         # Ensure confidence is one of the strictly allowed values
                         if "confidence" in val:
                             val["confidence"] = normalize_confidence(val["confidence"])
                    
                    if self.state_field == "sql_candidates" and isinstance(val, dict):
                         setattr(state, self.state_field, [val])

            # Store last output for orchestration logic
            state.last_agent_output = response
            res_summary = modularize_ai_response(response)
            Logger.log_agent_block(self.name, inputs, res_summary, "success", prompt=prompt_str)
            break 

        return state

        return state

    @staticmethod
    def _validate_planner_output(response: dict, state) -> dict:
        """
        Tasks 1, 3, 4, 5, 6: Hard JSON enforcement for QueryPlanner output.
        Validates structure, confidence, concept_mapping grounding, VARIANT flag,
        and early-stop conditions. Generic — no hardcoded column/table/DB names.
        Returns {"valid": True/False, "reason": "..."}.
        """
        # ── Task 1: All 6 required top-level fields must be present ──────────
        REQUIRED_FIELDS = [
            "strategies", "concept_mapping", "confidence",
            "missing_elements", "expansion_required", "requested_tables",
        ]
        missing_fields = [f for f in REQUIRED_FIELDS if f not in response]
        if missing_fields:
            return {"valid": False, "reason": f"Missing required fields: {missing_fields}"}

        # strategies sub-fields
        strat = response.get("strategies", {})
        if not isinstance(strat, dict):
            return {"valid": False, "reason": "strategies must be a dict"}
        for sub in ("primary", "alternative", "semantic_risks"):
            if sub not in strat:
                return {"valid": False, "reason": f"strategies.{sub} is missing"}

        # ── Task 6: Confidence must be exactly one of the three valid values ──
        VALID_CONFIDENCE = {"high", "medium", "low"}
        conf = response.get("confidence", None)
        if not conf or str(conf).lower().strip() not in VALID_CONFIDENCE:
            return {
                "valid": False,
                "reason": (
                    f"confidence='{conf}' is invalid. "
                    "Must be exactly 'high', 'medium', or 'low'."
                ),
            }

        # ── Task 3: Anti-hallucination — cross-reference concept_mapping ──────
        # Every concept_mapping entry's mapped_to column must exist in
        # state.selected_columns OR be flagged as source_type=assumption/variant_required.
        selected_columns = getattr(state, "selected_columns", {})
        if selected_columns:
            known_cols = set()
            for cols in selected_columns.values():
                for col in cols:
                    known_cols.add(col.strip().strip('"').upper())

            hallucinated = []
            for entry in response.get("concept_mapping", []):
                source_type = entry.get("source_type", "relational")
                if source_type in ("assumption",):
                    continue  # Assumption entries don't need grounding
                mapped_to = entry.get("mapped_to", "")
                col_name = mapped_to.split(".")[-1].strip('"').upper()
                # variant_required entries reference VARIANT columns — validate keys
                if source_type == "variant_required":
                    path = entry.get("mapped_to", "") # e.g. T.COL."key"
                    # Simple heuristic: if it has more than 2 parts separated by dots, it might be a key
                    parts = path.split(".")
                    if len(parts) >= 3:
                        # Check if the key part is in missing_elements or in schema_info
                        is_missing = any(path in m or m in path for m in response.get("missing_elements", []))
                        if not is_missing:
                             # Check schema for this column's variant_keys
                             v_keys = []
                             for info in getattr(state, "schema_info", {}).values():
                                 for c in info.get("columns", []):
                                     if c.get("variant_keys"):
                                         v_temp = c["variant_keys"]
                                         v_keys.extend(list(v_temp.keys()) if isinstance(v_temp, dict) else list(v_temp))
                             
                             # Extract key part (last part)
                             key_candidate = parts[-1].strip('"')
                             if key_candidate not in v_keys:
                                 hallucinated.append(f"{path} (Unknown VARIANT key)")
                    continue
                
                if col_name and col_name not in known_cols:
                    hallucinated.append(mapped_to)

            if hallucinated:
                return {
                    "valid": False,
                    "reason": (
                        f"Hallucinated columns not in schema: {hallucinated}. "
                        "Only use columns present in the provided schema."
                    ),
                }

        # ── Task 4: VARIANT source_type → FLATTEN must appear in primary ─────
        has_variant = any(
            e.get("source_type") == "variant_required"
            for e in response.get("concept_mapping", [])
        )
        if has_variant:
            primary_steps = " ".join(strat.get("primary", [])).lower()
            if "flatten" not in primary_steps and "lateral" not in primary_steps:
                return {
                    "valid": False,
                    "reason": (
                        "concept_mapping has source_type=variant_required but "
                        "strategies.primary does not mention LATERAL FLATTEN. "
                        "Add a FLATTEN step."
                    ),
                }

        # ── Task 5: Low confidence → expansion_required must be true ─────────
        if conf == "low" and not response.get("expansion_required", False):
            return {
                "valid": False,
                "reason": (
                    "confidence='low' but expansion_required=false. "
                    "Low confidence MUST set expansion_required=true."
                ),
            }

        return {"valid": True, "reason": "OK"}
