"""Typed models for the YouTube OAuth re-authentication."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class ReauthStatus(str, Enum):
    """High-level outcome of a re-authentication attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ReauthResult:
    """Result snapshot of an automation run for a specific channel."""

    channel_name: str
    status: ReauthStatus
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
