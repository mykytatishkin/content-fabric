"""Service orchestration for automated YouTube OAuth re-authentication.

Rewritten for prod: uses shared.db.repositories instead of legacy YouTubeMySQLDatabase.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from shared.youtube.reauth.models import (
    AutomationCredential,
    BrowserConfig,
    MFAChallengeError,
    ProxyConfig,
    ReauthResult,
    ReauthStatus,
)
from shared.youtube.reauth.oauth_flow import OAuthConfig, OAuthFlow
from shared.youtube.reauth.playwright_client import playwright_context, prepare_oauth_consent_page
from shared.db.repositories import channel_repo, console_repo, credential_repo, audit_repo
from shared.notifications import telegram

import logging

logger = logging.getLogger(__name__)


@dataclass
class OAuthSettings:
    """Shared OAuth settings independent of channel credentials."""

    redirect_port: int = 8080
    scopes: Optional[list[str]] = None
    prompt: str = "consent"
    access_type: str = "offline"
    timeout_seconds: int = 300


@dataclass
class ServiceConfig:
    """High-level configuration for the re-auth service."""

    browser: BrowserConfig = field(default_factory=BrowserConfig)
    oauth_settings: OAuthSettings = field(default_factory=OAuthSettings)
    max_concurrent_sessions: int = 1


class YouTubeReauthService:
    """Coordinates database credentials, Playwright automation, and OAuth exchange."""

    def __init__(
        self,
        service_config: Optional[ServiceConfig] = None,
        open_browser: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.config = service_config or ServiceConfig()
        self.open_browser = open_browser or self._default_open_browser

    @staticmethod
    def _default_open_browser(url: str) -> None:
        """Default no-op open_browser handler; Playwright handles navigation."""
        logger.info("Navigate browser to: %s", url)

    def _load_credential(self, channel_id: int) -> Optional[AutomationCredential]:
        """Load channel + login creds + OAuth console from DB."""
        channel = channel_repo.get_channel_by_id(channel_id)
        if not channel:
            logger.error("Channel not found: id=%d", channel_id)
            return None

        creds = credential_repo.get_credentials(channel_id)
        if not creds:
            logger.error("No login credentials for channel %d (%s)", channel_id, channel.get("name"))
            return None

        # Get OAuth client credentials from console
        console_id = channel.get("console_id")
        client_id = None
        client_secret = None

        if console_id:
            console = console_repo.get_console_by_id(console_id)
            if console:
                client_id = console.get("client_id")
                client_secret = console.get("client_secret")

        # Fallback to environment variables
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

        proxy = None
        if creds.get("proxy_host") and creds.get("proxy_port"):
            proxy = ProxyConfig(
                host=creds["proxy_host"],
                port=int(creds["proxy_port"]),
                username=creds.get("proxy_username"),
                password=creds.get("proxy_password"),
            )

        return AutomationCredential(
            channel_name=channel.get("name", f"channel-{channel_id}"),
            login_email=creds["login_email"],
            login_password=creds["login_password"],
            profile_path=creds.get("profile_path") or "",
            client_id=client_id,
            client_secret=client_secret,
            channel_id=channel.get("platform_channel_id"),
            totp_secret=creds.get("totp_secret"),
            backup_codes=creds.get("backup_codes"),
            proxy=proxy,
            user_agent=creds.get("user_agent"),
            last_success_at=creds.get("last_success_at"),
            last_attempt_at=creds.get("last_attempt_at"),
            enabled=creds.get("enabled", True),
        )

    async def _run_channel(self, channel_id: int, credential: AutomationCredential) -> ReauthResult:
        """Execute the automation flow for a single channel."""
        logger.info("Starting OAuth reauth for channel %s (id=%d)", credential.channel_name, channel_id)

        audit_id = audit_repo.create_reauth_audit(
            channel_id=channel_id,
            status=ReauthStatus.SKIPPED.value,
            initiated_at=datetime.now(timezone.utc),
            trigger_reason="automated_reauth",
            metadata={"stage": "initiated"},
        )

        state = f"{credential.channel_name}_{secrets.token_urlsafe(8)}"

        oauth_config = OAuthConfig(
            client_id=credential.client_id,
            client_secret=credential.client_secret,
            redirect_port=self.config.oauth_settings.redirect_port,
            scopes=self.config.oauth_settings.scopes,
            prompt=self.config.oauth_settings.prompt,
            access_type=self.config.oauth_settings.access_type,
            timeout_seconds=self.config.oauth_settings.timeout_seconds,
        )
        oauth_flow = OAuthFlow(oauth_config)

        try:
            async with playwright_context(credential, self.config.browser) as (_, context):
                page = await context.new_page()
                loop = asyncio.get_running_loop()

                def navigate_to_consent(url: str) -> None:
                    future = asyncio.run_coroutine_threadsafe(
                        prepare_oauth_consent_page(page, credential, self.config.browser, url),
                        loop,
                    )
                    try:
                        future.result(timeout=self.config.oauth_settings.timeout_seconds)
                    except MFAChallengeError:
                        raise
                    except Exception as exc:
                        logger.error("Failed to prepare OAuth consent page: %s", exc)

                result = await loop.run_in_executor(
                    None,
                    oauth_flow.run,
                    credential,
                    state,
                    navigate_to_consent,
                )

                if result.status != ReauthStatus.SUCCESS:
                    screenshot_file = await self._capture_failure_screenshot(
                        page, credential.channel_name
                    )
                    if screenshot_file:
                        if result.metadata is None:
                            result.metadata = {}
                        result.metadata["screenshot_path"] = screenshot_file

        except MFAChallengeError as exc:
            logger.warning("Skipping channel %s due to MFA challenge: %s", credential.channel_name, exc)
            metadata = {}
            if exc.screenshot_path:
                metadata["screenshot_path"] = exc.screenshot_path
            result = ReauthResult(
                channel_name=credential.channel_name,
                status=ReauthStatus.SKIPPED,
                error=str(exc),
                metadata=metadata or None,
            )

        # Persist results to DB
        credential_repo.mark_attempt(
            channel_id,
            success=result.status == ReauthStatus.SUCCESS,
            error_message=result.error,
        )

        audit_status = result.status.value
        if result.status == ReauthStatus.SUCCESS and result.access_token:
            if not result.refresh_token:
                logger.warning(
                    "OAuth succeeded but no refresh_token received for channel %d (%s); "
                    "tokens not saved (will not work after access_token expires)",
                    channel_id, credential.channel_name,
                )
                audit_status = ReauthStatus.FAILED.value
            else:
                channel_repo.update_channel_tokens(
                    channel_id=channel_id,
                    access_token=result.access_token,
                    refresh_token=result.refresh_token,
                    token_expires_at=(
                        datetime.now(timezone.utc) + timedelta(seconds=result.expires_in)
                        if result.expires_in else None
                    ),
                )
                logger.info("Tokens updated for channel %d (%s)", channel_id, credential.channel_name)

        if audit_id is not None:
            error_msg = (
                "Refresh token not received from Google"
                if audit_status == ReauthStatus.FAILED.value and result.status == ReauthStatus.SUCCESS
                else result.error
            )
            audit_repo.complete_reauth_audit(
                audit_id,
                status=audit_status,
                completed_at=datetime.now(timezone.utc),
                error_message=error_msg,
                metadata=result.metadata,
            )

        logger.info(
            "OAuth reauth completed for %s: status=%s",
            credential.channel_name, result.status.value,
        )

        if result.status != ReauthStatus.SUCCESS:
            self._send_error_notification(result)

        return result

    async def run_for_channels(self, channel_ids: Iterable[int]) -> List[ReauthResult]:
        """Run the automation flow for one or more channels sequentially."""
        results: List[ReauthResult] = []
        for channel_id in channel_ids:
            credential = self._load_credential(channel_id)
            if not credential:
                failed = ReauthResult(
                    channel_name=f"channel-{channel_id}",
                    status=ReauthStatus.FAILED,
                    error="Credentials not configured",
                )
                results.append(failed)
                self._send_error_notification(failed)
                continue

            result = await self._run_channel(channel_id, credential)
            results.append(result)
        return results

    def run_sync(self, channel_ids: Iterable[int]) -> List[ReauthResult]:
        """Synchronous wrapper around async execution."""
        return asyncio.run(self.run_for_channels(channel_ids))

    @staticmethod
    async def _capture_failure_screenshot(page, channel_name: str) -> Optional[str]:
        """Take a screenshot after a failure. Returns path or None."""
        screenshot_dir = Path("data/logs/reauth_failures")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = channel_name.replace(" ", "_")
        file_path = screenshot_dir / f"{safe_name}_{timestamp}.png"
        try:
            await page.screenshot(path=str(file_path), full_page=True)
            resolved = str(file_path.resolve())
            logger.info("Failure screenshot saved: %s", resolved)
            return resolved
        except Exception as exc:
            logger.debug("Failed to capture screenshot: %s", exc)
            return None

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
