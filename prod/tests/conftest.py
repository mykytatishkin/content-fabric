"""Shared fixtures for the CFF test suite."""

import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# ── Environment setup (before any app imports) ────────────────────
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["CFF_AUDIT_LOG"] = os.path.join(tempfile.gettempdir(), "cff-audit-test.log")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_DATABASE", "content_fabric_test")
os.environ.setdefault("MYSQL_USER", "test_user")
os.environ.setdefault("MYSQL_PASSWORD", "test_pass")

# Mock heavy deps unavailable on Windows
for _mod in ("rq", "rq.queue", "rq.job", "rq.worker",
             "googleapiclient", "googleapiclient.discovery",
             "googleapiclient.http", "googleapiclient.errors",
             "google.oauth2", "google.oauth2.credentials",
             "google.auth.transport.requests"):
    sys.modules.setdefault(_mod, MagicMock())


# ── Mock DB connection ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_engine():
    """Ensure global engine is reset between tests."""
    from shared.db import connection
    connection._engine = None
    yield
    connection._engine = None


# ── FastAPI test client ────────────────────────────────────────────

@pytest.fixture()
def app_client():
    """FastAPI TestClient with DB mocked."""
    from contextlib import contextmanager
    from fastapi.testclient import TestClient

    conn = MagicMock()
    result_mock = MagicMock()
    result_mock.fetchone.return_value = None
    result_mock.fetchall.return_value = []
    result_mock.rowcount = 0
    result_mock.lastrowid = 1
    result_mock.scalar.return_value = 0
    result_mock.mappings.return_value.fetchall.return_value = []
    conn.execute.return_value = result_mock

    @contextmanager
    def _fake_conn():
        yield conn

    with patch("shared.db.connection.get_connection", _fake_conn), \
         patch("shared.db.connection.get_engine", return_value=MagicMock()):
        from main import app
        yield TestClient(app)


# ── Auth helpers ───────────────────────────────────────────────────

TEST_USER = {
    "id": 1, "uuid": "test-uuid-1234", "username": "testuser",
    "email": "test@example.com", "password_hash": "hashed",
    "display_name": "Test User", "avatar_url": None,
    "status": 10, "timezone": "UTC",
    "totp_secret": None, "totp_enabled": False, "totp_backup_codes": None,
    "created_at": datetime(2026, 1, 1), "updated_at": datetime(2026, 1, 1),
}

ADMIN_USER = {
    **TEST_USER, "id": 2, "status": 1,
    "username": "admin", "email": "admin@example.com",
}


@pytest.fixture()
def auth_headers():
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token({'sub': 1})}"}


@pytest.fixture()
def admin_headers():
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token({'sub': 2})}"}
