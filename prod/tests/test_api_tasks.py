"""Tests for task API endpoints."""

from datetime import datetime
from unittest.mock import patch

import pytest

from tests.conftest import TEST_USER


def _task(task_id=1, status=0):
    return {
        "id": task_id, "channel_id": 10, "media_type": "video",
        "status": status, "created_at": datetime(2026, 1, 1),
        "source_file_path": "/tmp/v.mp4", "thumbnail_path": None,
        "title": "Test Video", "description": None, "keywords": None,
        "post_comment": None, "legacy_add_info": None,
        "scheduled_at": datetime(2026, 3, 1), "completed_at": None,
        "upload_id": None, "error_message": None, "retry_count": 0,
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
             patch("shared.db.repositories.task_repo.create_task", return_value=1), \
             patch("shared.db.repositories.task_repo.get_task", return_value=_task()), \
             patch("app.core.audit.log"):
            resp = app_client.post("/api/v1/tasks/", json={
                "channel_id": 10, "source_file_path": "/tmp/v.mp4",
                "title": "Test Video", "scheduled_at": "2026-03-01T12:00:00",
            }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == "Test Video"

    def test_creation_failure(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.create_task", return_value=None):
            resp = app_client.post("/api/v1/tasks/", json={
                "channel_id": 10, "source_file_path": "/v.mp4",
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
             patch("shared.db.repositories.task_repo.get_all_tasks", return_value=[]):
            resp = app_client.get("/api/v1/tasks/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_with_items(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER), \
             patch("shared.db.repositories.task_repo.get_all_tasks", return_value=[_task(i) for i in range(3)]):
            resp = app_client.get("/api/v1/tasks/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 3
