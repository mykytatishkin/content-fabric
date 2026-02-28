"""YouTube API client — service creation + video operations."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from shared.youtube.token_refresh import build_credentials, ensure_fresh_credentials

logger = logging.getLogger(__name__)

MAX_TITLE_LEN = 100
MAX_DESCRIPTION_LEN = 5000
DEFAULT_CATEGORY = "22"  # People & Blogs
RESUMABLE_MAX_RETRIES = 3


def create_service(
    access_token: str,
    refresh_token: str | None,
    client_id: str,
    client_secret: str,
    token_expires_at=None,
    channel_id: int | None = None,
):
    """Build an authenticated ``youtube`` v3 service object.

    Automatically refreshes the token if needed and persists to DB.
    """
    creds = build_credentials(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_expires_at=token_expires_at,
    )
    creds = ensure_fresh_credentials(creds, channel_id=channel_id)
    return build("youtube", "v3", credentials=creds), creds


def upload_video(
    service,
    file_path: str,
    title: str,
    description: str | None = None,
    tags: list[str] | None = None,
    category_id: str = DEFAULT_CATEGORY,
    privacy: str = "public",
    thumbnail_path: str | None = None,
) -> dict[str, Any]:
    """Upload a video via resumable upload. Returns YouTube API response dict."""
    body: dict[str, Any] = {
        "snippet": {
            "title": title[:MAX_TITLE_LEN],
            "description": _sanitize(description or "", MAX_DESCRIPTION_LEN),
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = _resumable_upload(request)

    video_id = response.get("id")
    logger.info("Video uploaded: id=%s title=%s", video_id, title[:60])

    if thumbnail_path and video_id:
        set_thumbnail(service, video_id, thumbnail_path)

    return response


def set_thumbnail(service, video_id: str, thumbnail_path: str) -> None:
    """Upload a custom thumbnail for a video."""
    try:
        media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        service.thumbnails().set(videoId=video_id, media_body=media).execute()
        logger.info("Thumbnail set for video %s", video_id)
    except Exception:
        logger.exception("Failed to set thumbnail for %s", video_id)


def like_video(service, video_id: str) -> None:
    """Auto-like a video after upload."""
    try:
        service.videos().rate(id=video_id, rating="like").execute()
        logger.info("Liked video %s", video_id)
    except Exception:
        logger.exception("Failed to like video %s", video_id)


def post_comment(service, video_id: str, text: str) -> None:
    """Post a comment on a video."""
    try:
        service.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": text}
                    },
                }
            },
        ).execute()
        logger.info("Comment posted on video %s", video_id)
    except Exception:
        logger.exception("Failed to post comment on %s", video_id)


# ── internal helpers ─────────────────────────────────────────────────

def _resumable_upload(request) -> dict[str, Any]:
    """Execute a resumable upload with retry + exponential backoff."""
    response = None
    retry = 0
    while response is None:
        try:
            _, response = request.next_chunk()
            if response and "id" in response:
                return response
            if response is not None:
                raise RuntimeError(f"Upload returned unexpected response: {response}")
        except Exception as exc:
            err = str(exc)
            if "invalid_grant" in err or "Token has been expired or revoked" in err:
                raise  # auth errors — don't retry
            if retry < RESUMABLE_MAX_RETRIES:
                retry += 1
                wait = 2 ** retry
                logger.warning("Upload chunk failed, retrying in %ds (attempt %d/%d)", wait, retry, RESUMABLE_MAX_RETRIES)
                time.sleep(wait)
            else:
                raise
    return response  # type: ignore[return-value]


def _sanitize(text: str, max_len: int) -> str:
    """Remove null bytes / control chars and truncate."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    if len(cleaned) <= max_len:
        return cleaned
    # truncate at last newline or space before limit
    cut = cleaned[:max_len]
    last_nl = cut.rfind("\n")
    if last_nl > max_len * 0.8:
        return cut[:last_nl]
    last_sp = cut.rfind(" ")
    if last_sp > max_len * 0.8:
        return cut[:last_sp]
    return cut
