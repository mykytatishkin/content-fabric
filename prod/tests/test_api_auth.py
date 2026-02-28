"""Tests for auth API endpoints."""

from datetime import datetime
from unittest.mock import patch

import pytest

from tests.conftest import TEST_USER


class TestLogin:
    def test_no_user(self, app_client):
        with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=None):
            resp = app_client.post("/api/v1/auth/login", json={"email": "x@x.com", "password": "pass"})
        assert resp.status_code == 401

    def test_wrong_password(self, app_client):
        with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=TEST_USER), \
             patch("app.api.endpoints.auth.verify_password", return_value=False):
            resp = app_client.post("/api/v1/auth/login", json={"email": "x@x.com", "password": "wrong"})
        assert resp.status_code == 401

    def test_success(self, app_client):
        with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=TEST_USER), \
             patch("app.api.endpoints.auth.verify_password", return_value=True), \
             patch("shared.db.repositories.user_repo.update_last_login"), \
             patch("app.core.audit.log"):
            resp = app_client.post("/api/v1/auth/login", json={"email": "x@x.com", "password": "pass"})
        assert resp.status_code == 200
        assert resp.json()["access_token"] != ""

    def test_2fa_required(self, app_client):
        user_2fa = {**TEST_USER, "totp_enabled": True, "totp_secret": "SECRET"}
        with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=user_2fa), \
             patch("app.api.endpoints.auth.verify_password", return_value=True):
            resp = app_client.post("/api/v1/auth/login", json={"email": "x@x.com", "password": "pass"})
        assert resp.status_code == 200
        assert resp.json()["requires_2fa"] is True
        assert resp.json()["access_token"] == ""


class TestRegister:
    def test_email_taken(self, app_client):
        with patch("shared.db.repositories.user_repo.get_user_by_email", return_value={"id": 1}):
            resp = app_client.post("/api/v1/auth/register", json={
                "username": "new", "email": "taken@x.com", "password": "pass",
            })
        assert resp.status_code == 409

    def test_username_taken(self, app_client):
        with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=None), \
             patch("shared.db.repositories.user_repo.get_user_by_username", return_value={"id": 1}):
            resp = app_client.post("/api/v1/auth/register", json={
                "username": "taken", "email": "new@x.com", "password": "pass",
            })
        assert resp.status_code == 409

    def test_success(self, app_client):
        with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=None), \
             patch("shared.db.repositories.user_repo.get_user_by_username", return_value=None), \
             patch("shared.db.repositories.user_repo.create_user", return_value=42), \
             patch("app.api.endpoints.auth.hash_password", return_value="hashed"), \
             patch("app.core.audit.log"):
            resp = app_client.post("/api/v1/auth/register", json={
                "username": "newuser", "email": "new@x.com", "password": "pass",
            })
        assert resp.status_code == 201
        assert "access_token" in resp.json()


class TestMe:
    def test_unauthenticated(self, app_client):
        resp = app_client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    def test_authenticated(self, app_client, auth_headers):
        with patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TEST_USER):
            resp = app_client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"
