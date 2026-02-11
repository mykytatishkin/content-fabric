"""Typed models for the YouTube OAuth re-authentication automation."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Sequence


class MFAChallengeError(Exception):
    """Raised when an MFA/security challenge is detected during login.

    The caller should skip the current channel and continue with the next one.
    """

    def __init__(self, message: str, screenshot_path: Optional[str] = None) -> None:
        super().__init__(message)
        self.screenshot_path = screenshot_path


class ReauthStatus(str, Enum):
    """High-level outcome of a re-authentication attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProxyConfig:
    """Proxy configuration for Playwright browser sessions."""

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class AutomationCredential:
    """Credential bundle required to automate a YouTube OAuth login."""

    channel_name: str
    login_email: str
    login_password: str
    profile_path: str
    client_id: str
    client_secret: str
    channel_id: Optional[str] = None  # YouTube channel ID (UC...) for channel selection
    totp_secret: Optional[str] = None
    backup_codes: Optional[Sequence[str]] = None
    proxy: Optional[ProxyConfig] = None
    user_agent: Optional[str] = None
    last_success_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    enabled: bool = True


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


