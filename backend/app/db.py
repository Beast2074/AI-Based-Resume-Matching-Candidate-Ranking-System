"""
Database Configuration & Connection Management.
Supports serverless PostgreSQL on Neon (via NullPool & pgbouncer) and SQLite for local development.
"""

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool

# Determine database URL: default to SQLite in /tmp for serverless or backend directory locally
if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    DEFAULT_SQLITE_PATH = Path("/tmp/app.db")
else:
    DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent.parent / "app.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

connect_args = {}
engine_kwargs = {
    "pool_pre_ping": True,
}

if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
else:
    # Postgres configuration for serverless / pgbouncer
    engine_kwargs["poolclass"] = NullPool
    # psycopg 3 prepare_threshold=None disables server-side prepared statements (required for pgbouncer transaction pooling)
    if "psycopg" in DATABASE_URL or "postgresql" in DATABASE_URL:
        connect_args["prepare_threshold"] = None

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Creates database tables on startup if they do not exist."""
    Base.metadata.create_all(bind=engine)
