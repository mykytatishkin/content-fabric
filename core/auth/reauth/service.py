"""Service orchestration for automated YouTube OAuth re-authentication."""

from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, List, Optional

from core.auth.reauth.models import AutomationCredential, ReauthResult, ReauthStatus
from core.auth.reauth.oauth_flow import OAuthConfig, OAuthFlow
from core.auth.reauth.playwright_client import BrowserConfig, perform_login, playwright_context
from core.database.mysql_db import YouTubeMySQLDatabase
from core.utils.logger import get_logger

LOGGER = get_logger(__name__)


@dataclass
class ServiceConfig:
    """High-level configuration for the re-auth service."""

    browser: BrowserConfig = field(default_factory=BrowserConfig)
    oauth: OAuthConfig = field(default_factory=OAuthConfig)
    max_concurrent_sessions: int = 1


class YouTubeReauthService:
    """Coordinates database credentials, Playwright automation, and OAuth exchange."""

    def __init__(
        self,
        db: YouTubeMySQLDatabase,
        service_config: ServiceConfig,
        open_browser: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.db = db
        self.config = service_config
        self.oauth_flow = OAuthFlow(service_config.oauth)
        self.open_browser = open_browser or self._default_open_browser

    @staticmethod
    def _default_open_browser(url: str) -> None:
        """Default no-op open_browser handler; Playwright handles navigation."""
        LOGGER.info("Navigate browser to: %s", url)

    def _load_credential(self, channel_name: str) -> Optional[AutomationCredential]:
        record = self.db.get_account_credentials(channel_name, include_disabled=False)
        if not record:
            LOGGER.error("No automation credentials configured for %s", channel_name)
            return None

        proxy = None
        if record.proxy_host and record.proxy_port:
            proxy = {
                "host": record.proxy_host,
                "port": record.proxy_port,
                "username": record.proxy_username,
                "password": record.proxy_password,
            }

        return AutomationCredential(
            channel_name=record.channel_name,
            login_email=record.login_email,
            login_password=record.login_password,
            profile_path=record.profile_path or "",
            totp_secret=record.totp_secret,
            backup_codes=record.backup_codes,
            proxy=proxy,
            user_agent=record.user_agent,
            last_success_at=record.last_success_at,
            last_attempt_at=record.last_attempt_at,
            enabled=record.enabled,
        )

    async def _run_channel(self, credential: AutomationCredential) -> ReauthResult:
        """Execute the automation flow for a single channel."""
        LOGGER.info("Starting OAuth reauth for channel %s", credential.channel_name)
        audit_id = self.db.create_reauth_audit(
            credential.channel_name,
            status=ReauthStatus.SKIPPED.value,
            initiated_at=datetime.utcnow(),
            metadata={"stage": "initiated"},
        )

        state = f"{credential.channel_name}_{secrets.token_urlsafe(8)}"

        async with playwright_context(credential, self.config.browser) as (_, context):
            page = await context.new_page()
            await perform_login(page, credential, self.config.browser)

            result = await asyncio.get_running_loop().run_in_executor(
                None,
                self.oauth_flow.run,
                credential,
                state,
                self.open_browser,
            )

        self.db.mark_credentials_attempt(
            credential.channel_name,
            success=result.status == ReauthStatus.SUCCESS,
            error_message=result.error,
        )

        if audit_id is not None:
            self.db.complete_reauth_audit(
                audit_id,
                status=result.status.value,
                completed_at=datetime.utcnow(),
                error_message=result.error,
                metadata=result.metadata,
            )

        LOGGER.info(
            "OAuth reauth completed for %s with status %s",
            credential.channel_name,
            result.status.value,
        )
        return result

    async def run_for_channels(self, channel_names: Iterable[str]) -> List[ReauthResult]:
        """Run the automation flow for one or more channels sequentially."""
        results: List[ReauthResult] = []
        for channel_name in channel_names:
            credential = self._load_credential(channel_name)
            if not credential:
                results.append(
                    ReauthResult(
                        channel_name=channel_name,
                        status=ReauthStatus.FAILED,
                        error="Credentials not configured",
                    )
                )
                continue

            result = await self._run_channel(credential)
            results.append(result)
        return results

    def run_sync(self, channel_names: Iterable[str]) -> List[ReauthResult]:
        """Synchronous wrapper around async execution."""
        return asyncio.run(self.run_for_channels(channel_names))


