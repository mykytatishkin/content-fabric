"""Playwright helpers for automating the YouTube OAuth login sequence."""

from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, AsyncIterator, Optional

if TYPE_CHECKING:  # pragma: no cover
    from playwright.async_api import BrowserContext, Page, Playwright  # type: ignore

from core.auth.reauth.models import AutomationCredential, ProxyConfig
from core.utils.logger import get_logger
from core.utils.notifications import NotificationManager

LOGGER = get_logger(__name__)
NOTIFIER: Optional[NotificationManager] = None


@dataclass
class BrowserConfig:
    """Configuration options for Playwright browser sessions."""

    headless: bool = False
    slow_mo_ms: int = 0
    navigation_timeout_ms: int = 60000
    human_delay_range_ms: tuple[int, int] = (300, 750)


def _build_proxy_settings(proxy: Optional[ProxyConfig]) -> Optional[dict]:
    if not proxy:
        return None

    server = f"{proxy.host}:{proxy.port}"
    credentials = {}
    if proxy.username:
        credentials["username"] = proxy.username
    if proxy.password:
        credentials["password"] = proxy.password

    proxy_dict: dict = {"server": server}
    proxy_dict.update(credentials)
    return proxy_dict


@asynccontextmanager
async def playwright_context(
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> AsyncIterator[tuple[Playwright, BrowserContext]]:
    """Initialize Playwright and yield a persistent Chromium context."""
    from playwright.async_api import async_playwright  # type: ignore

    playwright = await async_playwright().start()
    LOGGER.debug("Playwright started for channel %s", credential.channel_name)

    browser = await playwright.chromium.launch(
        headless=browser_config.headless,
        slow_mo=browser_config.slow_mo_ms,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )

    proxy_config = _build_proxy_settings(credential.proxy)

    context = await browser.new_context(
        user_agent=credential.user_agent,
        proxy=proxy_config,
        record_video_dir=None,
        base_url="https://accounts.google.com",
        storage_state=credential.profile_path if credential.profile_path else None,
    )

    context.set_default_navigation_timeout(browser_config.navigation_timeout_ms)

    try:
        yield playwright, context
    finally:
        await context.close()
        await browser.close()
        await playwright.stop()
        LOGGER.debug("Playwright shutdown completed for channel %s", credential.channel_name)


async def _human_pause(browser_config: BrowserConfig) -> None:
    """Introduce a human-like delay."""
    low, high = browser_config.human_delay_range_ms
    await asyncio.sleep(random.uniform(low / 1000.0, high / 1000.0))


async def perform_login(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> None:
    """Automate Google login (email, password, MFA)."""
    await page.goto("https://accounts.google.com/signin/v2/identifier")
    await page.fill('input[type="email"]', credential.login_email, timeout=browser_config.navigation_timeout_ms)
    await _human_pause(browser_config)
    await page.click("#identifierNext button", timeout=browser_config.navigation_timeout_ms)
    await page.wait_for_timeout(1500)

    await page.fill('input[type="password"]', credential.login_password, timeout=browser_config.navigation_timeout_ms)
    await _human_pause(browser_config)
    await page.click("#passwordNext button", timeout=browser_config.navigation_timeout_ms)
    await page.wait_for_timeout(2000)

    await _handle_mfa_if_needed(page, credential, browser_config)


async def _handle_mfa_if_needed(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> None:
    """Handle MFA challenges when secrets or backup codes are available."""
    await page.wait_for_timeout(browser_config.human_delay_range_ms[0])

    if credential.totp_secret:
        LOGGER.warning(
            "TOTP secret present for %s but automated MFA handling is not yet implemented.",
            credential.channel_name,
        )
        _notify_manual_intervention(
            credential.channel_name,
            "TOTP challenge encountered. Manual approval required in browser.",
        )
    elif credential.backup_codes:
        LOGGER.warning(
            "Backup codes available for %s; implement code entry when challenges appear.",
            credential.channel_name,
        )
        _notify_manual_intervention(
            credential.channel_name,
            "Backup code challenge detected. Please enter a code manually.",
        )
    else:
        LOGGER.debug("No MFA data configured for %s", credential.channel_name)
        _notify_manual_intervention(
            credential.channel_name,
            "MFA or security challenge detected but no automation data is configured.",
        )


def _notify_manual_intervention(channel_name: str, message: str) -> None:
    """Send Telegram alert informing operators about required manual action."""
    global NOTIFIER
    if NOTIFIER is None:
        NOTIFIER = NotificationManager()

    alert_message = (
        f"🔐 *YouTube Reauth Requires Attention*\n\n"
        f"*Channel:* {channel_name}\n"
        f"*Action Needed:* {message}\n\n"
        "Please complete the verification in the automation browser session."
    )
    try:
        NOTIFIER.send_system_alert("YouTube OAuth MFA", alert_message)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.error("Failed to dispatch manual intervention alert: %s", exc)

