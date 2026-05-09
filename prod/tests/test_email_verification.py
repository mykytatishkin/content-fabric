"""Tests for email-verification flow (Yii parity gap G5).

Mirrors:
  - .legacy/yii/yii/frontend/controllers/SiteController.php:223-258
      (actionVerifyEmail + actionResendVerificationEmail)
  - .legacy/yii/yii/frontend/models/VerifyEmailForm.php
  - .legacy/yii/yii/frontend/models/ResendVerificationEmailForm.php
  - .legacy/yii/yii/common/models/User.php:193-204
      (generateEmailVerificationToken)
"""

from __future__ import annotations

import secrets
import time
from unittest.mock import patch

from tests.conftest import TEST_USER

ACTIVE_USER = {**TEST_USER, "status": 10}    # UserStatus.ACTIVE
INACTIVE_USER = {**TEST_USER, "status": 9}   # UserStatus.INACTIVE


def _fresh_token() -> str:
    """A well-formed verification token issued just now."""
    from app.core.tokens import make_verification_token
    return make_verification_token()


def _expired_token() -> str:
    """A verification token whose embedded ts is older than 24 hours."""
    return f"{secrets.token_hex(32)}_{int(time.time()) - 86400 - 3600}"


# ── /api/v1/auth/verify-email/{token}  (GET, Yii path-style) ─────────


def test_verify_email_valid_token_flips_status_to_active(app_client):
    """GET with a valid token for an INACTIVE user → atomic mark_email_verified."""
    token = _fresh_token()
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
        return_value=INACTIVE_USER,
    ), patch(
        "shared.db.repositories.user_repo.mark_email_verified", return_value=True,
    ) as marker, patch("app.core.audit.log"):
        resp = app_client.get(f"/api/v1/auth/verify-email/{token}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    marker.assert_called_once_with(INACTIVE_USER["id"])


def test_verify_email_invalid_token_returns_400(app_client):
    """Well-formed but unknown token (no DB row) → 400."""
    token = _fresh_token()
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
        return_value=None,
    ), patch(
        "shared.db.repositories.user_repo.mark_email_verified",
    ) as marker:
        resp = app_client.get(f"/api/v1/auth/verify-email/{token}")
    assert resp.status_code == 400
    marker.assert_not_called()


def test_verify_email_expired_token_returns_400(app_client):
    """Token older than 24h is rejected up-front, before DB lookup."""
    token = _expired_token()
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
    ) as lookup, patch(
        "shared.db.repositories.user_repo.mark_email_verified",
    ) as marker:
        resp = app_client.get(f"/api/v1/auth/verify-email/{token}")
    assert resp.status_code == 400
    lookup.assert_not_called()
    marker.assert_not_called()


def test_verify_email_already_active_user_rejected(app_client):
    """Idempotent reject: only INACTIVE users may consume the token."""
    token = _fresh_token()
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
        return_value=ACTIVE_USER,
    ), patch(
        "shared.db.repositories.user_repo.mark_email_verified",
    ) as marker:
        resp = app_client.get(f"/api/v1/auth/verify-email/{token}")
    assert resp.status_code == 400
    marker.assert_not_called()


def test_verify_email_malformed_token_returns_400(app_client):
    """Token without `_<ts>` suffix is rejected up-front (no DB hit)."""
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
    ) as lookup:
        resp = app_client.get("/api/v1/auth/verify-email/totally-bogus")
    assert resp.status_code == 400
    lookup.assert_not_called()


