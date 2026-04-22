import os
import time

import psycopg2

from core.agent_base import AgentState, BaseAgent
from core.bq_service import BigQueryService
from core.file_coordinator import FileCoordinator
from core.logger import Logger
from core.sf_service import SnowflakeService
from core.sqlite_service import SQLiteService
from core.state import ExecutionResult


class SQLiteExecutorAgent(BaseAgent):
    """Agent responsible for executing SQL queries on SQLite databases.

    This agent uses the SQLiteService to run generated SQL and captures
    results, timing, and any execution errors.
    """

    def __init__(self, db_path: str | None = None):
        """Initializes the SQLiteExecutorAgent.

        Args:
            db_path (str, optional): Path to the SQLite database file.
        """
        super().__init__(name="SQLiteExecutor")
        self.file_coordinator = FileCoordinator()
        self.db_path = db_path

    def run(self, state: AgentState) -> AgentState:
        """Executes the SQLite query workflow.

        Args:
            state (AgentState): The current shared state (contains chosen_query).

        Returns:
            AgentState: The updated state containing the execution_result.
        """
        Logger.log_call(f"{self.name}.run", {"db_path": state.db_path})
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            self.log(state, "No valid SQL query chosen to execute.")
            return state

        svc = SQLiteService(state.db_path)
        sampling = getattr(state, "sampling_enabled", False)
        result = svc.execute_query(state.chosen_query, sampling=sampling)

        if result.error_message:
            state.error_message = result.error_message
            self.log(state, f"Execution Error: {result.error_message}")
            state.execution_error_history.append(f"SQL Error: {result.error_message}")

        state.execution_result = result
        self.log(
            state,
            f"Executed query. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms",
        )

        if result.error_message:
            self.file_coordinator.write_csv(
                state.instance_id,
                [["failed", result.error_message]],
                ["status", "error"],
                state.model_name,
            )
        else:
            self.file_coordinator.write_csv(
                state.instance_id, result.rows, result.columns, state.model_name
            )

        return state


class BigQueryExecutorAgent(BaseAgent):
    """Agent responsible for executing SQL queries on Google BigQuery.

    This agent uses the BigQuery client to run queries against GCP datasets
    and captures the result schema and data rows.
    """

    def __init__(self):
        """Initializes the BigQueryExecutorAgent."""
        super().__init__(name="BigQueryExecutor")
        self.file_coordinator = FileCoordinator()
        self.bq_service = BigQueryService()

    def run(self, state: AgentState) -> AgentState:
        """Executes the BigQuery query workflow.

        Args:
            state (AgentState): The current shared state (contains chosen_query).

        Returns:
            AgentState: The updated state containing the execution_result.
        """
        Logger.log_call(f"{self.name}.run")
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            return state

        client = self.bq_service.get_client()
        start_t = time.time()
        result = ExecutionResult()

        try:
            query_job = client.query(state.chosen_query)
            rows = query_job.result()
            result.columns = [field.name for field in rows.schema]
            all_rows = [list(row.values()) for row in rows]
            result.rows = (
                all_rows[:5] if getattr(state, "sampling_enabled", False) else all_rows
            )
            result.row_count = len(all_rows)
        except Exception as e:
            result.error_message = str(e)
            state.error_message = str(e)
            self.log(state, f"BigQuery Execution Error: {e}")
            state.execution_error_history.append(f"BigQuery Error: {str(e)}")
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(
            state,
            f"Executed BigQuery. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms",
        )
        self.file_coordinator.write_csv(
            state.instance_id,
            result.rows
            if not result.error_message
            else [["failed", result.error_message]],
            result.columns if not result.error_message else ["status", "error"],
            state.model_name,
        )
        return state


