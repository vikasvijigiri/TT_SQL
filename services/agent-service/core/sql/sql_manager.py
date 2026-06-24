from config.config import get_active_knowledge_dir


class SQLManager:
    """SQL cache reads and writes are disabled - every run goes through the full LLM pipeline.
    Failure hints (learning/) are unaffected; only sql_cache is suppressed.
    """

    def __init__(self):
        self.cache_dir = get_active_knowledge_dir() / "sql_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_best_sql(self, _instance_id: str) -> str:
        return ""

    def cache_success(self, _instance_id: str, _sql: str, _thought: str):
        pass

    def get_curated_sql(self, _instance_id: str) -> str:
        return ""

    def get_reference_context(self, _instance_id: str) -> str:
        return "No previous success cached."
