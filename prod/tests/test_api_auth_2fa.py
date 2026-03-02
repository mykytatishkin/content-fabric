"""Tests for 2FA endpoints — setup, verify, disable."""

from unittest.mock import patch, MagicMock
import pytest

from tests.conftest import TEST_USER


TOTP_USER = {**TEST_USER, "totp_enabled": True, "totp_secret": "JBSWY3DPEHPK3PXP"}
NO_TOTP_USER = {**TEST_USER, "totp_enabled": False, "totp_secret": None}


class TestSetup2FA:
    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=NO_TOTP_USER)
    @patch("shared.db.repositories.user_repo.set_totp_secret")
    def test_setup_success(self, mock_set, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        assert "backup_codes" in data
        assert len(data["backup_codes"]) == 8

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TOTP_USER)
    def test_setup_already_enabled(self, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/auth/2fa/setup", headers=auth_headers)
        assert resp.status_code == 409


class TestDisable2FA:
    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=NO_TOTP_USER)
    def test_disable_not_enabled(self, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/auth/2fa/disable", headers=auth_headers,
                               json={"password": "test"})
        assert resp.status_code == 400

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TOTP_USER)
    @patch("app.api.endpoints.auth.verify_password", return_value=False)
    def test_disable_wrong_password(self, mock_verify, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/auth/2fa/disable", headers=auth_headers,
                               json={"password": "wrong"})
        assert resp.status_code == 401

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TOTP_USER)
    @patch("app.api.endpoints.auth.verify_password", return_value=True)
    @patch("shared.db.repositories.user_repo.disable_totp")
    def test_disable_success(self, mock_disable, mock_verify, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/auth/2fa/disable", headers=auth_headers,
                               json={"password": "correct"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestVerify2FA:
    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=NO_TOTP_USER)
    def test_verify_no_secret(self, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/auth/2fa/verify", headers=auth_headers,
                               json={"code": "123456"})
        assert resp.status_code == 400

    @patch("shared.db.repositories.user_repo.get_user_by_id", return_value=TOTP_USER)
    def test_verify_already_enabled(self, mock_user, app_client, auth_headers):
        resp = app_client.post("/api/v1/auth/2fa/verify", headers=auth_headers,
                               json={"code": "123456"})
        assert resp.status_code == 409
