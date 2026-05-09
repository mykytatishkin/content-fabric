"""Build authenticated googleapiclient services for ``live_streaming_accounts`` rows.

Streaming uses a separate OAuth account from the per-channel uploader (see
``shared.youtube.client.create_service`` which is keyed off
``platform_channels``).  Streaming accounts live in ``live_streaming_accounts``
and are referenced by ``live_stream_configurations.streaming_account_id``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Tuple

from sqlalchemy import text

from shared.db.connection import get_connection
from shared.youtube.token_refresh import build_credentials, ensure_fresh_credentials

try:  # pragma: no cover
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover
    build = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


def _persist_refreshed_tokens(
    streaming_account_id: int,
    access_token: str,
    refresh_token: str | None,
    expiry: datetime | None,
) -> None:
    """Write a refreshed token tuple back to ``live_streaming_accounts``."""
    try:
        with get_connection() as conn:
            conn.execute(
                text(
                    """
                    UPDATE live_streaming_accounts
                    SET access_token = :access_token,
                        refresh_token = COALESCE(:refresh_token, refresh_token),
                        token_expires_at = :token_expires_at,
                        updated_at = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": streaming_account_id,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": expiry,
                },
            )
        logger.info(
            "Persisted refreshed token for streaming_account_id=%s",
            streaming_account_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to persist refreshed token for streaming_account_id=%s",
            streaming_account_id,
        )


def build_service_for_streaming_account(
    streaming_account_id: int,
) -> Tuple[Any, dict[str, Any]]:
    """Load a streaming account row, refresh its OAuth token, return ``(service, row)``.

    Raises ``RuntimeError`` if the account doesn't exist, is disabled, or has
    no refresh token (i.e. needs re-auth via the reauth flow).
    """
    with get_connection() as conn:
        row = (
            conn.execute(
                text(
                    """
                    SELECT id, project_id, platform, name,
                           client_id, client_secret,
                           access_token, refresh_token, token_expires_at,
                           enabled
                    FROM live_streaming_accounts
                    WHERE id = :id
                    """
                ),
                {"id": streaming_account_id},
            )
            .mappings()
            .first()
        )
    if not row:
        raise RuntimeError(
            f"live_streaming_accounts row {streaming_account_id} not found"
        )
    account = dict(row)
    if not account.get("enabled"):
        raise RuntimeError(
            f"Streaming account {streaming_account_id} is disabled"
        )
    if not account.get("refresh_token"):
        raise RuntimeError(
            f"Streaming account {streaming_account_id} has no refresh_token; re-auth required"
        )

    creds = build_credentials(
        access_token=account.get("access_token") or "",
        refresh_token=account.get("refresh_token"),
        client_id=account.get("client_id") or "",
        client_secret=account.get("client_secret") or "",
        token_expires_at=account.get("token_expires_at"),
    )

    before_token = creds.token
    creds = ensure_fresh_credentials(creds, channel_id=None)
    if creds.token != before_token:
        _persist_refreshed_tokens(
            streaming_account_id=streaming_account_id,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            expiry=creds.expiry,
        )

    if build is None:  # pragma: no cover - real env always has it
        raise RuntimeError("googleapiclient.discovery.build is not available")

    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    return service, account
