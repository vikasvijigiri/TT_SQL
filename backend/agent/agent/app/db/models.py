from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from agent.app.db.database import Base, engine
from datetime import datetime

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
    username = Column(String, index=True, nullable=True, default="vikasvijigiri")


class TaskRun(Base):
    __tablename__ = "task_runs"
    
    id = Column(String, primary_key=True, index=True)
    task_type = Column(String)  # 'dab_query', 'spider_batch', etc.
    status = Column(String)     # 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'
    target_id = Column(String)  # e.g., 'bookreview_q1'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_message = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)
