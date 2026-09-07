"""
Database engine / session management.

* Hackathon: SQLite file at data/cashguard.db
* Production: set DATABASE_URL to a PostgreSQL DSN — the ORM layer and all
  repositories work unchanged (SQLAlchemy abstracts the dialect).

Data-access note: no route handler ever touches SQLAlchemy directly; every
query goes through backend/repositories.py so that a future swap from
"local DB" to "NCRP/CFCFRMS API + bank data APIs" only rewrites repositories.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# SQLite needs check_same_thread=False because FastAPI serves requests from a
# thread pool while the APScheduler alert job may run on another thread.
_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        """Per-connection pragmas: WAL (readers never block the writer) and a
        30s busy timeout instead of an immediate OperationalError — this is what
        keeps the live demo from dying with "database is locked" when the
        scheduler's alert cycle, a webhook-triggered request, and a dashboard
        poll overlap on the single SQLite file."""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist. Called on app startup."""
    from . import models  # noqa: F401  (registers ORM classes on Base.metadata)

    Base.metadata.create_all(bind=engine)