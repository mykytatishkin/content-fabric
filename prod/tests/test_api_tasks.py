"""Tests for task API endpoints."""

from datetime import datetime
from unittest.mock import patch

import pytest

from tests.conftest import TEST_USER


_MOCK_CHANNEL = {"id": 10, "name": "TestCh", "created_by": 1}


def _task(task_id=1, status=0):
    return {
        "id": task_id, "channel_id": 10, "media_type": "video",
        "status": status, "created_at": datetime(2026, 1, 1),
        "source_file_path": "uploads/v.mp4", "thumbnail_path": None,
        "title": "Test Video", "description": None, "keywords": None,
        "post_comment": None, "legacy_add_info": None,
        "scheduled_at": datetime(2026, 3, 1), "completed_at": None,
        "upload_id": None, "error_message": None, "retry_count": 0,
        "created_by": TEST_USER["id"],
    }


class TestCreateTask:
    def test_unauthenticated(self, app_client):
        resp = app_client.post("/api/v1/tasks/", json={
            "channel_id": 1, "source_file_path": "/v.mp4",
            "title": "X", "scheduled_at": "2026-03-01T12:00:00",
        })
        assert resp.status_code in (401, 403)

    def test_success(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.channel_repo.get_channel_by_id", return_value=_MOCK_CHANNEL), \
             patch("shared.db.repositories.task_repo.create_task", return_value=1), \
             patch("shared.db.repositories.task_repo.get_task", return_value=_task()), \
             patch("app.core.audit.log"):
            resp = app_client.post("/api/v1/tasks/", json={
                "channel_id": 10, "source_file_path": "uploads/v.mp4",
                "title": "Test Video", "scheduled_at": "2026-03-01T12:00:00",
            }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == "Test Video"

    def test_creation_failure(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.channel_repo.get_channel_by_id", return_value=_MOCK_CHANNEL), \
             patch("shared.db.repositories.task_repo.create_task", return_value=None):
            resp = app_client.post("/api/v1/tasks/", json={
                "channel_id": 10, "source_file_path": "uploads/v.mp4",
                "title": "T", "scheduled_at": "2026-03-01T12:00:00",
            }, headers=auth_headers)
        assert resp.status_code == 500


class TestGetTask:
    def test_not_found(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_task", return_value=None):
            resp = app_client.get("/api/v1/tasks/999", headers=auth_headers)
        assert resp.status_code == 404

    def test_found(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_task", return_value=_task()):
            resp = app_client.get("/api/v1/tasks/1", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == 1


class TestCancelTask:
    def test_cancel_pending(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_task", side_effect=[_task(status=0), _task(status=4)]), \
             patch("shared.db.repositories.task_repo.cancel_task", return_value=True), \
             patch("app.core.audit.log"):
            resp = app_client.post("/api/v1/tasks/1/cancel", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == 4

    def test_cancel_completed_fails(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_task", return_value=_task(status=1)):
            resp = app_client.post("/api/v1/tasks/1/cancel", headers=auth_headers)
        assert resp.status_code == 409


class TestListTasks:
    def test_empty(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_all_tasks", return_value=[]), \
             patch("shared.db.repositories.task_repo.count_tasks", return_value=0):
            resp = app_client.get("/api/v1/tasks/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_with_items(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_all_tasks", return_value=[_task(i) for i in range(3)]), \
             patch("shared.db.repositories.task_repo.count_tasks", return_value=3):
            resp = app_client.get("/api/v1/tasks/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    def test_total_reflects_global_count_not_page_size(self, app_client, auth_headers):
        """Regression: total must come from count_tasks(), not len(items)."""
        page = [_task(i) for i in range(50)]  # one page of 50
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_all_tasks", return_value=page), \
             patch("shared.db.repositories.task_repo.count_tasks", return_value=8908):
            resp = app_client.get("/api/v1/tasks/?limit=50", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 50
        assert body["total"] == 8908  # global count, NOT len(items)


class TestTaskProgress:
    """Default progress values derived from terminal task status when Redis has
    no live progress entry. The endpoint reads `_get_progress_from_redis` and
    falls back to defaults when that returns empty dict — so we mock both."""

    def test_progress_completed_defaults_to_100(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_task", return_value=_task(status=1)), \
             patch("app.api.endpoints.tasks._get_progress_from_redis", return_value={}):
            resp = app_client.get("/api/v1/tasks/1/progress", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["progress_pct"] == 100
        assert body["stage"] == "completed"
        assert body["status"] == 1

    def test_progress_failed(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_task", return_value=_task(status=2)), \
             patch("app.api.endpoints.tasks._get_progress_from_redis", return_value={}):
            resp = app_client.get("/api/v1/tasks/1/progress", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["stage"] == "failed"

    def test_progress_pending(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_task", return_value=_task(status=0)), \
             patch("app.api.endpoints.tasks._get_progress_from_redis", return_value={}):
            resp = app_client.get("/api/v1/tasks/1/progress", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["stage"] == "pending"


class TestCalendarAliases:
    """Regression tests for /var/log/cff-api.log 2026-05-09 20:03:27 —
    smoketest hits /api/v1/tasks/calendar with ``start_date``/``end_date``
    instead of ``from``/``to``, getting 5x 422.  Both alias forms should
    work."""

    def test_from_to(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_all_tasks", return_value=[]):
            resp = app_client.get(
                "/api/v1/tasks/calendar?from=2026-05-01&to=2026-05-31",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_start_date_end_date(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_all_tasks", return_value=[]):
            resp = app_client.get(
                "/api/v1/tasks/calendar?start_date=2026-05-01&end_date=2026-05-31",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_missing_range_400(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER):
            resp = app_client.get("/api/v1/tasks/calendar", headers=auth_headers)
        # Should be 400 (helpful) rather than 422 (cryptic).
        assert resp.status_code == 400
