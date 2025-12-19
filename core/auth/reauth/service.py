"""Service orchestration for automated YouTube OAuth re-authentication."""

from __future__ import annotations

import asyncio
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable, List, Optional

from core.auth.reauth.models import AutomationCredential, ProxyConfig, ReauthResult, ReauthStatus
from core.auth.reauth.oauth_flow import OAuthConfig, OAuthFlow
from core.auth.reauth.playwright_client import BrowserConfig, playwright_context, prepare_oauth_consent_page
from core.database.mysql_db import YouTubeMySQLDatabase
from core.utils.logger import get_logger
from core.utils.telegram_broadcast import TelegramBroadcast
from core.utils.notifications import NotificationManager

LOGGER = get_logger(__name__)


@dataclass
class OAuthSettings:
    """Shared OAuth settings that are independent of channel credentials."""

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
        db: YouTubeMySQLDatabase,
        service_config: ServiceConfig,
        open_browser: Optional[Callable[[str], None]] = None,
        use_broadcast: bool = True,
    ) -> None:
        self.db = db
        self.config = service_config
        self.open_browser = open_browser or self._default_open_browser
        self.use_broadcast = use_broadcast
        self.broadcaster = TelegramBroadcast() if use_broadcast else None
        self.notifier = NotificationManager(config_path="config/config.yaml")

    @staticmethod
    def _default_open_browser(url: str) -> None:
        """Default no-op open_browser handler; Playwright handles navigation."""
        LOGGER.info("Navigate browser to: %s", url)

    def _load_credential(self, channel_name: str) -> Optional[AutomationCredential]:
        record = self.db.get_account_credentials(channel_name, include_disabled=False)
        if not record:
            LOGGER.error("No automation credentials configured for %s", channel_name)
            return None

        channel = self.db.get_channel(channel_name)
        if not channel:
            LOGGER.error("Channel configuration not found for %s", channel_name)
            return None

        # Get client credentials from google_consoles table via console_name or console_id
        # Fallback to environment variables if no console assigned
        credentials = self.db.get_console_credentials_for_channel(channel_name)
        
        if credentials:
            client_id = credentials['client_id']
            client_secret = credentials['client_secret']
        else:
            # Fallback to environment variables
            client_id = os.getenv('YOUTUBE_MAIN_CLIENT_ID')
            client_secret = os.getenv('YOUTUBE_MAIN_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            LOGGER.error("Missing client credentials for %s (not in google_consoles, not in channel, and not in env vars)", channel_name)
            return None

        proxy = None
        if record.proxy_host and record.proxy_port:
            proxy = ProxyConfig(
                host=record.proxy_host,
                port=record.proxy_port,
                username=record.proxy_username,
                password=record.proxy_password,
            )

        return AutomationCredential(
            channel_name=record.channel_name,
            login_email=record.login_email,
            login_password=record.login_password,
            profile_path=record.profile_path or "",
            client_id=client_id,
            client_secret=client_secret,
            channel_id=channel.channel_id,  # Add channel_id for YouTube channel selection
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
            initiated_at=datetime.now(timezone.utc),
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

        async with playwright_context(credential, self.config.browser) as (_, context):
            page = await context.new_page()

            loop = asyncio.get_running_loop()

            def navigate_to_consent(url: str) -> None:
                LOGGER.debug("Navigating Playwright page to OAuth consent URL: %s", url)
                future = asyncio.run_coroutine_threadsafe(
                    prepare_oauth_consent_page(page, credential, self.config.browser, url),
                    loop,
                )
                try:
                    future.result(timeout=self.config.oauth_settings.timeout_seconds)
                except Exception as exc:
                    LOGGER.error("Failed to prepare OAuth consent page: %s", exc)

            result = await asyncio.get_running_loop().run_in_executor(
                None,
                oauth_flow.run,
                credential,
                state,
                navigate_to_consent,
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
                completed_at=datetime.now(timezone.utc),
                error_message=result.error,
                metadata=result.metadata,
            )

        LOGGER.info(
            "OAuth reauth completed for %s with status %s",
            credential.channel_name,
            result.status.value,
        )
        
        # Send Telegram notification if reauth failed
        if result.status != ReauthStatus.SUCCESS:
            self._send_reauth_error_notification(result)
        
        return result

    async def run_for_channels(self, channel_names: Iterable[str]) -> List[ReauthResult]:
        """Run the automation flow for one or more channels sequentially."""
        results: List[ReauthResult] = []
        for channel_name in channel_names:
            credential = self._load_credential(channel_name)
            if not credential:
                failed_result = ReauthResult(
                    channel_name=channel_name,
                    status=ReauthStatus.FAILED,
                    error="Credentials not configured",
                )
                results.append(failed_result)
                # Send notification about missing credentials
                self._send_reauth_error_notification(failed_result)
                continue

            result = await self._run_channel(credential)
            results.append(result)
        return results

    def run_sync(self, channel_names: Iterable[str]) -> List[ReauthResult]:
        """Synchronous wrapper around async execution."""
        return asyncio.run(self.run_for_channels(channel_names))
    
    def _send_reauth_error_notification(self, result: ReauthResult) -> None:
        """Send Telegram notification about reauth error."""
        try:
            # Check if error is critical before sending notification
            error = result.error or ""
            LOGGER.debug(
                "Checking if error is critical: %s (channel: %s, status: %s)",
                error,
                result.channel_name,
                result.status.value
            )
            
            if not self._is_critical_error(error):
                LOGGER.info(
                    "Skipping notification for non-critical error: %s (channel: %s)",
                    error,
                    result.channel_name
                )
                return
            
            LOGGER.info(
                "Sending notification for critical error: %s (channel: %s)",
                error,
                result.channel_name
            )
            message = self._format_reauth_error_message(result)
            self._send_telegram_message(message)
        except Exception as e:
            LOGGER.error(f"Failed to send reauth error notification: {e}")
    
    def _is_critical_error(self, error: str) -> bool:
        """
        Check if error is critical and requires operator attention.
        
        Returns:
            True if error is critical, False for technical/non-critical errors
        """
        if not error:
            return False
        
        error_lower = error.lower()
        
        # Non-critical technical errors (don't notify)
        non_critical_patterns = [
            "address already in use",
            "errno 48",
            "port already in use",
            "connection refused",
            "network is unreachable",
            "temporary failure",
        ]
        
        for pattern in non_critical_patterns:
            if pattern in error_lower:
                LOGGER.info("Non-critical technical error detected: %s - skipping notification", error)
                return False
        
        # Critical errors (notify)
        critical_patterns = [
            "credentials",
            "mfa",
            "challenge",
            "код",
            "код подтверждения",
            "подтверждения",
            "timeout",
            "consent",
            "button",
            "authorization",
            "token",
            "invalid",
            "expired",
            "revoked",
            "security",
            "verification",
            "верифікація",
            "підтвердження",
            "not configured",
            "not found",
            "missing",
            "failed",
            "error",
        ]
        
        for pattern in critical_patterns:
            if pattern in error_lower:
                LOGGER.debug("Critical pattern '%s' found in error: %s", pattern, error)
                return True
        
        # Default: if we can't determine, assume it's critical (better safe than sorry)
        LOGGER.warning("Error doesn't match known patterns, treating as critical: %s", error)
        return True
    
    def _format_reauth_error_message(self, result: ReauthResult) -> str:
        """Format error message for Telegram notification."""
        channel_name = result.channel_name
        error = result.error or "Unknown error"
        status = result.status.value
        
        # Escape Markdown special characters in user input
        def escape_markdown(text: str) -> str:
            """Escape Markdown special characters."""
            special_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = text.replace(char, f'\\{char}')
            return text
        
        # Escape channel name and error to prevent Markdown parsing issues
        safe_channel = escape_markdown(channel_name)
        safe_error = escape_markdown(error)
        safe_status = escape_markdown(status)
        
        message = f"🚨 *Проблема з авторизацією YouTube*\n\n"
        message += f"*Канал:* {safe_channel}\n"
        message += f"*Статус:* {safe_status}\n"
        message += f"*Помилка:* {safe_error}\n\n"
        
        # Add helpful context based on error type
        if "MFA" in error or "challenge" in error.lower() or "код" in error.lower():
            message += "⚠️ Потрібен ручний ввід MFA коду\n"
        elif "credentials" in error.lower() or "не знайдено" in error.lower():
            message += "⚠️ Перевірте налаштування credentials в базі даних\n"
        elif "timeout" in error.lower():
            message += "⚠️ Перевищено час очікування. Спробуйте знову\n"
        elif "consent" in error.lower() or "button" in error.lower():
            message += "⚠️ Проблема з автоматичним натисканням кнопки Continue\n"
        
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        message += f"\n_Час: {timestamp}_"
        
        return message
    
    def _send_telegram_message(self, message: str) -> bool:
        """
        Send message via Telegram (broadcast or single user).
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if self.use_broadcast and self.broadcaster:
                # Check if there are subscribers
                subscribers = self.broadcaster.get_subscribers()
                
                if not subscribers:
                    # If no subscribers - add TELEGRAM_CHAT_ID as subscriber
                    telegram_chat_id = self.notifier.notification_config.telegram_chat_id
                    if telegram_chat_id:
                        try:
                            chat_id_int = int(telegram_chat_id)
                            self.broadcaster.add_subscriber(chat_id_int)
                            LOGGER.info(f"Added TELEGRAM_CHAT_ID {chat_id_int} as subscriber")
                        except (ValueError, TypeError):
                            LOGGER.error(f"Invalid TELEGRAM_CHAT_ID: {telegram_chat_id}")
                
                # Broadcast to all subscribers
                result = self.broadcaster.broadcast_message(message)
                success = result['success'] > 0
                if success:
                    LOGGER.info(f"Reauth error notification sent to {result['success']}/{result['total']} subscribers")
                return success
            else:
                # Send to single user (fallback method)
                self.notifier._send_telegram_message(message)
                return True
        except Exception as e:
            LOGGER.error(f"Error sending Telegram message: {str(e)}")
            return False


