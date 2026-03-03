"""Tests for shared.db.repositories — mocked DB layer.

Each repo imports get_connection at module level, so we must patch it
in the repo's own namespace (not shared.db.connection).
"""

from datetime import datetime
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

import pytest


def _make_conn(fetchone=None, fetchall=None, rowcount=0, lastrowid=1):
    conn = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = fetchone
    result.fetchall.return_value = fetchall or []
    result.rowcount = rowcount
    result.lastrowid = lastrowid
    conn.execute.return_value = result
    return conn


@contextmanager
def _patch_repo(module_path: str, conn):
    """Patch get_connection in a specific repo module."""
    @contextmanager
    def _fake():
        yield conn
    with patch(f"{module_path}.get_connection", _fake):
        yield


# ── task_repo ──────────────────────────────────────────────────────

TASK_MOD = "shared.db.repositories.task_repo"


class TestTaskRepo:
    def test_get_task_not_found(self):
        conn = _make_conn(fetchone=None)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.get_task(999) is None

    def test_get_task_found(self):
        row = (
            1, 10, "video", 0,
            datetime(2026, 1, 1), "/tmp/v.mp4", None,
            "Title", "Desc", "kw1,kw2", None,
            None, datetime(2026, 3, 1), None,
            None, None, 0,
        )
        conn = _make_conn(fetchone=row)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            result = task_repo.get_task(1)
        assert result["id"] == 1
        assert result["title"] == "Title"

    def test_get_pending_tasks_empty(self):
        conn = _make_conn(fetchall=[])
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.get_pending_tasks() == []

    def test_mark_task_processing(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.mark_task_processing(1) is True

    def test_mark_task_completed(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.mark_task_completed(1, upload_id="abc") is True

    def test_mark_task_failed(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.mark_task_failed(1, "boom") is True

    def test_cancel_task(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.cancel_task(1) is True

    def test_cancel_nonexistent(self):
        conn = _make_conn(rowcount=0)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.cancel_task(999) is False

    def test_delete_task(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.delete_task(1) is True


# ── channel_repo ───────────────────────────────────────────────────

CH_MOD = "shared.db.repositories.channel_repo"


class TestChannelRepo:
    def test_get_channel_not_found(self):
        conn = _make_conn(fetchone=None)
        with _patch_repo(CH_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.get_channel_by_id(999) is None

    def test_get_channel_found(self):
        row = (1, "Ch", "UC123", 5, 1, 1, "at", "rt", None, 9, datetime(2026, 1, 1), datetime(2026, 1, 1))
        conn = _make_conn(fetchone=row)
        with _patch_repo(CH_MOD, conn):
            from shared.db.repositories import channel_repo
            result = channel_repo.get_channel_by_id(1)
        assert result["name"] == "Ch"
        assert result["enabled"] is True

    def test_list_channels_empty(self):
        conn = _make_conn(fetchall=[])
        with _patch_repo(CH_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.list_channels() == []

    def test_channel_exists_false(self):
        conn = _make_conn(fetchone=None)
        with _patch_repo(CH_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.channel_exists_by_name("nope") is False

    def test_channel_exists_true(self):
        conn = _make_conn(fetchone=(1,))
        with _patch_repo(CH_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.channel_exists_by_name("yes") is True

    def test_update_tokens(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(CH_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.update_channel_tokens(1, "new_tok") is True


# ── user_repo ──────────────────────────────────────────────────────

USER_MOD = "shared.db.repositories.user_repo"


class TestUserRepo:
    def test_get_user_not_found(self):
        conn = _make_conn(fetchone=None)
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            assert user_repo.get_user_by_id(999) is None

    def test_get_user_found(self):
        row = (
            1, "uuid-1", "testuser", "test@x.com", "hash",
            "Test", None, 10, "UTC", None, False, None,
            datetime(2026, 1, 1), datetime(2026, 1, 1),
        )
        conn = _make_conn(fetchone=row)
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            result = user_repo.get_user_by_id(1)
        assert result["username"] == "testuser"

    def test_create_user(self):
        conn = _make_conn(lastrowid=42)
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            uid = user_repo.create_user("u", "user", "e@x.com", "hash", "key")
        assert uid == 42

    def test_update_last_login(self):
        conn = _make_conn()
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            user_repo.update_last_login(1)
        conn.execute.assert_called_once()


# ── credential_repo ────────────────────────────────────────────────

CRED_MOD = "shared.db.repositories.credential_repo"


class TestCredentialRepo:
    def test_get_credentials_not_found(self):
        conn = _make_conn(fetchone=None)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            assert credential_repo.get_credentials(999) is None

    def test_get_credentials_found(self):
        row = (
            1, 10, "email@t.com", "pass", "SECRET", None,
            "proxy", 8080, "pu", "pp", "/path", "ua",
            None, None, None, True, datetime(2026, 1, 1), datetime(2026, 1, 1),
        )
        conn = _make_conn(fetchone=row)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            result = credential_repo.get_credentials(10)
        assert result["totp_secret"] == "SECRET"

    def test_update_totp(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            assert credential_repo.update_totp_secret(10, "NEW") is True

    def test_disable(self):
        conn = _make_conn(rowcount=1)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            assert credential_repo.disable_credentials(10) is True
