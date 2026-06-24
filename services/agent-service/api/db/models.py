from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text
from api.db.database import Base, engine
from datetime import datetime

from config.config import DEFAULT_USERNAME

class Evaluation(Base):
    __tablename__ = "evaluations"
    
    id = Column(Integer, primary_key=True, index=True)
    dataset = Column(String, index=True)
    query_id = Column(String, index=True)
    instance_id = Column(String, index=True)
    run_suffix = Column(String, default="")
    passed = Column(Boolean)
    reason = Column(String)
    method = Column(String)
    ground_truth = Column(String)
    agent_answer_snippet = Column(String)
    elapsed_s = Column(Float, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    run_id = Column(String, index=True, nullable=True)
    username = Column(String, index=True, nullable=True, default=DEFAULT_USERNAME)


class TaskRun(Base):
    __tablename__ = "task_runs"
    
    id = Column(String, primary_key=True, index=True)
    task_type = Column(String)  # 'dab_query', 'spider_batch', etc.
    status = Column(String)     # 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    target_id = Column(String)  # e.g., 'bookreview_q1'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(String, nullable=True)


class PipelineRun(Base):
    """Stores per-run orchestrator evolution metrics for every query execution.

    This table answers: how many attempts were made, why did the loop exit, what
    quality score was achieved, and what did each attempt look like?  It is the
    single source of truth for pipeline progress analytics.
    """
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instance_id = Column(String, index=True)          # e.g. "patents_q1"
    dataset = Column(String, index=True)
    run_suffix = Column(String, default="")
    total_attempts = Column(Integer)
    evolution_score = Column(Float)                    # best quality_signal across attempts (0.0-1.3)
    final_verdict = Column(String)                     # SOLVED / PARTIAL / FAILED
    satisfaction_score = Column(Float, nullable=True)  # 0.0-1.0, derived from validator
    termination_reason = Column(String)                # why the loop exited
    best_sql = Column(Text, nullable=True)
    best_row_count = Column(Integer, nullable=True)
    total_latency_s = Column(Float, nullable=True)
    evolution_json = Column(Text, nullable=True)       # JSON list of per-attempt metric dicts
    smartness_score = Column(Float, nullable=True)     # 0-100 score: higher = smarter pipeline
    smartness_grade = Column(String, nullable=True)    # EXCEPTIONAL/GOOD/ADEQUATE/POOR/FAILED
    timestamp = Column(DateTime, default=datetime.utcnow)


for attempt in range(5):
    try:
        Base.metadata.create_all(bind=engine)
        break
    except Exception as e:
        if "locked" in str(e).lower() and attempt < 4:
            import time
            import random
            time.sleep(random.uniform(0.1, 0.5))
            continue
        raise e

