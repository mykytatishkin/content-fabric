"""MySQL database connection and operations for channels service."""

from contextlib import contextmanager
from typing import Any, Generator

import mysql.connector
from mysql.connector import Error

from app.core.config import settings


def get_db_config() -> dict[str, Any]:
    return {
        "host": settings.MYSQL_HOST,
        "port": settings.MYSQL_PORT,
        "database": settings.MYSQL_DATABASE,
        "user": settings.MYSQL_USER,
        "password": settings.MYSQL_PASSWORD,
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": True,
    }


@contextmanager
def get_db_connection() -> Generator[mysql.connector.MySQLConnection, None, None]:
    """Context manager for database connection."""
    conn = None
    try:
        conn = mysql.connector.connect(**get_db_config())
        yield conn
    except Error:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn and conn.is_connected():
            conn.close()


def execute_query(
    conn: mysql.connector.MySQLConnection,
    query: str,
    params: tuple | None = None,
    fetch: bool = False,
) -> list[tuple] | None:
    """Execute SQL query."""
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        if fetch:
            return cursor.fetchall()
        conn.commit()
        return None
    except Error:
        conn.rollback()
        raise
    finally:
        cursor.close()
