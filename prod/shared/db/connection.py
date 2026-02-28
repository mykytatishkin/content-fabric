"""SQLAlchemy engine with connection pooling for shared DB access."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

_engine: Engine | None = None


def _build_url() -> str:
    host = os.environ.get("MYSQL_HOST", "localhost")
    port = os.environ.get("MYSQL_PORT", "3306")
    db = os.environ.get("MYSQL_DATABASE", "content_fabric")
    user = os.environ.get("MYSQL_USER", "dev_user")
    password = os.environ.get("MYSQL_PASSWORD", "dev_pass")
    return f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4"


def get_engine() -> Engine:
    """Get or create the global SQLAlchemy engine with connection pooling."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            _build_url(),
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
    return _engine


def dispose_engine() -> None:
    """Dispose engine and release all connections (for testing/shutdown)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """Context manager yielding a SQLAlchemy connection with auto-commit."""
    engine = get_engine()
    with engine.connect() as conn:
        yield conn
        conn.commit()
