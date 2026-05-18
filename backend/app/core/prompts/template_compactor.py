import re
from typing import Dict, List

class TemplateCompactor:
    """
    Enterprise Syntax Template Compaction Engine.
    Strips verbose explanatory prose and comments from SQL templates while preserving
    absolute pristine syntax structures. Target: 50-120 tokens per template.
    """

    @classmethod
    def compact_sql(cls, sql: str) -> str:
        # Strip SQL comments
        cleaned = re.sub(r'--.*?\n', '\n', sql)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        
        # Remove extra whitespace while keeping clean indentation
        lines = [l.rstrip() for l in cleaned.splitlines() if l.strip()]
        return "\n".join(lines)

    @classmethod
    def compact_template(cls, template: Dict[str, str]) -> Dict[str, str]:
        name = template.get("name", "Template")
        sql = template.get("sql", "")
        compacted_sql = cls.compact_sql(sql)
        return {
            "name": name,
            "sql": compacted_sql
        }

    @classmethod
    def compact_templates(cls, templates: List[Dict[str, str]]) -> List[Dict[str, str]]:
        return [cls.compact_template(t) for t in templates]
