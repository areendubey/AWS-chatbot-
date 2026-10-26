"""
Database engine and session configuration.
Compatible with SQLite (local development and tests) and PostgreSQL (production).
Designed to easily swap with the team's shared `app.db.base` / `app.db.session` once merged.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.escalations.config import get_settings


class Base(DeclarativeBase):
    """
    SQLAlchemy Declarative Base.
    When moving to the team's shared database module, this can be replaced by:
        from app.db.base import Base
    """
    pass


def get_engine():
    settings = get_settings()
    db_url = settings.database_url
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(db_url, connect_args=connect_args)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session.
    Can be replaced later by:
        from app.db.session import get_db
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
