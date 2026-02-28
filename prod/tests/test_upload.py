"""Tests for shared.youtube.upload — upload orchestration logic."""

from unittest.mock import MagicMock, patch
from contextlib import contextmanager

from shared.youtube.upload import _is_token_error, _fail, _set_progress


class TestTokenErrorDetection:
    def test_invalid_grant(self):
        assert _is_token_error("invalid_grant") is True

    def test_token_expired(self):
        assert _is_token_error("Token has been expired or revoked") is True

    def test_token_expired_lowercase(self):
        assert _is_token_error("token expired") is True

    def test_case_insensitive(self):
        assert _is_token_error("INVALID_GRANT error occurred") is True

    def test_non_token_error(self):
        assert _is_token_error("Network timeout") is False

    def test_empty_string(self):
        assert _is_token_error("") is False

    def test_quota_error(self):
        assert _is_token_error("quotaExceeded") is False


class TestSetProgress:
    def test_redis_failure_ignored(self):
        """_set_progress silently catches all exceptions."""
        with patch("shared.queue.config.get_redis", side_effect=Exception("no redis")):
            _set_progress(1, "test", 0)  # should not raise


class TestFail:
    def test_sends_generic_notification(self):
        with patch("shared.db.repositories.task_repo.mark_task_failed"), \
             patch("shared.notifications.telegram.send") as mock_tg:
            _fail(1, "some error")
        mock_tg.assert_called_once()
        assert "task 1 failed" in mock_tg.call_args[0][0].lower()

    def test_token_error_sends_reauth_notification(self):
        channel = {"name": "TestCh"}
        with patch("shared.db.repositories.task_repo.mark_task_failed"), \
             patch("shared.db.repositories.channel_repo.get_channel_by_id", return_value=channel), \
             patch("shared.notifications.telegram.send") as mock_tg:
            _fail(1, "invalid_grant", channel_id=10)
        msg = mock_tg.call_args[0][0]
        assert "TestCh" in msg
        assert "Re-authorization" in msg
