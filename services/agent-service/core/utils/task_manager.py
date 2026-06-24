from typing import Optional
from api.db.database import SessionLocal
from api.db.models import TaskRun
from core.dependencies import EXECUTION_POOL
import uuid
from datetime import datetime

class TaskManager:
    @staticmethod
    def start_task(task_type: str, target_id: str) -> str:
        db = SessionLocal()
        task_id = str(uuid.uuid4())
        try:
            task = TaskRun(
                id=task_id,
                task_type=task_type,
                status="RUNNING",
                target_id=target_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(task)
            db.commit()
            return task_id
        finally:
            db.close()

    @staticmethod
    def complete_task(task_id: str, success: bool, error_message: Optional[str] = None):
        db = SessionLocal()
        try:
            task = db.query(TaskRun).filter(TaskRun.id == task_id).first()
            if task:
                task.status = "COMPLETED" if success else "FAILED"
                task.error_message = error_message
                task.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    @staticmethod
    def get_running_tasks():
        db = SessionLocal()
        try:
            tasks = db.query(TaskRun).filter(TaskRun.status == "RUNNING").all()
            return [{"id": t.id, "type": t.task_type, "target": t.target_id} for t in tasks]
        finally:
            db.close()
