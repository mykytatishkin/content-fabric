"""Google OAuth helpers shared between channel and streaming-account flows.

The Yii frontend exposed two parallel OAuth flows:

* ``channels`` — per ``platform_channels`` row (handled in ``app_portal.py``).
* ``streaming-accounts`` — per ``live_streaming_accounts`` row (Yii's
  ``YoutubeOauthController.actionOauth``; CFF panel below).

Both speak to ``https://accounts.google.com/o/oauth2/v2/auth`` and exchange
the returned ``code`` against ``https://oauth2.googleapis.com/token``.  The
only thing that differs is which DB table receives the resulting tokens.
This module factors out the common pieces.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)


# Streaming OAuth scopes — match what Yii's YoutubeOauthController used
# (https://www.googleapis.com/auth/youtube + youtube.force-ssl).  See
# .legacy/yii/yii/frontend/controllers/YoutubeOauthController.php:51-54.
STREAMING_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def build_google_auth_url(
    client_id: str,
    redirect_uri: str,
    scopes: list[str],
    state: str,
) -> str:
    """Return the consent-screen URL for an OAuth start request."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def make_state(prefix: str, account_id: int) -> str:
    """Pack ``{prefix}:{account_id}:{nonce}`` — verified by ``parse_state``.

    Mirrors Yii's ``accountId|csrf`` scheme but with a stable prefix so the
    two flows (channel / streaming-account) cannot be confused on callback.
    """
    nonce = secrets.token_urlsafe(16)
    return f"{prefix}:{account_id}:{nonce}"


def parse_state(state: str, expected_prefix: str) -> tuple[int | None, str | None]:
    """Return ``(account_id, nonce)`` or ``(None, None)`` if malformed."""
    if not state:
        return None, None
    parts = state.split(":", 2)
    if len(parts) != 3 or parts[0] != expected_prefix:
        return None, None
    try:
        account_id = int(parts[1])
    except (TypeError, ValueError):
        return None, None
    nonce = parts[2]
    if not nonce:
        return None, None
    return account_id, nonce


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    timeout: int = 30,
) -> dict[str, Any]:
    """POST to Google's token endpoint, return parsed JSON.

    Raises ``RuntimeError`` on HTTP error or non-JSON body — caller should
    catch and surface to the user as a flash message.
    """
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=timeout,
    )
    if not response.ok:
        logger.error(
            "Token exchange failed: HTTP %d body=%s",
            response.status_code,
            response.text[:500],
        )
        raise RuntimeError(
            f"Token exchange failed: HTTP {response.status_code}"
        )
    try:
        return response.json()
    except Exception as exc:
        raise RuntimeError(f"Token endpoint returned non-JSON: {exc}") from exc


def expires_at_from_payload(payload: dict[str, Any]) -> datetime | None:
    """Compute the absolute expiry timestamp from an ``expires_in`` seconds field."""
    expires_in = payload.get("expires_in")
    if not expires_in:
        return None
    try:
        seconds = int(expires_in)
    except (TypeError, ValueError):
        return None
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


__all__ = [
    "STREAMING_OAUTH_SCOPES",
    "build_google_auth_url",
    "make_state",
    "parse_state",
    "exchange_code_for_tokens",
    "expires_at_from_payload",
]
