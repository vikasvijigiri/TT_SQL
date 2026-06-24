import sqlite3
import os
import json
from datetime import datetime
from config.config import CONFIG_DIR
from core.utils.logger import logger

LEARNING_DB_PATH = CONFIG_DIR.parent / "knowledge" / "learning.db"

class SQLiteMemoryDB:
    def __init__(self, db_path: str = str(LEARNING_DB_PATH)):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # SUCCESS MEMORY
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS success_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_pattern TEXT NOT NULL,
                    schema_pattern TEXT NOT NULL,
                    reasoning_pattern TEXT NOT NULL,
                    successful_strategy TEXT NOT NULL,
                    confidence REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # FAILURE MEMORY
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS failure_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    failure_type TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    fix TEXT NOT NULL,
                    prevention_rule TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # SQL REPAIR MEMORY
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sql_repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bad_sql TEXT NOT NULL,
                    error TEXT NOT NULL,
                    fixed_sql TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # PATTERN LIBRARIES
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS schema_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    common_tables TEXT NOT NULL,  -- JSON list
                    common_joins TEXT NOT NULL,   -- JSON list
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reasoning_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT NOT NULL,
                    required_evidence TEXT NOT NULL, -- JSON list
                    reasoning_steps TEXT NOT NULL,   -- JSON list
                    success_rate REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info(f"Initialized SQLite Learning Engine at {self.db_path}")

    def insert_success(self, question: str, schema: str, reasoning: str, strategy: str, conf: float):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO success_patterns (question_pattern, schema_pattern, reasoning_pattern, successful_strategy, confidence) VALUES (?, ?, ?, ?, ?)",
                (question, schema, reasoning, strategy, conf)
            )
            conn.commit()

    def insert_failure(self, f_type: str, root_cause: str, fix: str, rule: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO failure_patterns (failure_type, root_cause, fix, prevention_rule) VALUES (?, ?, ?, ?)",
                (f_type, root_cause, fix, rule)
            )
            conn.commit()

    def search_similar_failures(self, query: str, limit: int = 5) -> list[dict]:
        """Simple text-based LIKE search for now. Upgradable to FTS5 or vector search."""
        words = [f"%{w}%" for w in query.split() if len(w) > 3]
        if not words:
            return []
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Construct dynamic OR clauses for basic keyword match
            clauses = " OR ".join(["root_cause LIKE ?" for _ in words])
            cursor.execute(f"SELECT * FROM failure_patterns WHERE {clauses} LIMIT ?", (*words, limit))
            return [dict(row) for row in cursor.fetchall()]

    def search_similar_successes(self, query: str, limit: int = 3) -> list[dict]:
        words = [f"%{w}%" for w in query.split() if len(w) > 3]
        if not words:
            return []
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            clauses = " OR ".join(["question_pattern LIKE ?" for _ in words])
            cursor.execute(f"SELECT * FROM success_patterns WHERE {clauses} LIMIT ?", (*words, limit))
            return [dict(row) for row in cursor.fetchall()]
