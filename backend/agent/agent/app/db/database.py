from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from agent.app.core.config import RESULTS_DIR, DEFAULT_USERNAME

DB_PATH = RESULTS_DIR / "nquire.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)

# Enable WAL mode so concurrent readers don't block on writers
@event.listens_for(engine, "connect")
def _set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=10000")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def migrate_db():
    try:
        # Check if evaluations table exists and apply any pending migrations
        with engine.connect() as conn:
            res_tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='evaluations'"))
            if res_tables.fetchone():
                res = conn.execute(text("PRAGMA table_info(evaluations)"))
                columns = [row[1] for row in res.fetchall()]

                # Migration: add run_id column (original migration)
                if "run_id" not in columns:
                    conn.execute(text("ALTER TABLE evaluations ADD COLUMN run_id VARCHAR DEFAULT NULL"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evaluations_run_id ON evaluations (run_id)"))
                    conn.commit()
                    print("Migrated DB: added run_id column.")

                # Migration: add username column to separate data per user
                if "username" not in columns:
                    conn.execute(text(f"ALTER TABLE evaluations ADD COLUMN username VARCHAR DEFAULT '{DEFAULT_USERNAME}'"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_evaluations_username ON evaluations (username)"))
                    # Backfill all existing rows to the current owner
                    conn.execute(text(f"UPDATE evaluations SET username = '{DEFAULT_USERNAME}' WHERE username IS NULL"))
                    conn.commit()
                    print(f"Migrated DB: added username column and backfilled existing rows to '{DEFAULT_USERNAME}'.")
    except Exception as e:
        print(f"Database migration failed: {e}")

migrate_db()

