"""Service orchestration for YouTube OAuth re-authentication.

Uses google-auth-oauthlib InstalledAppFlow for the token exchange.
When login credentials are available in the DB, Selenium + undetected-chromedriver
automates the Google sign-in flow; otherwise the user authorizes manually.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Thread
from typing import Iterable, List, Optional

from google_auth_oauthlib.flow import InstalledAppFlow

from shared.youtube.reauth.models import (
    ReauthResult,
    ReauthStatus,
)
from shared.db.repositories import channel_repo, console_repo, credential_repo, audit_repo
from shared.notifications import telegram

import logging

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


@dataclass
class OAuthSettings:
    """Shared OAuth settings independent of channel credentials."""

    redirect_port: int = 8080
    prompt: str = "consent"
    access_type: str = "offline"
    timeout_seconds: int = 300


@dataclass
class ServiceConfig:
    """High-level configuration for the re-auth service."""

    oauth_settings: OAuthSettings = field(default_factory=OAuthSettings)
    open_browser: bool = True
    headless: bool = False


@dataclass
class _ChannelOAuthInfo:
    """Minimal info needed to run OAuth for a channel."""

    channel_id: int
    channel_name: str
    client_id: str
    client_secret: str
    login_hint: Optional[str] = None
    login_password: Optional[str] = None
    totp_secret: Optional[str] = None


class YouTubeReauthService:
    """Coordinates database lookup and google-auth-oauthlib InstalledAppFlow."""

    def __init__(self, service_config: Optional[ServiceConfig] = None) -> None:
        self.config = service_config or ServiceConfig()

    def _load_oauth_info(self, channel_id: int) -> Optional[_ChannelOAuthInfo]:
        """Load channel + OAuth client credentials from DB."""
        channel = channel_repo.get_channel_by_id(channel_id)
        if not channel:
            logger.error("Channel not found: id=%d", channel_id)
            return None

        client_id = None
        client_secret = None
        console_id = channel.get("console_id")
        if console_id:
            console = console_repo.get_console_by_id(console_id)
            if console:
                client_id = console.get("client_id")
                client_secret = console.get("client_secret")

        if not client_id:
            client_id = os.getenv("YOUTUBE_MAIN_CLIENT_ID")
        if not client_secret:
            client_secret = os.getenv("YOUTUBE_MAIN_CLIENT_SECRET")

        if not client_id or not client_secret:
            logger.error(
                "Missing OAuth client credentials for channel %d (%s)",
                channel_id, channel.get("name"),
            )
            return None

        login_hint = None
        login_password = None
        totp_secret = None
        try:
            creds = credential_repo.get_credentials(channel_id)
            if creds:
                if creds.get("login_email"):
                    login_hint = creds["login_email"]
                if creds.get("login_password"):
                    login_password = creds["login_password"]
                if creds.get("totp_secret"):
                    totp_secret = creds["totp_secret"]
        except Exception:
            pass

        return _ChannelOAuthInfo(
            channel_id=channel_id,
            channel_name=channel.get("name", f"channel-{channel_id}"),
            client_id=client_id,
            client_secret=client_secret,
            login_hint=login_hint,
            login_password=login_password,
            totp_secret=totp_secret,
        )

    def _run_channel(self, info: _ChannelOAuthInfo) -> ReauthResult:
        """Run InstalledAppFlow for a single channel."""
        logger.info(
            "Starting OAuth reauth for channel %s (id=%d)", info.channel_name, info.channel_id
        )

        audit_id = audit_repo.create_reauth_audit(
            channel_id=info.channel_id,
            status=ReauthStatus.SKIPPED.value,
            initiated_at=datetime.now(timezone.utc),
            trigger_reason="cli_reauth",
            metadata={"stage": "initiated"},
        )

        client_config = {
            "installed": {
                "client_id": info.client_id,
                "client_secret": info.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }

        try:
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            port = self.config.oauth_settings.redirect_port

            hint_msg = f" ({info.login_hint})" if info.login_hint else ""
            print(f"\n{'='*60}")
            print(f"  Авторизація каналу: {info.channel_name} (id={info.channel_id}){hint_msg}")
            print(f"{'='*60}")

            can_automate = bool(info.login_hint and info.login_password)

            if can_automate:
                flow.redirect_uri = f"http://localhost:{port}/"
                auth_url = flow.authorization_url(
                    prompt=self.config.oauth_settings.prompt,
                    access_type=self.config.oauth_settings.access_type,
                    login_hint=info.login_hint,
                )[0]

                from shared.youtube.reauth.selenium_auth import run_automated_oauth

                selenium_error: Optional[Exception] = None

                def _selenium_worker() -> None:
                    nonlocal selenium_error
                    try:
                        run_automated_oauth(
                            auth_url=auth_url,
                            login_email=info.login_hint,
                            login_password=info.login_password,
                            totp_secret=info.totp_secret,
                            headless=self.config.headless,
                            timeout=self.config.oauth_settings.timeout_seconds,
                        )
                    except Exception as exc:
                        selenium_error = exc
                        logger.warning("Selenium automation failed: %s", exc)

                print("  Автоматичний режим (Selenium)…")
                thread = Thread(target=_selenium_worker, daemon=True)
                thread.start()

                kwargs = {
                    "port": port,
                    "prompt": self.config.oauth_settings.prompt,
                    "access_type": self.config.oauth_settings.access_type,
                    "open_browser": False,
                    "timeout_seconds": self.config.oauth_settings.timeout_seconds,
                }
                if info.login_hint:
                    kwargs["login_hint"] = info.login_hint

                creds = flow.run_local_server(**kwargs)

                thread.join(timeout=5)
                if selenium_error:
                    logger.warning(
                        "Selenium thread had error for %s but flow still completed: %s",
                        info.channel_name, selenium_error,
                    )
            else:
                if not self.config.open_browser:
                    print("  Відкрийте посилання в браузері для авторизації.")
                    print(f"  (Для віддаленого сервера: ssh -L {port}:localhost:{port} user@server)")

                kwargs = {
                    "port": port,
                    "prompt": self.config.oauth_settings.prompt,
                    "access_type": self.config.oauth_settings.access_type,
                    "open_browser": self.config.open_browser,
                    "timeout_seconds": self.config.oauth_settings.timeout_seconds,
                }
                if info.login_hint:
                    kwargs["login_hint"] = info.login_hint

                creds = flow.run_local_server(**kwargs)

            if not creds or not creds.token:
                result = ReauthResult(
                    channel_name=info.channel_name,
                    status=ReauthStatus.FAILED,
                    error="No credentials received from OAuth flow",
                )
            elif not creds.refresh_token:
                logger.warning(
                    "OAuth succeeded but no refresh_token for channel %d (%s)",
                    info.channel_id, info.channel_name,
                )
                result = ReauthResult(
                    channel_name=info.channel_name,
                    status=ReauthStatus.FAILED,
                    error="Refresh token not received from Google (ensure prompt=consent)",
                )
            else:
                expires_in = None
                token_expires_at = None
                if creds.expiry:
                    expiry = creds.expiry
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    token_expires_at = expiry
                    delta = expiry - datetime.now(timezone.utc)
                    expires_in = max(int(delta.total_seconds()), 0)

                channel_repo.update_channel_tokens(
                    channel_id=info.channel_id,
                    access_token=creds.token,
                    refresh_token=creds.refresh_token,
                    token_expires_at=token_expires_at,
                )
                logger.info("Tokens updated for channel %d (%s)", info.channel_id, info.channel_name)
                result = ReauthResult(
                    channel_name=info.channel_name,
                    status=ReauthStatus.SUCCESS,
                    access_token=creds.token,
                    refresh_token=creds.refresh_token,
                    expires_in=expires_in,
                )

        except Exception as exc:
            logger.exception("OAuth flow failed for channel %s: %s", info.channel_name, exc)
            result = ReauthResult(
                channel_name=info.channel_name,
                status=ReauthStatus.FAILED,
                error=str(exc),
            )

        # Mark attempt in credentials table (if entry exists)
        try:
            credential_repo.mark_attempt(
                info.channel_id,
                success=result.status == ReauthStatus.SUCCESS,
                error_message=result.error,
            )
        except Exception:
            pass

        # Complete audit
        if audit_id is not None:
            audit_repo.complete_reauth_audit(
                audit_id,
                status=result.status.value,
                completed_at=datetime.now(timezone.utc),
                error_message=result.error,
                metadata=result.metadata,
            )

        logger.info(
            "OAuth reauth completed for %s: status=%s",
            info.channel_name, result.status.value,
        )

        if result.status != ReauthStatus.SUCCESS:
            self._send_error_notification(result)

        return result

    def run_for_channels(self, channel_ids: Iterable[int]) -> List[ReauthResult]:
        """Run the OAuth flow for one or more channels sequentially."""
        results: List[ReauthResult] = []
        for channel_id in channel_ids:
            info = self._load_oauth_info(channel_id)
            if not info:
                failed = ReauthResult(
                    channel_name=f"channel-{channel_id}",
                    status=ReauthStatus.FAILED,
                    error="OAuth credentials not configured (missing console or client_id/secret)",
                )
                results.append(failed)
                self._send_error_notification(failed)
                continue

            result = self._run_channel(info)
            results.append(result)
        return results

    run_sync = run_for_channels

    @staticmethod
    def _send_error_notification(result: ReauthResult) -> None:
        """Send Telegram notification about reauth error."""
        try:
            error = result.error or "Unknown error"
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            message = (
                f"Проблема з авторизацією YouTube\n\n"
                f"Канал: {result.channel_name}\n"
                f"Статус: {result.status.value}\n"
                f"Помилка: {error}\n\n"
                f"Час: {timestamp}"
            )
            telegram.send(message)
        except Exception as e:
            logger.error("Failed to send reauth notification: %s", e)
