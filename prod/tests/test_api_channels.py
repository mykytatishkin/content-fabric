"""Tests for channels API endpoints."""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from tests.conftest import TEST_USER, ADMIN_USER

# Patch targets: functions are imported into the endpoint module namespace
_EP = "app.api.endpoints.channels"


class TestListChannels:
    def test_requires_auth(self, app_client):
        resp = app_client.get("/api/v1/channels/")
        assert resp.status_code == 401

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch(f"{_EP}.list_channels", return_value=[])
    def test_empty_list(self, mock_list, mock_user, app_client, auth_headers):
        resp = app_client.get("/api/v1/channels/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch(f"{_EP}.list_channels", return_value=[
        {"id": 1, "name": "TestChannel", "platform_channel_id": "UC123",
         "console_id": 1, "enabled": True, "project_id": None, "created_by": 1,
         "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
    ])
    def test_list_with_items(self, mock_list, mock_user, app_client, auth_headers):
        resp = app_client.get("/api/v1/channels/", headers=auth_headers)
        assert resp.status_code == 200
        channels = resp.json()
        assert len(channels) == 1
        assert channels[0]["name"] == "TestChannel"


class TestGetChannel:
    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch(f"{_EP}.get_channel_by_id", return_value=None)
    def test_not_found(self, mock_get, mock_user, app_client, auth_headers):
        resp = app_client.get("/api/v1/channels/999", headers=auth_headers)
        assert resp.status_code == 404

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch(f"{_EP}.get_channel_by_id", return_value={
        "id": 1, "name": "MyChannel", "platform_channel_id": "UC123",
        "console_id": 1, "enabled": True, "project_id": None, "created_by": 1,
        "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
    })
    def test_found(self, mock_get, mock_user, app_client, auth_headers):
        resp = app_client.get("/api/v1/channels/1", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "MyChannel"


class TestGetConsoles:
    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER)
    @patch(f"{_EP}.list_oauth_credentials", return_value=[
        {"id": 1, "name": "Console1", "description": "test", "enabled": True},
    ])
    def test_list_consoles(self, mock_list, mock_user, app_client, auth_headers):
        resp = app_client.get("/api/v1/channels/google-consoles", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Console1"
