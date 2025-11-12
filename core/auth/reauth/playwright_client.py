"""Playwright helpers for automating the YouTube OAuth login sequence."""

from __future__ import annotations

import asyncio
import random
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, AsyncIterator, Optional, Union

if TYPE_CHECKING:  # pragma: no cover
    from playwright.async_api import BrowserContext, Frame, Locator, Page, Playwright  # type: ignore

FrameLike = Union["Page", "Frame"]

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

    storage_state_path: Optional[str] = None
    if credential.profile_path:
        profile_path = Path(credential.profile_path)
        if profile_path.is_dir():
            profile_path.mkdir(parents=True, exist_ok=True)
            storage_state_path = str(profile_path / "state.json")
        else:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            storage_state_path = str(profile_path)

    context = await browser.new_context(
        user_agent=credential.user_agent,
        proxy=proxy_config,
        record_video_dir=None,
        base_url="https://accounts.google.com",
        storage_state=storage_state_path if storage_state_path and Path(storage_state_path).exists() else None,
    )

    context.set_default_navigation_timeout(browser_config.navigation_timeout_ms)

    try:
        yield playwright, context
    finally:
        if storage_state_path:
            await context.storage_state(path=storage_state_path)
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
    await _complete_login_flow(page, credential, browser_config)

async def prepare_oauth_consent_page(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
    url: str,
) -> None:
    """Navigate to consent URL and ensure we're past login prompts."""
    await page.goto(url, wait_until="load")
    await _complete_login_flow(page, credential, browser_config)


async def _handle_account_chooser_if_present(page: "Page", credential: AutomationCredential) -> bool:
    """Handle Google account chooser screen if shown."""
    email_aliases = {
        credential.login_email.lower(),
        credential.login_email.split("@")[0].lower(),
        credential.channel_name.lower(),
    }

    try:
        account_tiles = page.locator("div[data-identifier]")
        count = await account_tiles.count()
        if count == 0:
            return False

        for idx in range(count):
            tile = account_tiles.nth(idx)
            identifier = (await tile.get_attribute("data-identifier") or "").lower()
            label = (await tile.inner_text()).lower()
            if identifier in email_aliases or any(alias in label for alias in email_aliases):
                await tile.click()
                await page.wait_for_timeout(1500)
                return True

        chooser_link = page.locator("div[jsname='ksKsZd']").first
        if await chooser_link.count():
            await chooser_link.click()
        else:
            first_tile = account_tiles.first
            if await first_tile.count():
                await first_tile.click()
                await page.wait_for_timeout(1500)
                return True
    except Exception as exc:
        LOGGER.debug("Account chooser handling skipped: %s", exc)
    return False


