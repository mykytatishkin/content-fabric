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
    # #region agent log
    # Use the same debug log mechanism as in config.py instead of hardcoding the path
    from app.core.config import _log
    _log({"hypothesisId": "D", "location": "youtube_validator.py:validate", "message": "api_key at validate", "data": {"has_key": bool(api_key), "key_len": len(api_key or "")}})
    # #endregion
    if not api_key:
        return False, "YOUTUBE_API_KEY not configured"

    try:
        youtube = build("youtube", "v3", developerKey=api_key)

        # Handle @username format: resolve via Search API (forHandle not in cached discovery)
        if channel_id.startswith("@"):
            handle = channel_id.lstrip("@")
            # Search by @handle so API is more likely to match the channel handle
            search_response = youtube.search().list(
                part="snippet",
                type="channel",
                q="@" + handle,
                maxResults=1,
            ).execute()
            search_items = search_response.get("items", [])
            if not search_items:
                return False, "Channel not found"
            resolved_id = search_items[0]["snippet"]["channelId"]
            # Validate and return canonical ID via channels.list
            request = youtube.channels().list(part="id", id=resolved_id)
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
