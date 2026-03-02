"""Tests for app.core.auth — centralized auth helpers."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from tests.conftest import TEST_USER, ADMIN_USER


class TestIsAdmin:
    def test_admin_user(self):
        from app.core.auth import is_admin
        assert is_admin(ADMIN_USER) is True

    def test_regular_user(self):
        from app.core.auth import is_admin
        assert is_admin(TEST_USER) is False

    def test_inactive_user(self):
        from app.core.auth import is_admin
        assert is_admin({**TEST_USER, "status": 0}) is False

    def test_missing_status(self):
        from app.core.auth import is_admin
        assert is_admin({}) is False


class TestUserFromToken:
    @patch("app.core.auth.decode_access_token")
    @patch("shared.db.repositories.user_repo.get_user_by_id")
    def test_valid_token(self, mock_get_user, mock_decode):
        from app.core.auth import user_from_token
        mock_decode.return_value = {"sub": 1}
        mock_get_user.return_value = TEST_USER
        result = user_from_token("valid-token")
        assert result == TEST_USER
        mock_get_user.assert_called_once_with(1)

    @patch("app.core.auth.decode_access_token")
    def test_invalid_token(self, mock_decode):
        from app.core.auth import user_from_token
        mock_decode.return_value = None
        assert user_from_token("bad-token") is None

    @patch("app.core.auth.decode_access_token")
    def test_no_sub_claim(self, mock_decode):
        from app.core.auth import user_from_token
        mock_decode.return_value = {"exp": 123}
        assert user_from_token("no-sub") is None

    @patch("app.core.auth.decode_access_token")
    @patch("shared.db.repositories.user_repo.get_user_by_id")
    def test_user_not_found(self, mock_get_user, mock_decode):
        from app.core.auth import user_from_token
        mock_decode.return_value = {"sub": 999}
        mock_get_user.return_value = None
        assert user_from_token("orphan-token") is None


class TestUserFromCookie:
    @patch("app.core.auth.user_from_token")
    def test_no_cookie(self, mock_from_token):
        from app.core.auth import user_from_cookie
        request = MagicMock()
        request.cookies.get.return_value = None
        assert user_from_cookie(request) is None
        mock_from_token.assert_not_called()

    @patch("app.core.auth.user_from_token")
    def test_valid_cookie(self, mock_from_token):
        from app.core.auth import user_from_cookie
        request = MagicMock()
        request.cookies.get.return_value = "valid-jwt"
        mock_from_token.return_value = TEST_USER
        result = user_from_cookie(request)
        assert result == TEST_USER
        mock_from_token.assert_called_once_with("valid-jwt")


class TestRequireUser:
    @patch("app.core.auth.user_from_cookie")
    def test_authenticated(self, mock_cookie):
        from app.core.auth import require_user
        mock_cookie.return_value = TEST_USER
        request = MagicMock()
        user, redirect = require_user(request)
        assert user == TEST_USER
        assert redirect is None

    @patch("app.core.auth.user_from_cookie")
    def test_not_authenticated(self, mock_cookie):
        from app.core.auth import require_user
        mock_cookie.return_value = None
        request = MagicMock()
        user, redirect = require_user(request)
        assert user is None
        assert redirect is not None
        assert redirect.status_code == 302


class TestRequireAdmin:
    @patch("app.core.auth.user_from_cookie")
    def test_admin_passes(self, mock_cookie):
        from app.core.auth import require_admin
        mock_cookie.return_value = ADMIN_USER
        request = MagicMock()
        user, redirect = require_admin(request)
        assert user == ADMIN_USER
        assert redirect is None

    @patch("app.core.auth.user_from_cookie")
    def test_regular_user_redirected(self, mock_cookie):
        from app.core.auth import require_admin
        mock_cookie.return_value = TEST_USER
        request = MagicMock()
        user, redirect = require_admin(request)
        assert redirect is not None
        assert redirect.status_code == 302

    @patch("app.core.auth.user_from_cookie")
    def test_no_user_redirected(self, mock_cookie):
        from app.core.auth import require_admin
        mock_cookie.return_value = None
        request = MagicMock()
        user, redirect = require_admin(request)
        assert redirect is not None


class TestRequireAdminApi:
    def test_admin_passes(self):
        from app.core.auth import require_admin_api
        result = require_admin_api(ADMIN_USER)
        assert result == ADMIN_USER

    def test_non_admin_raises_403(self):
        from app.core.auth import require_admin_api
        with pytest.raises(HTTPException) as exc_info:
            require_admin_api(TEST_USER)
        assert exc_info.value.status_code == 403


class TestScopedUserId:
    def test_admin_returns_none(self):
        from app.core.auth import scoped_user_id
        assert scoped_user_id(ADMIN_USER) is None

    def test_regular_user_returns_id(self):
        from app.core.auth import scoped_user_id
        assert scoped_user_id(TEST_USER) == 1


class TestScopedWhere:
    def test_admin_returns_1_eq_1(self):
        from app.core.auth import scoped_where
        clause, params = scoped_where(ADMIN_USER)
        assert clause == "1=1"
        assert params == {}

    def test_regular_user_returns_filter(self):
        from app.core.auth import scoped_where
        clause, params = scoped_where(TEST_USER)
        assert "created_by = :user_id" in clause
        assert params["user_id"] == 1

    def test_with_table_alias(self):
        from app.core.auth import scoped_where
        clause, params = scoped_where(TEST_USER, "t")
        assert "t.created_by = :user_id" in clause


class TestCheckOwner:
    def test_admin_always_passes(self):
        from app.core.auth import check_owner
        resource = {"created_by": 999}
        assert check_owner(resource, ADMIN_USER) is True

    def test_owner_passes(self):
        from app.core.auth import check_owner
        resource = {"created_by": 1}
        assert check_owner(resource, TEST_USER) is True

    def test_non_owner_fails(self):
        from app.core.auth import check_owner
        resource = {"created_by": 999}
        assert check_owner(resource, TEST_USER) is False

    def test_custom_owner_field(self):
        from app.core.auth import check_owner
        resource = {"user_id": 1}
        assert check_owner(resource, TEST_USER, owner_field="user_id") is True


class TestCheckOwnerOr404:
    def test_owner_passes(self):
        from app.core.auth import check_owner_or_404
        resource = {"created_by": 1}
        check_owner_or_404(resource, TEST_USER)  # should not raise

    def test_non_owner_raises_404(self):
        from app.core.auth import check_owner_or_404
        resource = {"created_by": 999}
        with pytest.raises(HTTPException) as exc_info:
            check_owner_or_404(resource, TEST_USER)
        assert exc_info.value.status_code == 404

    def test_admin_never_raises(self):
        from app.core.auth import check_owner_or_404
        resource = {"created_by": 999}
        check_owner_or_404(resource, ADMIN_USER)  # should not raise
