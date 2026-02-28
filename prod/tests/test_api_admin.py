"""Tests for admin API endpoints."""

from unittest.mock import patch

import pytest

from tests.conftest import TEST_USER, ADMIN_USER


class TestAdminDashboard:
    def test_non_admin_rejected(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER):
            resp = app_client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 403

    def test_admin_allowed(self, app_client, admin_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=ADMIN_USER):
            resp = app_client.get("/api/v1/admin/dashboard", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "channels" in data
        assert "tasks" in data


class TestAdminUsers:
    def test_list_users(self, app_client, admin_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=ADMIN_USER):
            resp = app_client.get("/api/v1/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        assert "users" in resp.json()


class TestAdminQueue:
    def test_queue_status(self, app_client, admin_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=ADMIN_USER):
            resp = app_client.get("/api/v1/admin/queue", headers=admin_headers)
        assert resp.status_code == 200


class TestAdminCredentials:
    def test_list_masked(self, app_client, admin_headers):
        creds = [{"login_email": "a@b.com", "login_password": "secret", "proxy_password": "pp"}]
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=ADMIN_USER), \
             patch("shared.db.repositories.credential_repo.list_credentials", return_value=creds):
            resp = app_client.get("/api/v1/admin/credentials", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["credentials"][0]["login_password"] == "***"
        assert resp.json()["credentials"][0]["proxy_password"] == "***"

    def test_set_totp(self, app_client, admin_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=ADMIN_USER), \
             patch("shared.db.repositories.credential_repo.get_credentials", return_value={"id": 1}), \
             patch("shared.db.repositories.credential_repo.update_totp_secret", return_value=True):
            resp = app_client.post("/api/v1/admin/credentials/10/totp",
                                   params={"totp_secret": "SECRET"}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_set_totp_no_creds(self, app_client, admin_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=ADMIN_USER), \
             patch("shared.db.repositories.credential_repo.get_credentials", return_value=None):
            resp = app_client.post("/api/v1/admin/credentials/999/totp",
                                   params={"totp_secret": "X"}, headers=admin_headers)
        assert resp.status_code == 404
