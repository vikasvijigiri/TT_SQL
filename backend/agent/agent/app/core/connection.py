"""
connection.py
-------------
Universal connection string parser.

Given any URI, returns a ConnectionConfig describing:
  - dialect   : canonical DBMS keyword (sqlite, duckdb, postgresql, mysql,
                 mssql, bigquery, mongodb, snowflake, oracle, trino, ...)
  - db_name   : database / catalog name
  - host/port : for network DBs
  - path      : for file-based DBs
  - raw_uri   : the original string, ready to hand to SQLAlchemy

Supported URI schemes
---------------------
  sqlite:///absolute/path/to/db.db
  sqlite:///./relative/db.db
  duckdb:///path/to/db.duckdb
  postgresql://user:pass@host:5432/dbname      (alias: postgres://)
  mysql+mysqlconnector://user:pass@host/dbname  (alias: mysql://)
  mariadb+mariadbconnector://...
  mssql+pyodbc://server/dbname?driver=...
  bigquery://project/dataset
  mongodb://user:pass@host:27017/dbname        (alias: mongodb+srv://)
  snowflake://user:pass@account/db/schema?...
  oracle+cx_oracle://user:pass@host:1521/sid
  trino://user@host:8080/catalog/schema

No external dependencies Ã¢â‚¬â€ stdlib only (urllib.parse).
SQLAlchemy is NOT imported here so this module is always importable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Dict
from urllib.parse import urlparse, parse_qs, unquote


# Mapping from URI scheme (lower) Ã¢â€ â€™ canonical dialect keyword used
# throughout the pipeline (dialect rules, casting, SQL generation hints).
_SCHEME_TO_DIALECT: Dict[str, str] = {
    "sqlite": "sqlite",
    "duckdb": "duckdb",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql",
    "mysql+mysqlconnector": "mysql",
    "mysql+pymysql": "mysql",
    "mysql+aiomysql": "mysql",
    "mariadb": "mysql",
    "mariadb+mariadbconnector": "mysql",
    "mssql": "mssql",
    "mssql+pyodbc": "mssql",
    "mssql+pymssql": "mssql",
    "sqlserver": "mssql",
    "bigquery": "bigquery",
    "mongodb": "mongodb",
    "mongodb+srv": "mongodb",
    "snowflake": "snowflake",
    "oracle": "oracle",
    "oracle+cx_oracle": "oracle",
    "oracle+oracledb": "oracle",
    "trino": "trino",
    "presto": "trino",
    "redshift": "redshift",
    "redshift+redshift_connector": "redshift",
    "spark": "spark",
    "databricks": "spark",
    "hive": "hive",
}


@dataclass
class ConnectionConfig:
    dialect: str  # canonical dialect: sqlite / duckdb / postgresql / mysql / ...
    db_name: str  # catalog / database name (used for schema lookups)
    raw_uri: str  # original URI string, safe to pass to sqlalchemy.create_engine()
    schema_name: str = ""  # schema within the database (for multi-schema DBs)
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    path: Optional[str] = None  # for file-based DBs (sqlite / duckdb)
    extra_params: Dict[str, str] = field(default_factory=dict)

    # Whether this connection needs SQLAlchemy (vs. native driver in executor)
    @property
    def needs_sqlalchemy(self) -> bool:
        return self.dialect not in (
            "sqlite",
            "duckdb",
            "postgresql",
            "snowflake",
            "mongodb",
        )

    # psycopg2-style DSN string for PostgreSQL executor backend
    @property
    def pg_dsn(self) -> Optional[str]:
        if self.dialect != "postgresql":
            return None
        host = self.host or "localhost"
        port = self.port or 5432
        user = self.username or "postgres"
        pwd = self.password or ""
        db = self.db_name or "postgres"
        return f"host={host} port={port} user={user} password={pwd} dbname={db}"

    # SQLAlchemy-compatible URI (normalises scheme aliases)
    @property
    def sqlalchemy_url(self) -> str:
        return self.raw_uri


def parse_connection(uri: str) -> ConnectionConfig:
    """
    Parse any connection URI and return a ConnectionConfig.

    The function is intentionally lenient: unknown schemes are kept as-is
    so they can still be forwarded to SQLAlchemy. Dialect detection uses
    _SCHEME_TO_DIALECT; if the scheme is not in that map the scheme itself
    becomes the dialect keyword.
    """
    if not uri or not isinstance(uri, str):
        raise ValueError("Connection URI must be a non-empty string.")

    uri = uri.strip()

    # Ã¢â€â‚¬Ã¢â€â‚¬ 1. Parse the URI Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    parsed = urlparse(uri)
    scheme = (parsed.scheme or "").lower()

    # Handle "duckdb:///path" Ã¢â‚¬â€ urlparse maps this to netloc=""  path="/path"
    # Handle "sqlite:///path" similarly.

    dialect = _SCHEME_TO_DIALECT.get(scheme, scheme)  # unknown Ã¢â€ â€™ use scheme as-is

    # Ã¢â€â‚¬Ã¢â€â‚¬ 2. Extract host / port / user / password Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    host = parsed.hostname or None
    port = parsed.port or None
    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None

    # Ã¢â€â‚¬Ã¢â€â‚¬ 3. Derive db_name and schema_name from path segments Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    path_raw = parsed.path.lstrip("/")

    # File-based DBs: the whole path is the file path
    if dialect in ("sqlite", "duckdb"):
        # Reconstruct the absolute path from netloc + path
        # sqlite:///C:/path/to/db  Ã¢â€ â€™ netloc="", path="/C:/path/to/db"
        # sqlite:///./rel/db       Ã¢â€ â€™ netloc="", path="/./rel/db"
        full_path = (parsed.netloc or "") + parsed.path
        # Strip leading slash on Windows absolute paths like /C:/...
        if re.match(r"^/[A-Za-z]:/", full_path):
            full_path = full_path[1:]
        file_path = full_path or path_raw
        db_name = re.sub(
            r"\.(sqlite|sqlite3|db|duckdb)$",
            "",
            full_path.replace("\\", "/").split("/")[-1],
            flags=re.IGNORECASE,
        )
        return ConnectionConfig(
            dialect=dialect,
            db_name=db_name.upper() if db_name else "LOCAL",
            raw_uri=uri,
            path=file_path,
        )

    # Network DBs: path segments give catalog / schema
    segments = [s for s in path_raw.split("/") if s]

    db_name = segments[0] if len(segments) >= 1 else ""
    schema_name = segments[1] if len(segments) >= 2 else ""

    # BigQuery: uri = bigquery://project/dataset  Ã¢â€ â€™ db=project, schema=dataset
    if dialect == "bigquery":
        db_name = parsed.netloc or segments[0] if segments else ""
        schema_name = segments[0] if len(segments) >= 1 else ""

    # MongoDB: path="/dbname"
    if dialect == "mongodb":
        db_name = path_raw.split("?")[0].strip("/") or "default"
        schema_name = ""

    # Snowflake: path="/db/schema/warehouse" (optional segments)
    if dialect == "snowflake":
        db_name = segments[0] if segments else ""
        schema_name = segments[1] if len(segments) >= 2 else ""

    # Ã¢â€â‚¬Ã¢â€â‚¬ 4. Extra query-string params Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    extra: Dict[str, str] = {}
    if parsed.query:
        for k, vs in parse_qs(parsed.query).items():
            extra[k] = vs[0] if vs else ""

    return ConnectionConfig(
        dialect=dialect,
        db_name=(db_name or "").upper(),
        schema_name=schema_name or "",
        raw_uri=uri,
        host=host,
        port=port,
        username=username,
        password=password,
        extra_params=extra,
    )


def dialect_from_uri(uri: str) -> str:
    """Convenience: return just the dialect keyword from a URI."""
    return parse_connection(uri).dialect
