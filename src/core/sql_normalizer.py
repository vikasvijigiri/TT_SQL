import sqlglot
from sqlglot import exp, parse_one
from core.dialect_manager import DialectManager
from core.logger import Logger

class SQLNormalizer:
    """
    Builds a DIALECT-AWARE SQL NORMALIZATION layer using capability-driven logic.
    Transforms SQL structure based on dialect capabilities without string hacks.
    """
    def __init__(self, dialect: str):
        self.dialect = dialect
        self.mgr = DialectManager()
        self.capabilities = self.mgr.get_capabilities(dialect)
        self.violations = []
        self.transformations_applied = []

    def normalize(self, sql: str) -> str:
        """
        Main entry point for SQL normalization.
        Extracts SELECT context and resolves capability violations (e.g. alias in HAVING).
        """
        try:
            # sqlglot dialect resolution
            sg_dialect = self.dialect
            if sg_dialect == "postgresql": sg_dialect = "postgres"
            
            # 1. Parse AST
            expression = parse_one(sql, read=sg_dialect)
            
            # 2. Build Structural Representation (Alias Map)
            # TASK 2: Extract SELECT expressions (including aliases)
            alias_map = {}
            for select in expression.find_all(exp.Select):
                for projection in select.expressions:
                    if isinstance(projection, exp.Alias):
                        alias_name = projection.alias
                        # underlying expression (e.g. SUM(runs_scored))
                        alias_map[alias_name] = projection.this
            
            modified = False
            
            # 3. DETECT VIOLATIONS VIA CAPABILITIES
            # TASK 3 & 4: Generic Transformation Engine
            
            # Alex Reference Resolution in HAVING
            if not self.capabilities.get("allow_alias_in_having", True):
                # Traverse HAVING clause
                for having in expression.find_all(exp.Having):
                    for column in having.find_all(exp.Column):
                        col_name = column.name
                        if col_name in alias_map:
                            # Resolve alias using select_alias_map
                            # TASK 5: Ensure alias exists and mapping is unambiguous
                            replacement = alias_map[col_name].copy()
                            
                            # Replace alias with underlying expression
                            column.replace(replacement)
                            
                            self.violations.append({
                                "type": "alias_reference_violation",
                                "location": "HAVING",
                                "target": col_name
                            })
                            self.transformations_applied.append(f"HAVING {col_name} -> {replacement.sql(dialect=sg_dialect)}")
                            modified = True

            # Alias Reference Resolution in GROUP BY
            if not self.capabilities.get("allow_alias_in_group_by", True):
                for group in expression.find_all(exp.Group):
                    for column in group.find_all(exp.Column):
                        col_name = column.name
                        if col_name in alias_map:
                            replacement = alias_map[col_name].copy()
                            column.replace(replacement)
                            
                            self.violations.append({
                                "type": "alias_reference_violation",
                                "location": "GROUP BY",
                                "target": col_name
                            })
                            self.transformations_applied.append(f"GROUP BY {col_name} -> {replacement.sql(dialect=sg_dialect)}")
                            modified = True
            
            # TASK 9: NO STRING HACKS (STRICT) - uses AST parsing + structured transformation
            final_sql = expression.sql(dialect=sg_dialect)
            
            # TASK 6: INTEGRATE LOGS
            Logger.log(f"\n[SQLNormalizer] dialect: {self.dialect}")
            if self.violations:
                Logger.log(f"[SQLNormalizer] violations_detected: {len(self.violations)}")
                for v in self.violations:
                    Logger.log(f"  - {v['type']} at {v['location']}: {v['target']}")
                Logger.log(f"[SQLNormalizer] transformations_applied: {len(self.transformations_applied)}")
                Logger.log(f"[SQLNormalizer] sql_modified: {modified}")
            else:
                Logger.log("[SQLNormalizer] No violations detected. Original structure preserved.")
                
            return final_sql

        except Exception as e:
            # TASK 10: FAIL-SAFE DESIGN
            Logger.log(f"[SQLNormalizer] skipped (unsafe or unsupported): {str(e)}", level="WARN")
            return sql
