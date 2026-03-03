"""Tests for templates API endpoints."""

from unittest.mock import patch, MagicMock
import pytest

from tests.conftest import TEST_USER


class TestCreateTemplate:
    def test_requires_auth(self, app_client):
        resp = app_client.post("/api/v1/templates/", json={"name": "T1"})
        assert resp.status_code == 401

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch("shared.db.repositories.template_repo.create_template", return_value=1)
    @patch("shared.db.repositories.template_repo.add_slot")
    @patch("shared.db.repositories.template_repo.get_template", return_value={
        "id": 1, "project_id": 1, "name": "Weekly", "description": "Weekly schedule",
        "timezone": "UTC", "is_active": True, "created_at": "2026-01-01", "created_by": 1,
    })
    @patch("shared.db.repositories.template_repo.get_slots", return_value=[])
    def test_create_success(self, mock_slots, mock_get, mock_add, mock_create, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/templates/", headers=auth_headers, json={
            "name": "Weekly",
            "description": "Weekly schedule",
            "timezone": "UTC",
            "slots": [],
        })
        assert resp.status_code == 201


class TestListTemplates:
    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch("shared.db.repositories.template_repo.list_templates", return_value=[])
    def test_empty(self, mock_list, mock_user, app_client, auth_headers):
        resp = app_client.get("/api/v1/templates/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0


class TestDeleteTemplate:
    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch("shared.db.repositories.template_repo.get_template", return_value=None)
    def test_not_found(self, mock_get, mock_user, app_client, auth_headers):
        resp = app_client.delete("/api/v1/templates/999", headers=auth_headers)
        assert resp.status_code == 404

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch("shared.db.repositories.template_repo.delete_template", return_value=True)
    @patch("shared.db.repositories.template_repo.get_template", return_value={
        "id": 1, "name": "T", "created_by": 1,
    })
    def test_success(self, mock_get, mock_delete, mock_user, app_client, auth_headers):
        resp = app_client.delete("/api/v1/templates/1", headers=auth_headers)
        assert resp.status_code == 204