class SnowflakeExecutorAgent(BaseAgent):
    """Agent responsible for executing SQL queries on Snowflake.

    This agent uses the Snowflake connector to run queries and
    captures the resulting data and metadata.
    """

    def __init__(self):
        """Initializes the SnowflakeExecutorAgent."""
        super().__init__(name="SnowflakeExecutor")
        self.file_coordinator = FileCoordinator()
        self.sf_service = SnowflakeService()

    def run(self, state: AgentState) -> AgentState:
        """Executes the Snowflake query workflow.

        Args:
            state (AgentState): The current shared state (contains chosen_query).

        Returns:
            AgentState: The updated state containing the execution_result.
        """
        Logger.log_call(f"{self.name}.run")
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            return state

        database = state.db_name
        schema = "PUBLIC"
        if database and "." in database:
            parts = database.split(".")
            database, schema = parts[0], parts[1]

        conn = self.sf_service.get_connection(database=database, schema=schema)
        if not conn:
            state.error_message = "Failed to establish Snowflake connection."
            return state

        start_t = time.time()
        result = ExecutionResult()
        try:
            cursor = conn.cursor()
            cursor.execute(state.chosen_query)
            result.columns = (
                [desc[0] for desc in cursor.description] if cursor.description else []
            )
            rows = (
                cursor.fetchmany(5)
                if getattr(state, "sampling_enabled", False)
                else cursor.fetchall()
            )
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
        except Exception as e:
            result.error_message = str(e)
            state.error_message = str(e)
            self.log(state, f"Snowflake Execution Error: {e}")
            state.execution_error_history.append(f"Snowflake Error: {str(e)}")
        finally:
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(
            state,
            f"Executed Snowflake. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms",
        )
        self.file_coordinator.write_csv(
            state.instance_id,
            result.rows
            if not result.error_message
            else [["failed", result.error_message]],
            result.columns if not result.error_message else ["status", "error"],
            state.model_name,
        )
        return state


class PostgresExecutorAgent(BaseAgent):
    """Agent responsible for executing SQL queries on PostgreSQL.

    This agent uses psycopg2 to run queries against Postgres/RDS
    instances and captures the result set.
    """

    def __init__(self):
        """Initializes the PostgresExecutorAgent."""
        super().__init__(name="PostgresExecutor")
        self.file_coordinator = FileCoordinator()

    def run(self, state: AgentState) -> AgentState:
        """Executes the Postgres query workflow.

        Args:
            state (AgentState): The current shared state (contains chosen_query).

        Returns:
            AgentState: The updated state containing the execution_result.
        """
        Logger.log_call(f"{self.name}.run")
        if not state.chosen_query or state.chosen_query.upper().startswith("ERROR"):
            return state

        host = os.getenv("RDS_HOST")
        database = os.getenv("RDS_DATABASE", "postgres")
        user = os.getenv("RDS_USER")
        password = os.getenv("RDS_PASSWORD")
        port = os.getenv("RDS_PORT", "5432")
        schema = os.getenv("SCHEMA", "public").strip().replace('"', "")

        start_t = time.time()
        result = ExecutionResult()
        conn = None
        try:
            conn = psycopg2.connect(
                host=host,
                database=database,
                user=user,
                password=password,
                port=port,
                connect_timeout=10,
            )
            conn.autocommit = True
            cursor = conn.cursor()
            if schema and schema.lower() != "public":
                cursor.execute(f'SET search_path TO "{schema}", public;')
            cursor.execute(state.chosen_query)
            result.columns = (
                [desc[0] for desc in cursor.description] if cursor.description else []
            )
            rows = (
                cursor.fetchmany(5)
                if getattr(state, "sampling_enabled", False)
                else cursor.fetchall()
            )
            result.rows = [list(row) for row in rows]
            result.row_count = len(rows)
        except Exception as e:
            result.error_message = str(e)
            state.error_message = str(e)
            self.log(state, f"Postgres Execution Error: {e}")
            state.execution_error_history.append(f"Postgres Error: {str(e)}")
        finally:
            if conn:
                conn.close()
            result.execution_time_ms = (time.time() - start_t) * 1000

        state.execution_result = result
        self.log(
            state,
            f"Executed Postgres. Rows: {result.row_count}. Time: {result.execution_time_ms:.2f}ms",
        )
        self.file_coordinator.write_csv(
            state.instance_id,
            result.rows
            if not result.error_message
            else [["failed", result.error_message]],
            result.columns if not result.error_message else ["status", "error"],
            state.model_name,
        )
        return state
