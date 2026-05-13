import os
import json
from src.utils.llm import LLMService
from src.utils.logger import logger
from src.execution.executor import Executor
from src.core.models import Intent, ExecutionResult
from src.core.orchestrator import Text2SQLPipeline as Orchestrator

class Text2SQLPipeline:
    def __init__(self, metadata_path: str):
        self.db_name = os.path.basename(metadata_path).replace(".json", "")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.schema_with_samples = json.load(f)
            
        self.orchestrator = Orchestrator(
            db_name=self.db_name,
            db_connector=Executor(),
            llm=LLMService(),
            schema_with_samples=self.schema_with_samples
        )

    def run(self, query: str, threshold: float = 0.5, external_knowledge: str = "") -> ExecutionResult:
        result = ExecutionResult(query=query)
        
        # Call the new orchestrator
        pipeline_res = self.orchestrator.run(query, external_knowledge=external_knowledge)
        
        # Map back to ExecutionResult for compatibility
        result.sql = pipeline_res.sql
        result.rows = pipeline_res.rows
        result.row_count = pipeline_res.row_count_estimate
        result.confidence = pipeline_res.confidence
        result.status = pipeline_res.status
        result.latency_ms = pipeline_res.latency_ms
        result.error = "; ".join(pipeline_res.warnings) if pipeline_res.status == "failed" else None
        
        return result
