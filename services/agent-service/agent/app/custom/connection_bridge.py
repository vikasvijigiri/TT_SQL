"""
connection_bridge.py
--------------------
Converts a CustomProjectsScreen connection dict into a connection string URI
and provides a patched DatabaseExecutor for custom connections.

The patch is required for PostgreSQL: DatabaseExecutor._get_postgres_conn_str()
reads credentials from sf_credentials.json / env vars, NOT from the parsed
connection config.  We monkey-patch the instance method so the executor uses
the project's own credentials.
"""

from __future__ import annotations

from typing import Any, Dict

from agent.app.core.connection import parse_connection, ConnectionConfig
from agent.services.db_executor import DatabaseExecutor


def project_to_connection_string(conn: Dict[str, Any]) -> str:
    """Convert a project connection dict to a SQLAlchemy-compatible URI."""
    db_type = (conn.get("db_type") or "").lower()

    if db_type in ("sqlite",):
        path = conn.get("sqlite_path") or ""
        path = path.replace("\\", "/")
        return f"sqlite:///{path}"

    if db_type == "bulk_sqlite":
        path = conn.get("db_root") or conn.get("sqlite_path") or ""
        path = path.replace("\\", "/")
        return f"sqlite:///{path}"

    if db_type in ("postgres", "postgresql"):
        user = conn.get("user") or "postgres"
        password = conn.get("password") or ""
        host = conn.get("host") or "localhost"
        port = conn.get("port") or "5432"
        database = conn.get("database") or conn.get("db_name") or "postgres"
        # URL-encode special chars in password
        from urllib.parse import quote_plus
        return f"postgresql://{user}:{quote_plus(str(password))}@{host}:{port}/{database}"

    if db_type == "snowflake":
        user = conn.get("user") or ""
        password = conn.get("password") or ""
        account = conn.get("host") or ""
        database = conn.get("database") or ""
        schema = conn.get("db_name") or "PUBLIC"
        warehouse = conn.get("sf_warehouse") or ""
        role = conn.get("sf_role") or ""
        from urllib.parse import quote_plus
        uri = f"snowflake://{user}:{quote_plus(str(password))}@{account}/{database}/{schema}"
        params = []
        if warehouse:
            params.append(f"warehouse={warehouse}")
        if role:
            params.append(f"role={role}")
        if params:
            uri += "?" + "&".join(params)
        return uri

    if db_type == "bigquery":
        project = conn.get("database") or ""
        dataset = conn.get("db_name") or ""
        creds = conn.get("bq_credentials_path") or ""
        uri = f"bigquery://{project}/{dataset}"
        if creds:
            from urllib.parse import quote_plus
            uri += f"?credentials_path={quote_plus(creds)}"
        return uri

    raise ValueError(f"Unsupported db_type: {db_type!r}")


def _pg_dsn_from_conn(conn: Dict[str, Any]) -> str:
    """Build a psycopg2-style DSN from raw project connection fields."""
    host = conn.get("host") or "localhost"
    port = conn.get("port") or 5432
    user = conn.get("user") or "postgres"
    password = conn.get("password") or ""
    database = conn.get("database") or conn.get("db_name") or "postgres"
    return f"host={host} port={port} user={user} password={password} dbname={database}"


def make_executor(conn: Dict[str, Any]) -> DatabaseExecutor:
    """Create a DatabaseExecutor for a custom connection, with PostgreSQL fix."""
    conn_str = project_to_connection_string(conn)
    executor = DatabaseExecutor(connection_string=conn_str)

    db_type = (conn.get("db_type") or "").lower()
    if db_type in ("postgres", "postgresql"):
        pg_dsn = _pg_dsn_from_conn(conn)
        executor._get_postgres_conn_str = lambda: pg_dsn  # type: ignore[method-assign]

    return executor


def patch_orchestrator_executor(orchestrator: Any, conn: Dict[str, Any]) -> None:
    """Patch an existing orchestrator's executor for PostgreSQL custom connections."""
    db_type = (conn.get("db_type") or "").lower()
    if db_type in ("postgres", "postgresql"):
        pg_dsn = _pg_dsn_from_conn(conn)
        orchestrator.executor._get_postgres_conn_str = lambda: pg_dsn  # type: ignore[method-assign]
        if hasattr(orchestrator, "stabilizer") and hasattr(orchestrator.stabilizer, "executor"):
            orchestrator.stabilizer.executor._get_postgres_conn_str = lambda: pg_dsn  # type: ignore[method-assign]
