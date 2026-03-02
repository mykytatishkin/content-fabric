"""Extended repository tests — console, audit, stats, template, credential updates."""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


def _make_conn(fetchone=None, fetchall=None, rowcount=0, lastrowid=1, scalar=0):
    """Create a mock DB connection."""
    conn = MagicMock()
    result = MagicMock()
    result.fetchone.return_value = fetchone
    result.fetchall.return_value = fetchall or []
    result.rowcount = rowcount
    result.lastrowid = lastrowid
    result.scalar.return_value = scalar
    result.mappings.return_value.fetchall.return_value = fetchall or []
    conn.execute.return_value = result
    return conn, result


@contextmanager
def _patch_repo(module_path: str, conn):
    """Patch get_connection in a specific repo module namespace."""
    @contextmanager
    def _fake():
        yield conn

    with patch(f"{module_path}.get_connection", _fake):
        yield


# ── Console repo ──────────────────────────────────────────────────

CONSOLE_MOD = "shared.db.repositories.console_repo"


class TestConsoleRepo:
    def test_list_consoles_empty(self):
        conn, _ = _make_conn(fetchall=[])
        with _patch_repo(CONSOLE_MOD, conn):
            from shared.db.repositories import console_repo
            assert console_repo.list_consoles() == []

    def test_get_console_by_id_not_found(self):
        conn, _ = _make_conn(fetchone=None)
        with _patch_repo(CONSOLE_MOD, conn):
            from shared.db.repositories import console_repo
            assert console_repo.get_console_by_id(999) is None

    def test_get_console_by_id_found(self):
        row = (1, 1, "Console1", "gcp-proj", "client123", "secret", None,
               '["http://localhost"]', "desc", 1, datetime.now(), datetime.now())
        conn, _ = _make_conn(fetchone=row)
        with _patch_repo(CONSOLE_MOD, conn):
            from shared.db.repositories import console_repo
            result = console_repo.get_console_by_id(1)
            assert result is not None
            assert result["name"] == "Console1"
            assert result["redirect_uris"] == ["http://localhost"]
            assert result["enabled"] is True

    def test_get_console_by_name(self):
        row = (2, 1, "Test", None, "cid", "sec", None, None, None, 1,
               datetime.now(), datetime.now())
        conn, _ = _make_conn(fetchone=row)
        with _patch_repo(CONSOLE_MOD, conn):
            from shared.db.repositories import console_repo
            result = console_repo.get_console_by_name("Test")
            assert result is not None
            assert result["id"] == 2

    def test_add_console_success(self):
        conn, result = _make_conn(lastrowid=5)
        project_row = MagicMock()
        project_row.fetchone.return_value = (1,)
        conn.execute.side_effect = [project_row, result]
        with _patch_repo(CONSOLE_MOD, conn):
            from shared.db.repositories import console_repo
            cid = console_repo.add_console("NewConsole", "client_id", "client_secret")
            assert cid == 5

    def test_delete_console_success(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(CONSOLE_MOD, conn):
            from shared.db.repositories import console_repo
            assert console_repo.delete_console(1) is True

    def test_delete_console_not_found(self):
        conn, _ = _make_conn(rowcount=0)
        with _patch_repo(CONSOLE_MOD, conn):
            from shared.db.repositories import console_repo
            assert console_repo.delete_console(999) is False


# ── Audit repo ────────────────────────────────────────────────────

AUDIT_MOD = "shared.db.repositories.audit_repo"


class TestAuditRepo:
    def test_create_reauth_audit(self):
        conn, _ = _make_conn(lastrowid=10)
        with _patch_repo(AUDIT_MOD, conn):
            from shared.db.repositories import audit_repo
            aid = audit_repo.create_reauth_audit(channel_id=1, status="started")
            assert aid == 10

    def test_complete_reauth_audit(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(AUDIT_MOD, conn):
            from shared.db.repositories import audit_repo
            ok = audit_repo.complete_reauth_audit(10, status="completed")
            assert ok is True

    def test_complete_reauth_audit_not_found(self):
        conn, _ = _make_conn(rowcount=0)
        with _patch_repo(AUDIT_MOD, conn):
            from shared.db.repositories import audit_repo
            ok = audit_repo.complete_reauth_audit(999, status="completed")
            assert ok is False

    def test_get_recent_reauth_audits(self):
        rows = [
            (1, 5, datetime.now(), None, "started", "manual",
             None, None, None, datetime.now()),
        ]
        conn, _ = _make_conn(fetchall=rows)
        with _patch_repo(AUDIT_MOD, conn):
            from shared.db.repositories import audit_repo
            result = audit_repo.get_recent_reauth_audits(channel_id=5)
            assert len(result) == 1
            assert result[0]["channel_id"] == 5
            assert result[0]["status"] == "started"


# ── Stats repo ────────────────────────────────────────────────────

STATS_MOD = "shared.db.repositories.stats_repo"


class TestStatsRepo:
    def test_record_stats(self):
        conn, _ = _make_conn(lastrowid=42)
        with _patch_repo(STATS_MOD, conn):
            from shared.db.repositories import stats_repo
            rid = stats_repo.record_stats(
                channel_id=1, platform_channel_id="UC123",
                subscribers=1000, views=50000, videos=100,
            )
            assert rid == 42

    def test_get_channel_stats_empty(self):
        conn, _ = _make_conn(fetchall=[])
        with _patch_repo(STATS_MOD, conn):
            from shared.db.repositories import stats_repo
            assert stats_repo.get_channel_stats(1) == []


# ── Credential repo extended ──────────────────────────────────────

CRED_MOD = "shared.db.repositories.credential_repo"


class TestCredentialRepoExtended:
    def test_add_credentials(self):
        conn, _ = _make_conn(lastrowid=7)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            cid = credential_repo.add_credentials(
                channel_id=1, login_email="test@test.com", login_password="pass",
            )
            assert cid == 7

    def test_upsert_credentials(self):
        conn, _ = _make_conn()
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            ok = credential_repo.upsert_credentials(
                channel_id=1, login_email="test@test.com", login_password="pass",
            )
            assert ok is True

    def test_mark_attempt_success(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            ok = credential_repo.mark_attempt(channel_id=1, success=True)
            assert ok is True

    def test_mark_attempt_failure(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            ok = credential_repo.mark_attempt(channel_id=1, success=False, error_message="timeout")
            assert ok is True

    def test_update_profile_path(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(CRED_MOD, conn):
            from shared.db.repositories import credential_repo
            ok = credential_repo.update_profile_path(1, "/home/user/.profile")
            assert ok is True


# ── Channel repo extended ─────────────────────────────────────────

CHAN_MOD = "shared.db.repositories.channel_repo"


class TestChannelRepoExtended:
    def test_channel_exists_by_name_true(self):
        conn, _ = _make_conn(fetchone=(1,))
        with _patch_repo(CHAN_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.channel_exists_by_name("TestChannel") is True

    def test_channel_exists_by_name_false(self):
        conn, _ = _make_conn(fetchone=None)
        with _patch_repo(CHAN_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.channel_exists_by_name("Nonexistent") is False

    def test_update_channel_tokens(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(CHAN_MOD, conn):
            from shared.db.repositories import channel_repo
            ok = channel_repo.update_channel_tokens(1, "new_access", "new_refresh")
            assert ok is True

    def test_delete_channel(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(CHAN_MOD, conn):
            from shared.db.repositories import channel_repo
            ok = channel_repo.delete_channel(1)
            assert ok is True

    def test_get_all_channels_empty(self):
        conn, _ = _make_conn(fetchall=[])
        with _patch_repo(CHAN_MOD, conn):
            from shared.db.repositories import channel_repo
            assert channel_repo.get_all_channels() == []


# ── Task repo extended ────────────────────────────────────────────

TASK_MOD = "shared.db.repositories.task_repo"


class TestTaskRepoExtended:
    def test_get_task_by_uuid_not_found(self):
        conn, _ = _make_conn(fetchone=None)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.get_task_by_uuid("nonexistent-uuid") is None

    def test_retry_task_success(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.retry_task(1) is True

    def test_retry_task_wrong_status(self):
        conn, _ = _make_conn(rowcount=0)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            assert task_repo.retry_task(1) is False

    def test_update_task_scheduled_at(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            ok = task_repo.update_task_scheduled_at(1, datetime.now())
            assert ok is True

    def test_update_task_upload_id(self):
        conn, _ = _make_conn(rowcount=1)
        with _patch_repo(TASK_MOD, conn):
            from shared.db.repositories import task_repo
            ok = task_repo.update_task_upload_id(1, "yt-upload-123")
            assert ok is True


# ── User repo extended ────────────────────────────────────────────

USER_MOD = "shared.db.repositories.user_repo"


class TestUserRepoExtended:
    def test_get_user_by_email_not_found(self):
        conn, _ = _make_conn(fetchone=None)
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            assert user_repo.get_user_by_email("nobody@test.com") is None

    def test_get_user_by_username(self):
        row = (1, "uuid", "testuser", "test@test.com", "hash", "Test",
               None, 10, "UTC", None, False, None, datetime.now(), datetime.now())
        conn, _ = _make_conn(fetchone=row)
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            user = user_repo.get_user_by_username("testuser")
            assert user is not None
            assert user["username"] == "testuser"

    def test_change_password(self):
        conn, _ = _make_conn()
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            user_repo.change_password(1, "new_hash")  # should not raise

    def test_set_totp_secret(self):
        conn, _ = _make_conn()
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            user_repo.set_totp_secret(1, "ABCDEF123456")  # should not raise

    def test_enable_totp(self):
        conn, _ = _make_conn()
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            user_repo.enable_totp(1, ["code1", "code2"])  # should not raise

    def test_disable_totp(self):
        conn, _ = _make_conn()
        with _patch_repo(USER_MOD, conn):
            from shared.db.repositories import user_repo
            user_repo.disable_totp(1)  # should not raise
