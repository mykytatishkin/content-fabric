"""YouTube liveBroadcasts lifecycle helpers.

Mirrors the legacy Yii ``common\\services\\YoutubeService.php`` (lines ~50-380)
so that ``/api/v1/streams/start`` and ``/api/v1/streams/stop`` drive the YouTube
broadcast state machine (``ready`` -> ``live`` -> ``complete``) in addition to
starting/stopping the local ffmpeg systemd unit.

All functions accept a built ``googleapiclient`` ``Resource`` (created via
:mod:`shared.youtube.streaming_accounts`).  ``HttpError`` exceptions are logged
and re-raised so callers can decide whether to abort the start / stop flow.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

try:  # pragma: no cover - import guard for test environment
    from googleapiclient.errors import HttpError as _RealHttpError
    # In tests conftest pre-registers googleapiclient as a MagicMock so the
    # import "succeeds" but yields a MagicMock — which is not a class and
    # cannot be used in an `except` clause.  Detect that and fall through.
    if not (isinstance(_RealHttpError, type) and issubclass(_RealHttpError, BaseException)):
        raise TypeError("googleapiclient.errors.HttpError is not a real class")
    HttpError = _RealHttpError  # type: ignore[misc]
except Exception:  # pragma: no cover
    class HttpError(Exception):  # type: ignore[no-redef]
        """Fallback when googleapiclient isn't importable (tests)."""


logger = logging.getLogger(__name__)

BroadcastStatus = Literal["testing", "live", "complete"]
PrivacyStatus = Literal["public", "unlisted", "private"]

_REUSABLE_STATES = {"ready", "testing", "live", "created"}


# ── tag parsing ────────────────────────────────────────────────────


def parse_tags(raw: str | None) -> list[str]:
    """Split a free-form tag string into a deduped, trimmed list.

    Mirrors Yii ``YoutubeService::parseTags`` (line ~373) but additionally
    deduplicates while preserving order.  Splits on ``,``, ``;`` and newlines.
    """
    if not raw:
        return []
    parts = re.split(r"[,;\n]+", str(raw))
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        t = p.strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


# ── liveBroadcasts CRUD ────────────────────────────────────────────


def get_broadcast(service, broadcast_id: str) -> dict[str, Any] | None:
    """Return a broadcast resource or ``None`` if not found.

    Mirrors Yii ``getBroadcast`` (line ~113).
    """
    try:
        resp = (
            service.liveBroadcasts()
            .list(part="id,snippet,status,contentDetails", id=broadcast_id)
            .execute()
        )
    except HttpError as exc:
        logger.exception("getBroadcast(%s) failed", broadcast_id)
        raise RuntimeError(f"YouTube getBroadcast failed: {exc}") from exc
    items = resp.get("items") or []
    return items[0] if items else None


