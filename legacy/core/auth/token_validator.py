#!/usr/bin/env python3
"""Shared utility for validating YouTube OAuth refresh tokens.

Used by both the reauth service and the standalone checker script.
"""

from __future__ import annotations

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.utils.logger import get_logger

logger = get_logger("token_validator")


def test_refresh_token(channel, db) -> tuple[bool, str]:
    """Test if a channel's refresh_token is valid by refreshing it and making an API call.

    Args:
        channel: :class:`YouTubeChannel` instance (must have ``refresh_token``).
        db: ``YouTubeMySQLDatabase`` instance used to look up console credentials.

    Returns:
        ``(is_valid, message)`` – *is_valid* is ``True`` when the token was
        successfully refreshed **and** the subsequent YouTube API call
        returned channel data.
    """
    if not channel.refresh_token:
        return False, "No refresh_token in database"

    # Get OAuth client credentials from the linked Google Console
    credentials = db.get_console_credentials_for_channel(channel.name)
    if not credentials:
        return False, "No console credentials found. Channel must have console_name or console_id set."

    client_id = credentials["client_id"]
    client_secret = credentials["client_secret"]

    try:
        creds = Credentials(
            token=None,  # Force a refresh
            refresh_token=channel.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )

        # Attempt to refresh the access token
        creds.refresh(Request())

        # Verify the refreshed token actually works with the YouTube API
        youtube_service = build("youtube", "v3", credentials=creds)
        response = youtube_service.channels().list(part="snippet", mine=True).execute()

        if response.get("items"):
            return True, "Valid - successfully refreshed and tested with API"
        else:
            return False, "Refresh succeeded but API call returned no channels"

    except HttpError as e:
        error_str = str(e)
        if "invalid_grant" in error_str.lower():
            return False, f"Invalid/revoked: {error_str[:100]}"
        return False, f"HTTP Error: {error_str[:100]}"
    except Exception as e:
        error_str = str(e)
        if "invalid_grant" in error_str.lower():
            return False, f"Invalid/revoked: {error_str[:100]}"
        return False, f"Error: {error_str[:100]}"
