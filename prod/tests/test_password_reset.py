"""Tests for password reset flow.

Mirrors Yii's frontend SiteController::actionRequestPasswordReset / actionResetPassword
and the PasswordResetRequestForm + ResetPasswordForm models.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from tests.conftest import TEST_USER

ACTIVE_USER = {**TEST_USER, "status": 10}  # UserStatus.ACTIVE
INACTIVE_USER = {**TEST_USER, "status": 0}  # UserStatus.INACTIVE


# ── /api/v1/auth/forgot-password ──────────────────────────────────────


def test_forgot_password_existing_user_sends_email(app_client):
    with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=ACTIVE_USER), \
         patch("shared.db.repositories.user_repo.set_password_reset_token", return_value=True) as set_tok, \
         patch("app.api.endpoints.auth.email_sender.send_password_reset_email", return_value=True) as sender, \
         patch("app.core.audit.log"):
        resp = app_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": ACTIVE_USER["email"]},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "email has been sent" in body["message"].lower()
    assert set_tok.called
    assert sender.called
    # Token written must be the same one used in the URL.
    written_token = set_tok.call_args.args[1]
    sent_url = sender.call_args.kwargs["reset_url"]
    assert written_token in sent_url


def test_forgot_password_unknown_email_returns_ok_no_email(app_client):
    """Don't leak which addresses are registered — same response either way."""
    with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=None), \
         patch("app.api.endpoints.auth.email_sender.send_password_reset_email") as sender, \
         patch("shared.db.repositories.user_repo.set_password_reset_token") as set_tok:
        resp = app_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    sender.assert_not_called()
    set_tok.assert_not_called()


def test_forgot_password_inactive_user_no_email(app_client):
    with patch("shared.db.repositories.user_repo.get_user_by_email", return_value=INACTIVE_USER), \
         patch("app.api.endpoints.auth.email_sender.send_password_reset_email") as sender, \
         patch("shared.db.repositories.user_repo.set_password_reset_token") as set_tok:
        resp = app_client.post(
            "/api/v1/auth/forgot-password",
            json={"email": INACTIVE_USER["email"]},
        )
    assert resp.status_code == 200
    sender.assert_not_called()
    set_tok.assert_not_called()


# ── /api/v1/auth/reset-password ───────────────────────────────────────


def _fresh_token() -> str:
    """A well-formed reset token issued just now."""
    from app.core.tokens import make_reset_token
    return make_reset_token()


def _expired_token() -> str:
    """A reset token whose embedded ts is older than 1 hour."""
    import secrets
    return f"{secrets.token_hex(32)}_{int(time.time()) - 7200}"


def test_reset_password_valid_token(app_client):
    token = _fresh_token()
    with patch("shared.db.repositories.user_repo.get_user_by_reset_token", return_value=ACTIVE_USER), \
         patch("shared.db.repositories.user_repo.change_password") as change_pw, \
         patch("shared.db.repositories.user_repo.set_password_reset_token", return_value=True) as set_tok, \
         patch("app.api.endpoints.auth.hash_password", return_value="bcrypt-hashed-new"), \
         patch("app.core.audit.log"):
        resp = app_client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BrandNewSecret123"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    change_pw.assert_called_once_with(ACTIVE_USER["id"], "bcrypt-hashed-new")
    # Token MUST be cleared after use (single-use).
    set_tok.assert_called_with(ACTIVE_USER["id"], None)


def test_reset_password_expired_token(app_client):
    token = _expired_token()
    with patch("shared.db.repositories.user_repo.get_user_by_reset_token") as lookup, \
         patch("shared.db.repositories.user_repo.change_password") as change_pw:
        resp = app_client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BrandNewSecret123"},
        )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()
    lookup.assert_not_called()
    change_pw.assert_not_called()


def test_reset_password_malformed_token(app_client):
    """Token without `_<ts>` suffix is rejected up-front."""
    with patch("shared.db.repositories.user_repo.get_user_by_reset_token") as lookup:
        resp = app_client.post(
            "/api/v1/auth/reset-password",
            json={"token": "deadbeef-not-a-real-token", "password": "BrandNewSecret123"},
        )
    assert resp.status_code == 400
    lookup.assert_not_called()


