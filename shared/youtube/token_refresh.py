"""YouTube OAuth token refresh logic."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from shared.db.repositories import channel_repo

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.force-ssl"]

TOKEN_REFRESH_MARGIN = timedelta(minutes=5)


def build_credentials(
    access_token: str,
    refresh_token: str | None,
    client_id: str,
    client_secret: str,
    token_expires_at: datetime | str | None = None,
) -> Credentials:
    """Build a google.oauth2.credentials.Credentials object."""
    expiry = None
    if token_expires_at:
        if isinstance(token_expires_at, str):
            expiry = datetime.fromisoformat(token_expires_at)
        else:
            expiry = token_expires_at

    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
        expiry=expiry,
    )


def ensure_fresh_credentials(
    creds: Credentials,
    channel_id: int | None = None,
) -> Credentials:
    """Refresh credentials if expired or about to expire.

    If *channel_id* is provided the refreshed token is persisted to the DB.
    Raises on ``invalid_grant`` (revoked refresh token).
    """
    needs_refresh = False
    if creds.expired:
        needs_refresh = True
    elif creds.expiry:
        if creds.expiry - datetime.now(timezone.utc) < TOKEN_REFRESH_MARGIN:
            needs_refresh = True
    else:
        needs_refresh = True  # no expiry info → refresh to be safe

    if not needs_refresh:
        return creds

    if not creds.refresh_token:
        raise RuntimeError("No refresh_token available; re-authentication required")

    logger.info("Refreshing YouTube OAuth token (channel_id=%s)", channel_id)
    try:
        creds.refresh(Request())
    except RefreshError as e:
        logger.warning("Refresh token revoked or expired (channel_id=%s): %s", channel_id, e)
        raise RuntimeError("Refresh token revoked or expired; re-authentication required") from e

    if channel_id is not None:
        channel_repo.update_channel_tokens(
            channel_id=channel_id,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_expires_at=creds.expiry,
        )
        logger.info("Persisted refreshed token for channel_id=%s", channel_id)

    return creds
