import os
from typing import Optional, Dict, Any
import time
import threading
from app.services.agents.base import BaseAgent
from app.schemas.agent_state import AgentState, ExecutionResult
from app.core.logger import Logger
from app.db.sql_repo import DBRepository
from app.repositories.file_coordinator import FileCoordinator
from app.core.settings import settings
from app.repositories.paths import InstancePaths

class SQLiteExecutorAgent(BaseAgent):
    """
    SQLiteExecutorAgent executes SQL queries against a local SQLite database.
    It utilizes the centralized DBRepository for all database interactions.
    """
    def __init__(self, db_path: Optional[str] = None, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None, user_slug: str = None):
        super().__init__(name="SQLiteExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)

    @classmethod
    def reset_connection_pool(cls):
        """Reset connection pool. No-op for SQLite since it uses file-based connections."""
        pass

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query:
            self.log(state, "No query provided for execution.")
            return state

        start_t = time.time()
        # Use centralized repository for execution
        result = DBRepository.execute_query(
            query=state.chosen_query,
            db_type="sqlite",
            db_path=getattr(state, "db_path", None),
            user_slug=self.user_slug
        )
        result.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = result

        if result.error_message:
            self.log(state, f"SQLite Execution Failure: {result.error_message}", level="ERROR")
            if result.error_message not in state.execution_error_history:
                state.execution_error_history.append(f"SQL Error: {result.error_message}")
        else:
            self.log(state, f"Execution completed in {result.execution_time_ms:.2f}ms. Returned {result.row_count} records.")
        
        threading.Thread(target=self._bg_persist_results, args=(state, result), daemon=True).start()
        return state

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            self.file_coordinator.write_csv(
                state.instance_id, 
                result.rows if not result.error_message else [["failed", result.error_message]], 
                result.columns if not result.error_message else ["status", "error"], 
                state.model_name
            )
        except Exception:
            pass
       

class PostgresExecutorAgent(BaseAgent):
    """
    PostgresExecutorAgent executes SQL queries against PostgreSQL instances.
    It utilizes the centralized DBRepository for all database interactions.
    """
    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None, user_slug: str = None):
        super().__init__(name="PostgresExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)

    @classmethod
    def reset_connection_pool(cls):
        """Reset connection pool. No-op for DBRepository managed connections."""
        pass

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query:
            self.log(state, "No valid query provided for RDS execution.")
            return state

        start_t = time.time()
        # Use centralized repository for execution
        result = DBRepository.execute_query(
            query=state.chosen_query,
            db_type="postgres",
            db_name=getattr(state, "db_name", "public"),
            user_slug=self.user_slug
        )
        result.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = result
        
        if result.error_message:
            self.log(state, f"RDS Execution Failure: {result.error_message}", level="ERROR")
            if result.error_message not in state.execution_error_history:
                state.execution_error_history.append(f"Postgres Error: {result.error_message}")
        else:
            self.log(state, f"RDS Execution completed in {result.execution_time_ms:.2f}ms. Rows: {result.row_count}")
        
        threading.Thread(target=self._bg_persist_results, args=(state, result), daemon=True).start()
        return state

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            self.file_coordinator.write_csv(
                state.instance_id, 
                result.rows if not result.error_message else [["failed", result.error_message]], 
                result.columns if not result.error_message else ["status", "error"], 
                state.model_name
            )
        except Exception:
            pass

class BigQueryExecutorAgent(BaseAgent):
    """
    Executes SQL queries against Google Cloud BigQuery using DBRepository.
    """
    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None, user_slug: str = None):
        super().__init__(name="BigQueryExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)

    @classmethod
    def reset_connection_pool(cls):
        """Reset connection pool. No-op for DBRepository managed connections."""
        pass

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query: return state
        start_t = time.time()
        res = DBRepository.execute_query(state.chosen_query, db_type="bigquery", user_slug=self.user_slug)
        res.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = res
        
        if res.error_message:
            self.log(state, f"BigQuery Error: {res.error_message}", level="ERROR")
        else:
            self.log(state, f"BigQuery Success: {res.row_count} rows in {res.execution_time_ms:.2f}ms")
            
        threading.Thread(target=self._bg_persist_results, args=(state, res), daemon=True).start()
        return state

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            self.file_coordinator.write_csv(
                state.instance_id, 
                result.rows if not result.error_message else [["failed", result.error_message]], 
                result.columns if not result.error_message else ["status", "error"], 
                state.model_name
            )
        except Exception:
            pass

class SnowflakeExecutorAgent(BaseAgent):
    """
    Executes SQL queries against Snowflake using DBRepository.
    """
    def __init__(self, results_dir: str = None, logs_dir: str = None, metadata_dir: str = None, user_slug: str = None):
        super().__init__(name="SnowflakeExecutor", results_dir=results_dir, logs_dir=logs_dir, metadata_dir=metadata_dir, user_slug=user_slug)
        self.file_coordinator = FileCoordinator(results_dir=results_dir, logs_dir=logs_dir, user_slug=user_slug)

    @classmethod
    def reset_connection_pool(cls):
        """Reset connection pool. No-op for DBRepository managed connections."""
        pass

    def run(self, state: AgentState, on_token: callable = None) -> AgentState:
        if not state.chosen_query: return state
        start_t = time.time()
        res = DBRepository.execute_query(state.chosen_query, db_type="snowflake", user_slug=self.user_slug)
        res.execution_time_ms = (time.time() - start_t) * 1000
        state.execution_result = res
        
        if res.error_message:
            self.log(state, f"Snowflake Error: {res.error_message}", level="ERROR")
        else:
            self.log(state, f"Snowflake Success: {res.row_count} rows in {res.execution_time_ms:.2f}ms")
            
        threading.Thread(target=self._bg_persist_results, args=(state, res), daemon=True).start()
        return state

    def _bg_persist_results(self, state: AgentState, result: ExecutionResult):
        try:
            self.file_coordinator.write_csv(
                state.instance_id, 
                result.rows if not result.error_message else [["failed", result.error_message]], 
                result.columns if not result.error_message else ["status", "error"], 
                state.model_name
            )
        except Exception:
            pass

