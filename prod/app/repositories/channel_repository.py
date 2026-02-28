"""Channel repository — thin wrapper delegating to shared.db.repositories.

Keeps the existing function signatures so that API endpoints continue to work
without changes.  Internally all queries go through the SQLAlchemy-based
shared layer.
"""

from __future__ import annotations

import json
from typing import Any

from app.schemas.channel import ChannelCreate, ChannelCredentials

from shared.db.repositories import channel_repo, console_repo, credential_repo


# ── OAuth credentials (consoles) ────────────────────────────────────

def list_oauth_credentials(enabled_only: bool = True) -> list[dict]:
    return console_repo.list_consoles_brief(enabled_only=enabled_only)




def get_console_by_id(console_id: int) -> dict | None:
    row = console_repo.get_console_by_id(console_id)
    if not row:
        return None
    # API only needs id + name for validation
    return {"id": row["id"], "name": row["name"]}


# ── Channel existence checks ────────────────────────────────────────

def channel_exists_by_name(name: str) -> bool:
    return channel_repo.channel_exists_by_name(name.strip())


def channel_exists_by_channel_id(platform_channel_id: str) -> bool:
    return channel_repo.channel_exists_by_channel_id(platform_channel_id.strip())


# ── Channel CRUD ────────────────────────────────────────────────────

def add_channel(data: ChannelCreate) -> int | None:
    project_id = data.project_id or channel_repo.get_default_project_id()
    if not project_id:
        raise ValueError("No project_id provided and no default project found")
    return channel_repo.add_channel(
        project_id=project_id,
        name=data.name,
        platform_channel_id=data.platform_channel_id,
        console_id=data.console_id,
        enabled=data.enabled,
    )


def add_account_credentials(channel_id: int, creds: ChannelCredentials) -> int:
    return credential_repo.add_credentials(
        channel_id=channel_id,
        login_email=creds.login_email,
        login_password=creds.login_password,
        totp_secret=creds.totp_secret,
        backup_codes=creds.backup_codes,
        proxy_host=creds.proxy_host,
        proxy_port=creds.proxy_port,
        proxy_username=creds.proxy_username,
        proxy_password=creds.proxy_password,
    )


def list_channels(project_id: int | None = None) -> list[dict]:
    return channel_repo.list_channels(project_id=project_id)


def get_channel_by_id(channel_id: int) -> dict | None:
    return channel_repo.get_channel_by_id(channel_id)