async def _handle_mfa_if_needed(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> None:
    """Handle MFA challenges when secrets or backup codes are available."""
    await page.wait_for_timeout(browser_config.human_delay_range_ms[0])

    security_message: Optional[str] = None
    mfa_selectors = [
        ("input[name='idvPin']", "Google запрашивает код подтверждения. Введите код вручную."),
        ("input[name='totpPin']", "Google запрашивает TOTP код. Введите данные вручную."),
        ("input[type='tel']", "Google запрашивает код подтверждения на телефон. Введите его вручную."),
    ]
    mfa_texts = [
        "Підтвердьте свою особу",
        "Подтвердите свою личность",
        "Verify it's you",
    ]

    security_message = await _detect_security_prompt(page, mfa_selectors, mfa_texts)

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
        if security_message:
            await _handle_security_challenge(page, credential, browser_config, security_message)
        else:
            _notify_manual_intervention(
                credential.channel_name,
                "MFA or security challenge detected but no automation data is configured.",
            )


async def _handle_security_challenge(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
    security_message: str,
) -> None:
    await _click_more_ways_if_available(page, browser_config)

    screenshot_path = Path("data/logs/mfa")
    screenshot_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = screenshot_path / f"{credential.channel_name.replace(' ', '_')}_{timestamp}.png"
    try:
        await page.screenshot(path=str(file_path), full_page=True)
    except Exception as exc:
        LOGGER.debug("Failed to capture MFA screenshot: %s", exc)

    LOGGER.warning(
        "Security challenge detected for %s: %s",
        credential.channel_name,
        security_message,
    )
    _notify_manual_intervention(
        credential.channel_name,
        f"{security_message}\n\nСсылка на скрин: {file_path.resolve()}",
    )


async def _handle_account_data_prompt(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> None:
    """Dismiss account recovery prompts that offer 'Skip' button."""
    try:
        labels = ("Пропустити", "Пропустить", "Skip", "Продовжити", "Continue")
        for label in labels:
            locator = page.locator(f"text='{label}'").first
            if await locator.count():
                await locator.click()
                await page.wait_for_timeout(browser_config.human_delay_range_ms[0])
                LOGGER.info("Skipped account recovery prompt via '%s'.", label)
                return
        # fallback for bold-like buttons
        skip_locator = page.locator("button", has_text="Skip").first
        if await skip_locator.count():
            await skip_locator.click()
            await page.wait_for_timeout(browser_config.human_delay_range_ms[0])
            LOGGER.info("Skipped account recovery prompt via button Skip.")
            return
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.debug("Unable to auto-dismiss account data prompt: %s", exc)

    # notify if we couldn't skip
    _notify_manual_intervention(
        credential.channel_name,
        "Google is asking to add recovery info. Please respond manually.",
    )


async def _approve_consent_if_present(
    page: "Page",
    browser_config: BrowserConfig,
    credential: AutomationCredential,
) -> bool:
    """Approve consent screen by selecting scopes and clicking Allow."""
    surface = _find_consent_surface(page)
    if not await _is_consent_screen(surface):
        return False

    await _select_all_scopes(surface, browser_config)

    if await _click_consent_button(surface, browser_config, credential):
        return True

    _notify_manual_intervention(
        credential.channel_name,
        "Unable to approve consent automatically. Please click Allow manually.",
    )
    return False


def _find_consent_surface(page: "Page") -> FrameLike:
    for frame in page.frames:
        url = frame.url or ""
        if "consentsummary" in url or "oauth" in url:
            return frame
    return page


async def _is_consent_screen(surface: FrameLike) -> bool:
    consent_indicators = [
        "wants access to your Google Account",
        "хоче отримати доступ до вашого облікового запису Google",
        "хочет получить доступ к вашей учетной записи Google",
    ]
    return any(await surface.locator(f"text='{indicator}'").count() for indicator in consent_indicators)


async def _select_all_scopes(surface: FrameLike, browser_config: BrowserConfig) -> None:
    try:
        select_all_locators = [
            surface.locator("text='Select all'"),
            surface.locator("text='Вибрати все'"),
            surface.locator("text='Выбрать все'"),
        ]
        if any(await locator.count() for locator in select_all_locators):
            for locator in select_all_locators:
                if await locator.count():
                    await locator.first.click()
                    await _page_from_surface(surface).wait_for_timeout(browser_config.human_delay_range_ms[0])
                    break

        checkboxes = surface.locator('input[type="checkbox"]')
        total = await checkboxes.count()
        for idx in range(total):
            checkbox = checkboxes.nth(idx)
            if not await checkbox.is_checked():
                await checkbox.click()
                await _page_from_surface(surface).wait_for_timeout(100)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.debug("Unable to toggle consent checkboxes: %s", exc)


async def _click_consent_button(
    surface: FrameLike,
    browser_config: BrowserConfig,
    credential: AutomationCredential,
) -> bool:
    await _scroll_to_bottom(surface)
    approve_locators = [
        surface.locator("#submit_approve_access"),
        surface.get_by_role("button", name=re.compile("Continue", re.I)),
        surface.get_by_role("button", name=re.compile("Allow", re.I)),
        surface.locator("button:has-text('Allow')"),
        surface.locator("button:has-text('Continue')"),
        surface.locator("button:has-text('Продовжити')"),
        surface.locator("button:has-text('Продовжить')"),
        surface.locator("div[role='button']:has-text('Allow')"),
        surface.locator("div[role='button']:has-text('Continue')"),
        surface.locator("div[role='button']:has-text('Продовжити')"),
        surface.locator("div[role='button']:has-text('Продовжить')"),
    ]

    for locator in approve_locators:
        if await locator.count():
            button = locator.first
            if await _try_click_strategies(button, surface, browser_config):
                LOGGER.info("Consent approved automatically for %s.", credential.channel_name)
                return True

    # Fallback: search via JS for any button-like element containing text
    try:
        button_handle = await surface.evaluate_handle(
            """
() => {
  const candidates = Array.from(document.querySelectorAll('button, div[role="button"]'));
  return candidates.find(el => {
    const text = el.innerText.trim().toLowerCase();
    return text === 'continue' || text === 'allow' ||
           text === 'продовжити' || text === 'продовжить';
  }) || null;
}
"""
        )
        if button_handle:
            await surface.evaluate("(el) => el.click()", button_handle)
            await surface.wait_for_load_state("networkidle", timeout=browser_config.navigation_timeout_ms)
            LOGGER.info("Consent approved via JS fallback for %s.", credential.channel_name)
            return True
    except Exception as js_exc:  # pragma: no cover - defensive logging
        LOGGER.debug("JS fallback consent click failed: %s", js_exc)

    return False


async def _scroll_to_bottom(surface: FrameLike) -> None:
    try:
        await surface.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page_obj = _page_from_surface(surface)
        await page_obj.wait_for_timeout(300)
        await page_obj.mouse.wheel(0, 2000)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.debug("Unable to scroll consent page: %s", exc)


async def _try_click_strategies(
    button: "Locator",
    surface: FrameLike,
    browser_config: BrowserConfig,
) -> bool:
    try:
        await button.scroll_into_view_if_needed()
    except Exception:
        pass

    strategies = ("normal", "force", "js", "enter")
    for attempt in strategies:
        try:
            if attempt == "normal":
                await button.click(timeout=browser_config.navigation_timeout_ms)
            elif attempt == "force":
                await button.click(timeout=browser_config.navigation_timeout_ms, force=True)
            elif attempt == "js":
                handle = await button.element_handle()
                if handle:
                    await surface.evaluate("(el) => el.click()", handle)
                else:
                    raise RuntimeError("No element handle for JS click")
            elif attempt == "enter":
                await _page_from_surface(surface).keyboard.press("Enter")
            await surface.wait_for_load_state("networkidle", timeout=browser_config.navigation_timeout_ms)
            LOGGER.debug("Consent button clicked using '%s' strategy.", attempt)
            return True
        except Exception as exc:
            LOGGER.debug("Consent click strategy '%s' failed: %s", attempt, exc)
            continue
    return False


def _page_from_surface(surface: FrameLike) -> "Page":
    return surface.page if hasattr(surface, "page") else surface  # type: ignore[return-value]


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


async def _detect_security_prompt(
    page: "Page",
    selectors: list[tuple[str, str]],
    texts: list[str],
) -> Optional[str]:
    for selector, message in selectors:
        if await page.locator(selector).count():
            return message
    for text in texts:
        if await page.locator(f"text='{text}'").count():
            return "Google запрашивает подтверждение личности на странице авторизации."
    return None


async def _complete_login_flow(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> None:
    """Iteratively handle Google login prompts."""
    max_attempts = 5
    for _ in range(max_attempts):
        if await _handle_account_chooser_if_present(page, credential):
            continue

        if await _enter_email_if_needed(page, credential, browser_config):
            continue

        if await _enter_password_if_needed(page, credential, browser_config):
            continue

        await _handle_mfa_if_needed(page, credential, browser_config)
        await _handle_account_data_prompt(page, credential, browser_config)
        if await _approve_consent_if_present(page, browser_config, credential):
            continue
        break  # exit loop once no further automated steps are needed


async def _enter_email_if_needed(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> bool:
    email_field = page.locator('input[type="email"]:visible')
    if not await email_field.count():
        return False

    await email_field.first.fill(credential.login_email, timeout=browser_config.navigation_timeout_ms)
    await _human_pause(browser_config)
    identifier_button = page.locator("#identifierNext button:visible")
    if await identifier_button.count():
        await identifier_button.first.click(timeout=browser_config.navigation_timeout_ms)
    await page.wait_for_timeout(1500)
    return True


async def _enter_password_if_needed(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> bool:
    password_field = page.locator('input[type="password"]:visible')
    if not await password_field.count():
        return False

    await password_field.first.fill(credential.login_password)
    await _human_pause(browser_config)
    password_next = page.locator("#passwordNext button:visible")
    if await password_next.count():
        try:
            await password_next.first.click(timeout=browser_config.navigation_timeout_ms)
        except Exception:
            await page.keyboard.press("Enter")
    else:
        await page.keyboard.press("Enter")
    try:
        await page.wait_for_load_state("networkidle", timeout=browser_config.navigation_timeout_ms)
    except Exception:
        await page.wait_for_timeout(2000)
    return True


async def _click_more_ways_if_available(
    page: "Page",
    browser_config: BrowserConfig,
) -> None:
    """Click 'More ways' link on security verification prompts if present."""
    more_links = (
        page.locator("text='More ways to verify'"),
        page.locator("text='Інші способи підтвердження'"),
        page.locator("text='Другие способы подтверждения'"),
    )
    for locator in more_links:
        if await locator.count():
            try:
                await locator.first.click()
                await page.wait_for_timeout(browser_config.human_delay_range_ms[0])
                LOGGER.info("Clicked alternative verification link during MFA challenge.")
                return
            except Exception as exc:
                LOGGER.debug("Failed to click alternative verification link: %s", exc)