def test_reset_password_unknown_token_in_db(app_client):
    """Well-formed, unexpired token but no user has it."""
    token = _fresh_token()
    with patch("shared.db.repositories.user_repo.get_user_by_reset_token", return_value=None), \
         patch("shared.db.repositories.user_repo.change_password") as change_pw:
        resp = app_client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BrandNewSecret123"},
        )
    assert resp.status_code == 400
    change_pw.assert_not_called()


def test_reset_password_reused_token_fails(app_client):
    """First use clears the token; the second lookup returns None ⇒ 400."""
    token = _fresh_token()

    # Simulate the DB by tracking whether the token has been "consumed".
    state = {"consumed": False}

    def _lookup(t):
        if state["consumed"]:
            return None
        return ACTIVE_USER

    def _set_token(uid, tok):
        if tok is None:
            state["consumed"] = True
        return True

    with patch("shared.db.repositories.user_repo.get_user_by_reset_token", side_effect=_lookup), \
         patch("shared.db.repositories.user_repo.change_password"), \
         patch("shared.db.repositories.user_repo.set_password_reset_token", side_effect=_set_token), \
         patch("app.api.endpoints.auth.hash_password", return_value="hashed"), \
         patch("app.core.audit.log"):
        r1 = app_client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BrandNewSecret123"},
        )
        r2 = app_client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "AnotherSecret456"},
        )
    assert r1.status_code == 200
    assert r2.status_code == 400


def test_reset_password_short_password_rejected_by_schema(app_client):
    token = _fresh_token()
    resp = app_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "short"},
    )
    assert resp.status_code == 422  # pydantic min_length=8


def test_forgot_then_reset_clears_token(app_client):
    """End-to-end: forgot writes a token, reset clears it."""
    user = dict(ACTIVE_USER)
    written = {}

    def _set_tok(uid, tok):
        written["uid"] = uid
        written["token"] = tok
        return True

    def _by_email(email):
        return user if email == user["email"] else None

    with patch("shared.db.repositories.user_repo.get_user_by_email", side_effect=_by_email), \
         patch("shared.db.repositories.user_repo.set_password_reset_token", side_effect=_set_tok), \
         patch("app.api.endpoints.auth.email_sender.send_password_reset_email", return_value=True), \
         patch("app.core.audit.log"):
        r1 = app_client.post(
            "/api/v1/auth/forgot-password", json={"email": user["email"]},
        )
        assert r1.status_code == 200
        token = written["token"]
        assert token and "_" in token

    # Now consume that exact token via reset-password.
    with patch("shared.db.repositories.user_repo.get_user_by_reset_token", return_value=user), \
         patch("shared.db.repositories.user_repo.change_password"), \
         patch("shared.db.repositories.user_repo.set_password_reset_token", side_effect=_set_tok), \
         patch("app.api.endpoints.auth.hash_password", return_value="hashed"), \
         patch("app.core.audit.log"):
        r2 = app_client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BrandNewSecret123"},
        )
    assert r2.status_code == 200
    # Last call to set_password_reset_token must have set token=None.
    assert written["token"] is None


def test_token_helpers_roundtrip():
    from app.core.tokens import (
        PASSWORD_RESET_TTL_SEC,
        is_token_ts_expired,
        make_reset_token,
        parse_token_ts,
    )
    token = make_reset_token()
    ts = parse_token_ts(token)
    assert ts is not None
    assert abs(ts - int(time.time())) < 5
    assert not is_token_ts_expired(token, PASSWORD_RESET_TTL_SEC)
    assert is_token_ts_expired(token, ttl_sec=0)
    assert is_token_ts_expired("garbage-no-underscore", PASSWORD_RESET_TTL_SEC)
    assert parse_token_ts("garbage-no-underscore") is None


def test_reset_password_portal_page_invalid_token_redirects(app_client):
    """GET /app/reset-password/<bad-token> redirects to /app/login."""
    resp = app_client.get(
        "/app/reset-password/totally-bogus", follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    assert "/app/login" in resp.headers.get("location", "")