def test_verify_email_post_body_form_also_works(app_client):
    """Legacy POST {token} body form still works alongside GET path style."""
    token = _fresh_token()
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
        return_value=INACTIVE_USER,
    ), patch(
        "shared.db.repositories.user_repo.mark_email_verified", return_value=True,
    ), patch("app.core.audit.log"):
        resp = app_client.post(
            "/api/v1/auth/verify-email", json={"token": token},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ── /api/v1/auth/resend-verification ─────────────────────────────────


def test_resend_verification_inactive_user_sends_email(app_client):
    with patch(
        "shared.db.repositories.user_repo.get_user_by_email",
        return_value=INACTIVE_USER,
    ), patch(
        "shared.db.repositories.user_repo.set_verification_token", return_value=True,
    ) as set_tok, patch(
        "app.api.endpoints.auth.email_sender.send_verification_email",
        return_value=True,
    ) as sender, patch("app.core.audit.log"):
        resp = app_client.post(
            "/api/v1/auth/resend-verification",
            json={"email": INACTIVE_USER["email"]},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    set_tok.assert_called_once()
    sender.assert_called_once()
    written_token = set_tok.call_args.args[1]
    sent_url = sender.call_args.kwargs["verify_url"]
    assert written_token in sent_url


def test_resend_verification_active_user_no_email(app_client):
    """ACTIVE users must not receive a verification email — already verified."""
    with patch(
        "shared.db.repositories.user_repo.get_user_by_email",
        return_value=ACTIVE_USER,
    ), patch(
        "app.api.endpoints.auth.email_sender.send_verification_email",
    ) as sender, patch(
        "shared.db.repositories.user_repo.set_verification_token",
    ) as set_tok:
        resp = app_client.post(
            "/api/v1/auth/resend-verification",
            json={"email": ACTIVE_USER["email"]},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    sender.assert_not_called()
    set_tok.assert_not_called()


def test_resend_verification_unknown_email_no_leak(app_client):
    """Unknown email → same generic OK response, no email."""
    with patch(
        "shared.db.repositories.user_repo.get_user_by_email", return_value=None,
    ), patch(
        "app.api.endpoints.auth.email_sender.send_verification_email",
    ) as sender:
        resp = app_client.post(
            "/api/v1/auth/resend-verification",
            json={"email": "nobody@example.com"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    sender.assert_not_called()


# ── /api/v1/auth/register with EMAIL_VERIFICATION_REQUIRED ───────────


def test_register_with_verification_required_sets_inactive_and_sends_email(
    app_client, monkeypatch,
):
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    monkeypatch.setenv("APP_BASE_URL", "http://test.local")
    with patch(
        "shared.db.repositories.user_repo.get_user_by_email", return_value=None,
    ), patch(
        "shared.db.repositories.user_repo.get_user_by_username", return_value=None,
    ), patch(
        "shared.db.repositories.user_repo.create_user", return_value=42,
    ), patch(
        "shared.db.repositories.user_repo.set_verification_token", return_value=True,
    ) as set_tok, patch(
        "shared.db.repositories.user_repo.set_status",
    ) as set_st, patch(
        "app.api.endpoints.auth.email_sender.send_verification_email",
        return_value=True,
    ) as sender, patch(
        "app.api.endpoints.auth.hash_password", return_value="bcrypt-hash",
    ), patch("app.core.audit.log"):
        resp = app_client.post(
            "/api/v1/auth/register",
            json={
                "username": "newbie", "email": "newbie@example.com",
                "password": "SuperSecret123",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    # No access token until the user verifies.
    assert body["access_token"] == ""
    set_tok.assert_called_once()
    # Status flipped to INACTIVE (=0).
    set_st.assert_called_once()
    assert int(set_st.call_args.args[1]) == 9  # UserStatus.INACTIVE
    sender.assert_called_once()


# ── /api/v1/auth/login gate ──────────────────────────────────────────


def test_login_inactive_user_returns_403(app_client):
    """Login for unverified user returns 403 (not 401, which is bad creds)."""
    inactive = {**INACTIVE_USER, "password_hash": "hashed"}
    with patch(
        "shared.db.repositories.user_repo.get_user_by_email", return_value=inactive,
    ), patch(
        "app.api.endpoints.auth.verify_password", return_value=True,
    ):
        resp = app_client.post(
            "/api/v1/auth/login",
            json={"email": inactive["email"], "password": "whatever"},
        )
    assert resp.status_code == 403
    assert "not verified" in resp.json()["detail"].lower()


# ── Portal pages ─────────────────────────────────────────────────────


def test_portal_resend_verification_page_renders(app_client):
    resp = app_client.get("/app/resend-verification")
    assert resp.status_code == 200
    body = resp.text
    assert "email" in body.lower()
    # Form posts back to itself.
    assert 'action="/app/resend-verification"' in body


def test_portal_verify_email_valid_token_redirects_to_login(app_client):
    token = _fresh_token()
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
        return_value=INACTIVE_USER,
    ), patch(
        "shared.db.repositories.user_repo.mark_email_verified", return_value=True,
    ), patch("app.core.audit.log"):
        resp = app_client.get(
            f"/app/verify-email/{token}", follow_redirects=False,
        )
    assert resp.status_code in (302, 303)
    assert "/app/login" in resp.headers.get("location", "")


def test_portal_verify_email_bad_token_redirects_to_login(app_client):
    """Malformed token → redirect with error flash, no DB hit."""
    with patch(
        "shared.db.repositories.user_repo.get_user_by_verification_token",
    ) as lookup:
        resp = app_client.get(
            "/app/verify-email/totally-bogus", follow_redirects=False,
        )
    assert resp.status_code in (302, 303)
    assert "/app/login" in resp.headers.get("location", "")
    lookup.assert_not_called()


def test_portal_resend_verification_post_redirects(app_client):
    with patch(
        "shared.db.repositories.user_repo.get_user_by_email",
        return_value=INACTIVE_USER,
    ), patch(
        "shared.db.repositories.user_repo.set_verification_token", return_value=True,
    ), patch(
        "shared.notifications.email.send_verification_email", return_value=True,
    ):
        resp = app_client.post(
            "/app/resend-verification",
            data={"email": INACTIVE_USER["email"]},
            follow_redirects=False,
        )
    assert resp.status_code in (302, 303)
    assert "/app/login" in resp.headers.get("location", "")


# ── Token helpers ────────────────────────────────────────────────────


def test_verification_token_helpers_roundtrip():
    from app.core.tokens import (
        VERIFICATION_TOKEN_TTL_SEC,
        is_token_ts_expired,
        make_verification_token,
        parse_token_ts,
    )
    token = make_verification_token()
    ts = parse_token_ts(token)
    assert ts is not None
    assert abs(ts - int(time.time())) < 5
    assert not is_token_ts_expired(token, VERIFICATION_TOKEN_TTL_SEC)
    # Force-expired by passing ttl_sec=0.
    assert is_token_ts_expired(token, ttl_sec=0)
    # 24h is the documented TTL for verification.
    assert VERIFICATION_TOKEN_TTL_SEC == 86400
