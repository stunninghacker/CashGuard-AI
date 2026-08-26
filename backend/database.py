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

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

# SQLite needs check_same_thread=False because FastAPI serves requests from a
# thread pool while the APScheduler alert job may run on another thread.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


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