def create_broadcast(
    service,
    title: str,
    description: str = "",
    scheduled_start_time: str | None = None,
    privacy: PrivacyStatus = "public",
) -> dict[str, Any]:
    """Insert a new liveBroadcast.  Mirrors Yii ``createBroadcast`` (line ~122)."""
    if not scheduled_start_time:
        scheduled_start_time = (
            datetime.now(tz=timezone.utc) + timedelta(seconds=10)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    body = {
        "snippet": {
            "title": title or "Live Stream",
            "description": description or "",
            "scheduledStartTime": scheduled_start_time,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
        "contentDetails": {
            "enableAutoStart": True,
            "enableAutoStop": True,
        },
    }

    try:
        return (
            service.liveBroadcasts()
            .insert(part="snippet,status,contentDetails", body=body)
            .execute()
        )
    except HttpError as exc:
        logger.exception("createBroadcast(title=%s) failed", title[:60])
        raise RuntimeError(f"YouTube createBroadcast failed: {exc}") from exc


def update_broadcast_meta(
    service,
    broadcast_id: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,  # noqa: ARG001 — kept for API parity
    scheduled_start_time: str | None = None,
) -> None:
    """Update broadcast snippet (title/description/scheduled time).

    Mirrors Yii ``updateBroadcastMeta`` (line ~149).  ``tags`` are NOT a
    snippet field on ``liveBroadcasts`` — they go on the underlying video,
    handled by :func:`update_video_meta`.  We accept the kwarg so callers can
    pass meta uniformly.
    """
    if not scheduled_start_time:
        existing = get_broadcast(service, broadcast_id)
        scheduled_start_time = (
            (existing or {}).get("snippet", {}).get("scheduledStartTime")
        )
    if not scheduled_start_time:
        scheduled_start_time = (
            datetime.now(tz=timezone.utc) + timedelta(seconds=30)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    body = {
        "id": broadcast_id,
        "snippet": {
            "title": title or "",
            "description": description or "",
            "scheduledStartTime": scheduled_start_time,
        },
    }

    try:
        service.liveBroadcasts().update(part="snippet", body=body).execute()
    except HttpError as exc:
        logger.exception("updateBroadcastMeta(%s) failed", broadcast_id)
        raise RuntimeError(f"YouTube updateBroadcastMeta failed: {exc}") from exc


def update_video_meta(
    service,
    video_id: str,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    category_id: str = "22",
) -> None:
    """Update the underlying video snippet (title/description/tags).

    Mirrors Yii ``updateVideoMeta`` (line ~175).  For live broadcasts the
    broadcast id == video id.
    """
    snippet: dict[str, Any] = {
        "title": title or "",
        "description": description or "",
        "categoryId": category_id,
    }
    if tags:
        clean = [str(t).strip() for t in tags if str(t).strip()]
        if clean:
            snippet["tags"] = clean

    body = {"id": video_id, "snippet": snippet}
    try:
        service.videos().update(part="snippet", body=body).execute()
    except HttpError as exc:
        logger.exception("updateVideoMeta(%s) failed", video_id)
        raise RuntimeError(f"YouTube updateVideoMeta failed: {exc}") from exc


# ── liveStreams (ingest) lookup + bind ─────────────────────────────


def find_live_stream_id_by_stream_key(
    service, stream_key: str, max_pages: int = 6
) -> str | None:
    """Find a ``liveStreams`` resource id whose CDN stream key matches.

    Paginates ``liveStreams.list(mine=True, maxResults=50)`` up to
    ``max_pages`` pages.  Mirrors Yii ``findLiveStreamIdByStreamKey``
    (line ~253).
    """
    sk = (stream_key or "").strip()
    if not sk:
        return None

    page_token: str | None = None
    for _ in range(max_pages):
        kwargs: dict[str, Any] = {
            "part": "id,cdn",
            "mine": True,
            "maxResults": 50,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        try:
            resp = service.liveStreams().list(**kwargs).execute()
        except HttpError as exc:
            logger.exception("findLiveStreamIdByStreamKey failed")
            raise RuntimeError(
                f"YouTube findLiveStreamIdByStreamKey failed: {exc}"
            ) from exc

        for item in resp.get("items") or []:
            sn = (
                item.get("cdn", {})
                .get("ingestionInfo", {})
                .get("streamName")
            )
            if sn and sn == sk:
                return str(item.get("id") or "")

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return None


def bind_broadcast_to_stream(
    service, broadcast_id: str, stream_id: str
) -> None:
    """Bind a broadcast to an ingest stream.  Mirrors Yii ``bindBroadcastToStream`` (line ~282)."""
    try:
        service.liveBroadcasts().bind(
            id=broadcast_id,
            streamId=stream_id,
            part="id,contentDetails",
        ).execute()
    except HttpError as exc:
        logger.exception(
            "bindBroadcastToStream(%s, %s) failed", broadcast_id, stream_id
        )
        raise RuntimeError(f"YouTube bindBroadcastToStream failed: {exc}") from exc


def transition_broadcast(
    service, broadcast_id: str, to_status: BroadcastStatus
) -> None:
    """Transition broadcast lifecycle (testing | live | complete).

    Mirrors Yii ``transitionBroadcast`` (line ~292) and
    ``YoutubeLiveService::goLive`` / ``::complete``.
    """
    if to_status not in ("testing", "live", "complete"):
        raise ValueError(f"Invalid broadcast status: {to_status}")
    try:
        service.liveBroadcasts().transition(
            broadcastStatus=to_status,
            id=broadcast_id,
            part="id,status",
        ).execute()
    except HttpError as exc:
        logger.exception(
            "transitionBroadcast(%s -> %s) failed", broadcast_id, to_status
        )
        raise RuntimeError(
            f"YouTube transitionBroadcast({to_status}) failed: {exc}"
        ) from exc


# ── high-level orchestration ───────────────────────────────────────


def ensure_broadcast_for_stream(
    service, stream: dict[str, Any], fallback_title: str
) -> str:
    """Reuse the stream's existing broadcast if still usable, else create a new one.

    Mirrors Yii ``ensureBroadcastForStream`` (line ~303) but with a stricter
    reuse rule: we only reuse broadcasts in ``ready`` / ``testing`` / ``live``
    / ``created`` lifecycle states.  Returns the broadcast id.
    """
    existing_id = (stream.get("platform_broadcast_id") or "").strip()
    if existing_id:
        b = get_broadcast(service, existing_id)
        if b:
            life = (b.get("status") or {}).get("lifeCycleStatus", "")
            if life in _REUSABLE_STATES:
                return existing_id
            logger.info(
                "Broadcast %s is in unusable state %s — creating new one",
                existing_id, life,
            )

    title = (stream.get("title") or stream.get("name") or fallback_title).strip()
    description = stream.get("description") or ""
    created = create_broadcast(
        service,
        title=title,
        description=description,
        privacy="public",
    )
    new_id = str(created.get("id") or "")
    if not new_id:
        raise RuntimeError("YouTube createBroadcast returned no id")
    return new_id


def prepare_broadcast_for_start(
    service, stream: dict[str, Any]
) -> dict[str, Any]:
    """One-shot pre-start orchestration: ensure broadcast, bind stream, push meta + thumb.

    Mirrors Yii ``prepareBroadcastForStart`` (line ~331).  Returns
    ``{"broadcast_id": str, "stream_id": str | None}``.

    Errors on bind / meta / thumbnail are logged but do NOT abort — the
    caller still wants the systemd unit to start so ffmpeg pushes RTMP.
    """
    fallback_title = stream.get("name") or "Live Stream"
    broadcast_id = ensure_broadcast_for_stream(
        service, stream, fallback_title=fallback_title
    )

    stream_id: str | None = None
    sk = (stream.get("stream_key") or "").strip()
    if sk:
        try:
            stream_id = find_live_stream_id_by_stream_key(service, sk)
        except Exception:  # noqa: BLE001
            logger.warning(
                "find_live_stream_id_by_stream_key failed; continuing without bind",
                exc_info=True,
            )
        if stream_id:
            try:
                bind_broadcast_to_stream(service, broadcast_id, stream_id)
            except Exception:  # noqa: BLE001
                # don't abort start: usual cause is broadcast already bound
                logger.warning(
                    "bind_broadcast_to_stream failed; continuing", exc_info=True
                )

    title = (stream.get("title") or stream.get("name") or fallback_title)
    description = stream.get("description") or ""
    tags = parse_tags(stream.get("tags"))

    try:
        update_broadcast_meta(service, broadcast_id, title, description)
    except Exception:  # noqa: BLE001
        logger.warning("update_broadcast_meta failed; continuing", exc_info=True)

    try:
        update_video_meta(service, broadcast_id, title, description, tags=tags)
    except Exception:  # noqa: BLE001
        # video may not exist yet for fresh broadcast — that's fine
        logger.info(
            "update_video_meta failed (likely video not yet published); continuing",
            exc_info=True,
        )

    thumb = stream.get("thumbnail_path")
    if thumb:
        try:
            from shared.youtube.client import set_thumbnail

            set_thumbnail(service, broadcast_id, str(thumb))
        except Exception:  # noqa: BLE001
            logger.warning("set_thumbnail failed; continuing", exc_info=True)

    return {"broadcast_id": broadcast_id, "stream_id": stream_id}
