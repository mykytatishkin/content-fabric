"""Channels API endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import get_current_user
from app.repositories.channel_repository import (
    add_account_credentials,
    add_channel,
    channel_exists_by_channel_id,
    channel_exists_by_name,
    get_channel_by_id,
    get_console_by_id,
    list_channels,
    list_oauth_credentials,
)
from app.schemas.channel import Channel, ChannelCreate, OAuthCredential
from app.services.youtube_validator import validate_channel_id
from shared.db.models import UserStatus

logger = logging.getLogger(__name__)

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)
_templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@router.get("/google-consoles", response_model=list[OAuthCredential])
async def get_consoles(user: dict = Depends(get_current_user)):
    """List OAuth credentials for dropdown."""
    consoles = list_oauth_credentials(enabled_only=True)
    return [OAuthCredential(**c) for c in consoles]


@router.get("/", response_model=list[Channel])
async def get_channels(project_id: int | None = None, user: dict = Depends(get_current_user)):
    """List channels owned by current user (admins see all)."""
    channels = list_channels(project_id=project_id)
    if user["status"] != UserStatus.ADMIN.value:
        channels = [c for c in channels if c.get("created_by") == user["id"]]
    return [Channel(**c) for c in channels]


@router.get("/form", response_class=HTMLResponse)
async def channel_form(request: Request, user: dict = Depends(get_current_user)):
    """Serve add-channel form page."""
    consoles = list_oauth_credentials(enabled_only=True)
    return templates.TemplateResponse(
        "add_channel.html",
        {"request": request, "consoles": consoles},
    )


@router.post("/", response_model=Channel, status_code=201)
@_limiter.limit("10/minute")
async def create_channel(request: Request, data: ChannelCreate, user: dict = Depends(get_current_user)):
    """Add a new YouTube channel with validation."""
    # Validate console exists
    if not data.console_id:
        raise HTTPException(status_code=400, detail="console_id is required")
    console = get_console_by_id(data.console_id)
    if not console:
        raise HTTPException(status_code=400, detail="Invalid console_id")

    # Check duplicates by name
    if channel_exists_by_name(data.name):
        raise HTTPException(status_code=409, detail="Канал с таким названием уже существует")

    # Validate channel via YouTube API
    is_valid, result = validate_channel_id(data.platform_channel_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail=result or "Invalid channel")
    canonical_id = result

    # Check duplicate by platform_channel_id (after resolving @handle to UC...)
    if channel_exists_by_channel_id(canonical_id):
        raise HTTPException(status_code=409, detail="Канал с таким YouTube channel_id уже существует")

    data = ChannelCreate(**{**data.model_dump(), "platform_channel_id": canonical_id})

    logger.info("Creating channel: user=%s name=%r platform_id=%s", user["id"], data.name, canonical_id)
    channel_id = add_channel(data, created_by=user["id"])
    if channel_id is None:
        raise HTTPException(
            status_code=409,
            detail="Канал с таким названием или channel_id уже существует",
        )

    # Save RPA auth credentials if provided
    if data.credentials:
        try:
            add_account_credentials(channel_id, data.credentials)
        except Exception as e:
            logger.error(
                "Channel %s created (id=%s) but credentials insert failed: %s",
                data.name, channel_id, e, exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Канал создан (id={channel_id}), но не удалось сохранить креды. Проверьте логи.",
            )

    channel = get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=500, detail="Channel created but not found")
    logger.info("Channel created: id=%s name=%r", channel_id, data.name)
    return Channel(**channel)


@router.get("/{channel_id}", response_model=Channel)
async def get_channel(channel_id: int, user: dict = Depends(get_current_user)):
    """Get channel by ID (owner or admin only)."""
    channel = get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if user["status"] != UserStatus.ADMIN.value and channel.get("created_by") != user["id"]:
        raise HTTPException(status_code=404, detail="Channel not found")
    return Channel(**channel)


@router.get("/{channel_id}/stats")
async def get_channel_stats(channel_id: int, days: int = 30, user: dict = Depends(get_current_user)):
    """Get daily statistics for a channel (owner or admin only)."""
    from shared.db.repositories import stats_repo
    channel = get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if user["status"] != UserStatus.ADMIN.value and channel.get("created_by") != user["id"]:
        raise HTTPException(status_code=404, detail="Channel not found")
    stats = stats_repo.get_channel_stats(channel_id, days=days)
    return {"channel_id": channel_id, "days": days, "stats": stats}
