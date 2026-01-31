"""YouTube channel ID validation via YouTube Data API v3."""

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import api_settings


def validate_channel_id(channel_id: str) -> tuple[bool, str | None]:
    """
    Validate that a YouTube channel exists via API.

    Supports channel ID (UC...) and handle (@username).
    Returns (is_valid, canonical_channel_id or error_message).
    """
    api_key = api_settings.YOUTUBE_API_KEY
    if not api_key:
        return False, "YOUTUBE_API_KEY not configured"

    try:
        youtube = build("youtube", "v3", developerKey=api_key)

        # Handle @username format
        if channel_id.startswith("@"):
            request = youtube.channels().list(
                part="id",
                forHandle=channel_id.lstrip("@"),
            )
        else:
            request = youtube.channels().list(
                part="id",
                id=channel_id,
            )

        response = request.execute()
        items = response.get("items", [])

        if not items:
            return False, "Channel not found"

        return True, items[0]["id"]

    except HttpError as e:
        if e.resp.status == 403:
            return False, "YouTube API quota exceeded or access denied"
        if e.resp.status == 404:
            return False, "Channel not found"
        return False, str(e)
    except Exception as e:
        return False, str(e)
