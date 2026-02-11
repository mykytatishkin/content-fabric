"""Channels API endpoints."""

import logging
from uuid import UUID

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.channel_repository import (
    add_account_credentials,
    add_channel,
    channel_exists_by_channel_id,
    channel_exists_by_name,
    get_channel_by_id,
    get_console_by_id,
    list_channels,
    list_google_consoles,
)
from app.schemas.channel import Channel, ChannelCreate, GoogleConsole
from app.services.youtube_validator import validate_channel_id

logger = logging.getLogger(__name__)

router = APIRouter()
_templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@router.get("/google-consoles", response_model=list[GoogleConsole])
async def get_consoles():
    """List Google consoles for dropdown."""
    consoles = list_google_consoles(enabled_only=True)
    return [GoogleConsole(**c) for c in consoles]


@router.get("/", response_model=list[Channel])
async def get_channels(user_id: UUID | None = None):
    """List all channels, optionally filtered by user."""
    channels = list_channels(user_id=user_id)
    return [Channel(**c) for c in channels]


@router.get("/form", response_class=HTMLResponse)
async def channel_form(request: Request):
    """Serve add-channel form page."""
    consoles = list_google_consoles(enabled_only=True)
    return templates.TemplateResponse(
        "add_channel.html",
        {"request": request, "consoles": consoles},
    )


@router.post("/", response_model=Channel, status_code=201)
async def create_channel(data: ChannelCreate):
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
    is_valid, result = validate_channel_id(data.channel_id)
    if not is_valid:
        raise HTTPException(status_code=400, detail=result or "Invalid channel")
    canonical_id = result

    # Check duplicate by channel_id (after resolving @handle to UC...)
    if channel_exists_by_channel_id(canonical_id):
        raise HTTPException(status_code=409, detail="Канал с таким YouTube channel_id уже существует")

    data = ChannelCreate(**{**data.model_dump(), "channel_id": canonical_id})

    channel_id = add_channel(data)
    if channel_id is None:
        raise HTTPException(
            status_code=409,
            detail="Канал с таким названием или channel_id уже существует",
        )

    # Save RPA auth credentials if provided
    if data.credentials:
        try:
            add_account_credentials(data.name, data.credentials)
        except Exception as e:
            logger.error(
                "Channel %s created (id=%s) but credentials insert failed: %s",
                data.name, channel_id, e,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Канал создан (id={channel_id}), но не удалось сохранить креды: {e}",
            )

    channel = get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=500, detail="Channel created but not found")
    return Channel(**channel)


@router.get("/{channel_id}", response_model=Channel)
async def get_channel(channel_id: int):
    """Get channel by ID."""
    channel = get_channel_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return Channel(**channel)
