import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agent.services.logger import logger


class StageMetric(BaseModel):
    stage_name: str
    start_time: float
    end_time: Optional[float] = None
    latency_sec: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TelemetryReport(BaseModel):
    query_id: str
    total_latency_sec: float
    total_input_tokens: int
    total_output_tokens: int
    retrieval_reduction_ratio: float
    schema_compression_ratio: float
    stages: List[StageMetric] = Field(default_factory=list)


class PipelineTelemetry:
    """
    Enterprise-grade structured telemetry tracker measuring latency, token usage,
    and schema reduction ratios across all pipeline stages.
    """

    def __init__(self, query_id: str = "default_run"):
        self.query_id = query_id
        self.start_time = time.time()
        self.stages: Dict[str, StageMetric] = {}
        self.current_stage: Optional[str] = None
        self.total_raw_schema_tokens: int = 1
        self.total_compressed_schema_tokens: int = 1
        self.total_raw_tables: int = 1
        self.total_retrieved_tables: int = 1

    def start_stage(self, stage_name: str, metadata: Dict[str, Any] | None = None):
        if (
            self.current_stage
            and self.current_stage in self.stages
            and not self.stages[self.current_stage].end_time
        ):
            self.end_stage(self.current_stage)

        self.current_stage = stage_name
        self.stages[stage_name] = StageMetric(
            stage_name=stage_name, start_time=time.time(), metadata=metadata or {}
        )
        logger.debug(f"[Telemetry] Started stage: {stage_name}")

    def end_stage(
        self,
        stage_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata: Dict[str, Any] | None = None,
    ):
        if stage_name in self.stages:
            metric = self.stages[stage_name]
            metric.end_time = time.time()
            metric.latency_sec = round(metric.end_time - metric.start_time, 3)
            metric.input_tokens = input_tokens
            metric.output_tokens = output_tokens
            if metadata:
                metric.metadata.update(metadata)
            logger.debug(
                f"[Telemetry] Ended stage: {stage_name} (Latency: {metric.latency_sec}s, Input Tokens: {input_tokens})"
            )

    def record_schema_compression(self, raw_tokens: int, compressed_tokens: int):
        self.total_raw_schema_tokens = max(1, raw_tokens)
        self.total_compressed_schema_tokens = max(1, compressed_tokens)

    def record_table_retrieval(self, raw_tables: int, retrieved_tables: int):
        self.total_raw_tables = max(1, raw_tables)
        self.total_retrieved_tables = max(1, retrieved_tables)

    def get_report(self) -> TelemetryReport:
        total_latency = time.time() - self.start_time
        tot_in = sum((s.input_tokens or 0) for s in self.stages.values())
        tot_out = sum((s.output_tokens or 0) for s in self.stages.values())

        comp_ratio = 1.0 - (
            self.total_compressed_schema_tokens / self.total_raw_schema_tokens
        )
        ret_ratio = 1.0 - (self.total_retrieved_tables / self.total_raw_tables)

        report = TelemetryReport(
            query_id=self.query_id,
            total_latency_sec=round(total_latency, 3),
            total_input_tokens=tot_in,
            total_output_tokens=tot_out,
            retrieval_reduction_ratio=round(max(0.0, min(1.0, ret_ratio)), 3),
            schema_compression_ratio=round(max(0.0, min(1.0, comp_ratio)), 3),
            stages=list(self.stages.values()),
        )
        return report

    def log_summary(self):
        rep = self.get_report()
        logger.info(f"=== TELEMETRY SUMMARY [{rep.query_id}] ===")
        logger.info(
            f"  Total Latency: {rep.total_latency_sec:.2f}s | Input Tokens: {rep.total_input_tokens} | Output Tokens: {rep.total_output_tokens}"
        )
        logger.info(
            f"  Retrieval Reduction: {rep.retrieval_reduction_ratio * 100:.1f}% | Schema Compression: {rep.schema_compression_ratio * 100:.1f}%"
        )
        for s in rep.stages:
            logger.debug(
                f"  Stage [{s.stage_name}]: {s.latency_sec}s | In: {s.input_tokens or 0} | Out: {s.output_tokens or 0}"
            )
