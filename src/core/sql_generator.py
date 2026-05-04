from core.logger import Logger

class SQLGenerator:
    """
    Generates SQL from a query plan.
    Template-first approach (Step 9).
    """

    def generate(self, plan: dict) -> str:
        """
        Generates SQL from plan.
        Plan structure: {base_table, joins, mappings}
        """
        if not plan or "error" in plan:
            return "SELECT * FROM (SELECT 1) WHERE 1=0"

        base_table = plan["base_table"]
        joins = plan["joins"]
        mappings = plan["mappings"]

        # Organize mappings by type
        filters = []
        aggregations = []
        columns = []
        
        # Track tables for aliasing if needed
        # (For now we'll use fully qualified names or simple names)
        
        for m in mappings:
            task = m["task"]
            mapping = m["mapping"]
            table = mapping["table"]
            col = mapping["column"]
            fqn = f"{table}.{col}"
            
            if task["type"] == "filter":
                f_obj = task["value"]
                op = f_obj.get("operator", "=")
                val = f_obj.get("value")
                
                # Format value
                if isinstance(val, str):
                    val_str = f"'{val}'"
                else:
                    val_str = str(val)
                
                filters.append(f"{fqn} {op} {val_str}")
            
            elif task["type"] == "aggregation":
                agg_obj = task["value"]
                op = agg_obj.get("operation", "COUNT").upper()
                out_name = agg_obj.get("output", "result")
                aggregations.append(f"{op}({fqn}) AS {out_name}")
            
            else:
                columns.append(fqn)

        # Build SQL parts
        select_clause = "SELECT "
        if aggregations:
            select_clause += ", ".join(aggregations)
        elif columns:
            select_clause += ", ".join(list(set(columns)))
        else:
            select_clause += "*"

        from_clause = f"FROM {base_table}"
        
        join_clauses = []
        for j in joins:
            join_clauses.append(
                f"JOIN {j['target_table']} ON {j['source_table']}.{j['source_col']} = {j['target_table']}.{j['target_col']}"
            )
        
        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        sql = f"{select_clause}\n{from_clause}\n" + "\n".join(join_clauses)
        if where_clause:
            sql += f"\n{where_clause}"
            
        # Hardened safety limit
        if "LIMIT" not in sql.upper():
            sql += "\nLIMIT 1000"

        return sql
