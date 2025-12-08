"""Playwright helpers for automating the YouTube OAuth login sequence."""

from __future__ import annotations

import asyncio
import json
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
from core.utils.telegram_broadcast import TelegramBroadcast

LOGGER = get_logger(__name__)
NOTIFIER: Optional[NotificationManager] = None
BROADCASTER: Optional[TelegramBroadcast] = None


@dataclass
class BrowserConfig:
    """Configuration options for Playwright browser sessions."""

    headless: bool = False
    slow_mo_ms: int = 50  # Add slight delay between actions by default
    navigation_timeout_ms: int = 60000
    human_delay_range_ms: tuple[int, int] = (500, 1200)  # Increased delays for more human-like behavior


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

    # Build proxy config first
    proxy_config = _build_proxy_settings(credential.proxy)

    # Check if we should use persistent context (real Chrome profile)
    use_persistent_context = False
    user_data_dir = None
    if credential.profile_path:
        profile_path = Path(credential.profile_path)
        if profile_path.exists() and profile_path.is_dir():
            # Check if it looks like a Chrome user data directory
            if (profile_path / "Default").exists() or (profile_path / "Profile 1").exists():
                user_data_dir = str(profile_path)
                use_persistent_context = True
                LOGGER.info("Using real Chrome profile from: %s", user_data_dir)

    # Enhanced browser args to avoid detection
    browser_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-site-isolation-trials",
        "--disable-infobars",
        "--disable-notifications",
        "--disable-popup-blocking",
        "--disable-translate",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--disable-ipc-flooding-protection",
        "--enable-features=NetworkService,NetworkServiceInProcess",
        "--force-color-profile=srgb",
        "--metrics-recording-only",
        "--use-mock-keychain",
        "--no-first-run",
        "--no-default-browser-check",
        "--password-store=basic",
        "--use-mock-keychain",
    ]
    
    if use_persistent_context:
        # Use persistent context with real Chrome profile
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=browser_config.headless,
            slow_mo=browser_config.slow_mo_ms,
            args=browser_args,
            user_agent=credential.user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            proxy=proxy_config,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )
        browser = None  # Not needed for persistent context
    else:
        # Use regular launch
        browser = await playwright.chromium.launch(
            headless=browser_config.headless,
            slow_mo=browser_config.slow_mo_ms,
            args=browser_args,
        )

    storage_state_path: Optional[str] = None
    if credential.profile_path and not use_persistent_context:
        profile_path = Path(credential.profile_path)
        if profile_path.is_dir():
            profile_path.mkdir(parents=True, exist_ok=True)
            storage_state_path = str(profile_path / "state.json")
        else:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            storage_state_path = str(profile_path)

    # Enhanced stealth script to hide automation
    stealth_script = """
    (function() {
        // Override navigator.webdriver - most important
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        
        // Override chrome object
        if (!window.chrome) {
            window.chrome = {};
        }
        window.chrome.runtime = {};
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Override plugins to look real
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [];
                for (let i = 0; i < 5; i++) {
                    plugins.push({
                        0: {type: 'application/x-google-chrome-pdf'},
                        description: 'Portable Document Format',
                        filename: 'internal-pdf-viewer',
                        length: 1,
                        name: 'Chrome PDF Plugin'
                    });
                }
                return plugins;
            },
            configurable: true
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        });
        
        // Remove all automation indicators
        const propsToDelete = [
            'cdc_adoQpoasnfa76pfcZLmcfl_Array',
            'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
            'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
            '__playwright',
            '__pw_manual',
            '__pw_original'
        ];
        propsToDelete.forEach(prop => {
            try {
                delete window[prop];
            } catch (e) {}
        });
        
        // Override getProperty to hide webdriver
        const originalGetProperty = Object.getOwnPropertyDescriptor;
        Object.getOwnPropertyDescriptor = function(obj, prop) {
            if (prop === 'webdriver' && obj === navigator) {
                return undefined;
            }
            return originalGetProperty.apply(this, arguments);
        };
        
        // Make toString methods return normal values
        const originalToString = Function.prototype.toString;
        Function.prototype.toString = function() {
            if (this === navigator.webdriver) {
                return 'function webdriver() { [native code] }';
            }
            return originalToString.apply(this, arguments);
        };
        
        // Override Notification to prevent detection
        const OriginalNotification = window.Notification;
        window.Notification = function(title, options) {
            return new OriginalNotification(title, options);
        };
        Object.setPrototypeOf(window.Notification, OriginalNotification);
        Object.defineProperty(window.Notification, 'permission', {
            get: () => OriginalNotification.permission
        });
        
        // Override document.documentElement.webdriver
        Object.defineProperty(document.documentElement, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        
        // Override window.navigator.webdriver getter
        const originalNavigator = window.navigator;
        Object.defineProperty(window, 'navigator', {
            get: () => {
                const nav = originalNavigator;
                Object.defineProperty(nav, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });
                return nav;
            },
            configurable: true
        });
    })();
    """

    if not use_persistent_context:
        context = await browser.new_context(
            user_agent=credential.user_agent or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            proxy=proxy_config,
            record_video_dir=None,
            base_url="https://accounts.google.com",
            storage_state=storage_state_path if storage_state_path and Path(storage_state_path).exists() else None,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )
        context.set_default_navigation_timeout(browser_config.navigation_timeout_ms)
    
    # Add stealth script to every page
    await context.add_init_script(stealth_script)

    try:
        yield playwright, context
    finally:
        if storage_state_path and not use_persistent_context:
            await context.storage_state(path=storage_state_path)
        await context.close()
        if browser:  # Only close if we created it (not persistent context)
            await browser.close()
        await playwright.stop()
        LOGGER.debug("Playwright shutdown completed for channel %s", credential.channel_name)


async def _log_page_state(
    page: "Page",
    action: str = "checking",
    credential: Optional[AutomationCredential] = None,
) -> None:
    """Log detailed information about current page state for debugging."""
    try:
        url = await page.evaluate("() => window.location.href")
        title = await page.evaluate("() => document.title")
        
        # Get page text (first 1000 chars)
        page_text = await page.evaluate("() => document.body.innerText")
        text_preview = page_text[:500] if len(page_text) > 500 else page_text
        text_length = len(page_text)
        
        # Get visible buttons and clickable elements
        clickable_elements = await page.evaluate("""
() => {
  const elements = [];
  const selectors = ['button', 'a[href]', 'div[role="button"]', '[onclick]', '[jsname]'];
  for (const selector of selectors) {
    document.querySelectorAll(selector).forEach(el => {
      const text = (el.textContent || '').trim();
      const jsname = el.getAttribute('jsname');
      const visible = el.offsetWidth > 0 && el.offsetHeight > 0;
      if (visible && (text || jsname)) {
        elements.push({
          tag: el.tagName.toLowerCase(),
          text: text.substring(0, 50),
          jsname: jsname,
          id: el.id || '',
          className: el.className || ''
        });
      }
    });
  }
  return elements.slice(0, 20); // Limit to first 20
}
""")
        
        channel_name = credential.channel_name if credential else "unknown"
        LOGGER.info(
            "📄 PAGE STATE [%s] for %s:\n"
            "   URL: %s\n"
            "   Title: %s\n"
            "   Text length: %d chars\n"
            "   Text preview: %s\n"
            "   Clickable elements found: %d",
            action.upper(),
            channel_name,
            url,
            title,
            text_length,
            text_preview,
            len(clickable_elements)
        )
        
        if clickable_elements:
            LOGGER.info("   Visible buttons/elements:")
            for elem in clickable_elements[:10]:  # Log first 10
                LOGGER.info(
                    "      - %s%s%s%s",
                    elem['tag'],
                    f" (jsname='{elem['jsname']}')" if elem['jsname'] else "",
                    f" id='{elem['id']}'" if elem['id'] else "",
                    f": '{elem['text']}'" if elem['text'] else ""
                )
    except Exception as exc:
        LOGGER.debug("Failed to log page state: %s", exc)


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
    LOGGER.info("🌐 Navigating to OAuth consent URL for %s: %s", credential.channel_name, url)
    await page.goto(url, wait_until="load")
    LOGGER.info("✅ Page loaded, starting login flow for %s", credential.channel_name)
    await _log_page_state(page, "after navigating to OAuth URL", credential)
    await _complete_login_flow(page, credential, browser_config)


async def _handle_account_chooser_if_present(page: "Page", credential: AutomationCredential) -> bool:
    """Handle Google account chooser screen if shown."""
    LOGGER.info("🔍 Checking for account chooser screen for %s", credential.channel_name)
    email_aliases = {
        credential.login_email.lower(),
        credential.login_email.split("@")[0].lower(),
        credential.channel_name.lower(),
    }

    try:
        account_tiles = page.locator("div[data-identifier]")
        count = await account_tiles.count()
        if count == 0:
            LOGGER.debug("No account chooser tiles found for %s", credential.channel_name)
            return False

        LOGGER.info("🔍 Found %d account tiles, searching for matching account for %s", count, credential.channel_name)
        for idx in range(count):
            tile = account_tiles.nth(idx)
            identifier = (await tile.get_attribute("data-identifier") or "").lower()
            label = (await tile.inner_text()).lower()
            LOGGER.info("   Tile %d: identifier='%s', label='%s'", idx + 1, identifier, label[:50])
            if identifier in email_aliases or any(alias in label for alias in email_aliases):
                LOGGER.info("✅ Found matching account, clicking tile %d for %s", idx + 1, credential.channel_name)
                await tile.click()
                await page.wait_for_timeout(1500)
                return True

        LOGGER.info("⚠️  No matching account found, trying fallback for %s", credential.channel_name)
        chooser_link = page.locator("div[jsname='ksKsZd']").first
        if await chooser_link.count():
            LOGGER.info("🖱️  Clicking 'Use another account' link for %s", credential.channel_name)
            await chooser_link.click()
        else:
            first_tile = account_tiles.first
            if await first_tile.count():
                LOGGER.info("🖱️  Clicking first account tile (fallback) for %s", credential.channel_name)
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
        # Don't notify here - notification will be sent from service.py if auth fails
        LOGGER.info("TOTP challenge encountered for %s - will notify if auth fails", credential.channel_name)
    elif credential.backup_codes:
        LOGGER.warning(
            "Backup codes available for %s; implement code entry when challenges appear.",
            credential.channel_name,
        )
        # Don't notify here - notification will be sent from service.py if auth fails
        LOGGER.info("Backup code challenge detected for %s - will notify if auth fails", credential.channel_name)
    else:
        LOGGER.debug("No MFA data configured for %s", credential.channel_name)
        if security_message:
            await _handle_security_challenge(page, credential, browser_config, security_message)
        else:
            # Don't notify here - notification will be sent from service.py if auth fails
            LOGGER.warning("MFA or security challenge detected for %s but no automation data is configured - will notify if auth fails", credential.channel_name)


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
    # Don't notify here - notification will be sent from service.py if auth fails
    # Screenshot is saved for debugging purposes
    LOGGER.info("Security challenge screenshot saved to %s - will notify if auth fails", file_path.resolve())


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

    # Don't notify for recovery info - it's not critical and doesn't block auth
    # Recovery prompts can be safely ignored and don't prevent successful authorization
    LOGGER.info("Recovery info prompt detected but not critical - continuing without notification")


async def _approve_consent_if_present(
    page: "Page",
    browser_config: BrowserConfig,
    credential: AutomationCredential,
) -> bool:
    """Approve consent screen by selecting scopes and clicking Allow."""
    LOGGER.info("🔍 Checking for consent screen for %s", credential.channel_name)
    await _log_page_state(page, "checking consent screen", credential)
    try:
        surface = _find_consent_surface(page)
        LOGGER.info("✅ Found consent surface for %s", credential.channel_name)
        
        # Log page info for debugging
        page_url = "unknown"
        try:
            page_url = await surface.evaluate("() => window.location.href")
            page_title = await surface.evaluate("() => document.title")
            page_text_sample = await surface.evaluate("() => document.body.innerText.substring(0, 200)")
            LOGGER.info("Page URL: %s, Title: %s, Text sample: %s", page_url, page_title, page_text_sample)
        except Exception as debug_exc:
            LOGGER.debug("Failed to get page debug info: %s", debug_exc)
        
        is_consent = await _is_consent_screen(surface)
        if not is_consent:
            LOGGER.warning("Not recognized as consent screen for %s. URL: %s", credential.channel_name, page_url)
            
            # Strong fallback: If URL contains consent/oauth, force attempt anyway
            url_lower = page_url.lower() if page_url else ""
            if "consent" in url_lower or "oauth" in url_lower:
                LOGGER.info("URL contains 'consent' or 'oauth' - forcing consent screen handling for %s", credential.channel_name)
                try:
                    await _select_all_scopes(surface, browser_config)
                    if await _click_consent_button(surface, browser_config, credential):
                        LOGGER.info("Successfully clicked consent button (URL-based fallback) for %s", credential.channel_name)
                        return True
                except Exception as force_exc:
                    LOGGER.error("Failed to click button via URL fallback: %s", force_exc)
            
            # Try to find the button anyway if we see "ContentFactory" or similar in text
            try:
                page_text_lower = await surface.evaluate("() => document.body.innerText.toLowerCase()")
                if "contentfactory" in page_text_lower or "wants access" in page_text_lower or "google account" in page_text_lower:
                    LOGGER.info("Found consent-related text, attempting to click button anyway for %s", credential.channel_name)
                    # Force attempt to click the button
                    await _select_all_scopes(surface, browser_config)
                    if await _click_consent_button(surface, browser_config, credential):
                        LOGGER.info("Successfully clicked consent button (text-based fallback) for %s", credential.channel_name)
                        return True
            except Exception as force_exc:
                LOGGER.debug("Failed to force click button: %s", force_exc)
            return False

        LOGGER.info("✅ Consent screen detected for %s, selecting scopes...", credential.channel_name)
        await _select_all_scopes(surface, browser_config)
        LOGGER.info("✅ Scopes selected for %s", credential.channel_name)

        LOGGER.info("🖱️  Calling _click_consent_button for %s...", credential.channel_name)
        if await _click_consent_button(surface, browser_config, credential):
            LOGGER.info("✅ Successfully clicked consent button for %s", credential.channel_name)
            return True
    except Exception as exc:
        LOGGER.error("Error in _approve_consent_if_present for %s: %s", credential.channel_name, exc, exc_info=True)
        raise

    # Don't notify here - notification will be sent from service.py if auth fails
    LOGGER.warning("Unable to approve consent automatically for %s - will notify if auth fails", credential.channel_name)
    return False


def _find_consent_surface(page: "Page") -> FrameLike:
    for frame in page.frames:
        url = frame.url or ""
        if "consentsummary" in url or "oauth" in url:
            return frame
    return page


async def _is_consent_screen(surface: FrameLike) -> bool:
    """Check if current page is a Google OAuth consent screen."""
    LOGGER.info("Checking if page is consent screen...")
    
    # First, get full page text for analysis
    try:
        page_text_full = await surface.evaluate("() => document.body.innerText")
        page_text_lower = page_text_full.lower()
        LOGGER.info("Page text (first 500 chars): %s", page_text_full[:500])
        LOGGER.info("Page text length: %d characters", len(page_text_full))
    except Exception as exc:
        LOGGER.warning("Failed to get page text: %s", exc)
        page_text_lower = ""
    
    # Check URL first - if it contains consent/oauth, it's likely a consent screen
    page_url = ""
    try:
        page_url = await surface.evaluate("() => window.location.href")
        url_lower = page_url.lower()
        if "consent" in url_lower or ("oauth" in url_lower and "consent" in url_lower):
            LOGGER.info("URL contains 'consent' or 'oauth' - treating as consent screen: %s", page_url[:200])
            # URL is a strong indicator - return True immediately if URL clearly indicates consent
            if "/consent" in url_lower or "consentsummary" in url_lower:
                LOGGER.info("URL path contains '/consent' - definitely a consent screen")
                return True
    except Exception as url_exc:
        LOGGER.debug("Failed to get page URL: %s", url_exc)
    
    # Try multiple ways to detect consent screen
    consent_indicators_exact = [
        "wants access to your Google Account",
        "хоче отримати доступ до вашого облікового запису Google",
        "хочет получить доступ к вашей учетной записи Google",
        "wants to access your Google Account",
        "ContentFactory wants access",
    ]
    
    # Try exact matches first
    LOGGER.info("Checking exact text matches...")
    counts = []
    for idx, indicator in enumerate(consent_indicators_exact):
        count = await surface.locator(f"text='{indicator}'").count()
        counts.append(count)
        if count > 0:
            LOGGER.info("Found exact match #%d: '%s' (count: %d)", idx, indicator[:50], count)
    
    if any(counts):
        LOGGER.info("Consent screen detected via exact text match")
        return True
    
    # Try partial matches (contains)
    LOGGER.info("Checking partial text matches...")
    consent_indicators_partial = [
        "wants access",
        "access to your Google",
        "Google Account",
        "ContentFactory",
        "consent",
        "разрешить доступ",
        "доступ до облікового запису",
    ]
    
    for indicator in consent_indicators_partial:
        try:
            # Use text= with contains
            locator = surface.locator(f"text=/{indicator}/i")
            count = await locator.count()
            if count > 0:
                LOGGER.info("Consent screen detected via partial match: '%s' (count: %d)", indicator, count)
                return True
        except Exception as exc:
            LOGGER.debug("Error checking partial match '%s': %s", indicator, exc)
            continue
    
    # Try to find consent-related elements by checking page content
    LOGGER.info("Analyzing page text content...")
    try:
        consent_keywords = ["wants access", "google account", "contentfactory", "consent", "разрешить", "доступ"]
        found_keywords = [kw for kw in consent_keywords if kw in page_text_lower]
        if found_keywords:
            LOGGER.info("Consent screen detected via page text analysis. Found keywords: %s", found_keywords)
            return True
        else:
            LOGGER.info("No consent keywords found in page text. Searched for: %s", consent_keywords)
    except Exception as exc:
        LOGGER.warning("Failed to analyze page text: %s", exc)
    
    # Check for common consent screen elements
    try:
        LOGGER.info("Checking for common consent screen elements...")
        # Check for buttons with Continue/Allow text
        continue_buttons = await surface.locator("button, div[role='button']").filter(has_text=re.compile("continue|allow|продолжить|разрешить", re.I)).count()
        if continue_buttons > 0:
            LOGGER.info("Found %d buttons with Continue/Allow text", continue_buttons)
            return True
        
        # Check for checkboxes (scope selection)
        checkboxes = await surface.locator('input[type="checkbox"]').count()
        if checkboxes > 0:
            LOGGER.info("Found %d checkboxes on page", checkboxes)
            # If we have checkboxes and URL has consent, it's likely a consent screen
            if page_url and "consent" in page_url.lower():
                LOGGER.info("URL has 'consent' and page has checkboxes - likely consent screen")
                return True
    except Exception as exc:
        LOGGER.debug("Error checking consent elements: %s", exc)
    
    LOGGER.warning("No consent screen indicators found. Page might not be a consent screen.")
    return False


async def _select_all_scopes(surface: FrameLike, browser_config: BrowserConfig) -> None:
    """Select all scopes by clicking 'Select all' checkbox or individual checkboxes."""
    try:
        LOGGER.info("🔍 Looking for 'Select all' checkbox...")
        # Pause before interacting with checkboxes (humans read first)
        await asyncio.sleep(random.uniform(0.5, 1.2))
        
        # METHOD 1: Try to find checkbox by jsname="YPqjbf" (the actual Select All checkbox)
        try:
            LOGGER.info("🔍 Method 1: Searching for checkbox with jsname='YPqjbf' (Select All)...")
            select_all_checkbox = surface.locator('input[jsname="YPqjbf"]')
            if await select_all_checkbox.count() > 0:
                is_checked = await select_all_checkbox.first.is_checked()
                LOGGER.info("✅ Found Select All checkbox (jsname='YPqjbf'), currently checked: %s", is_checked)
                if not is_checked:
                    LOGGER.info("🖱️  Clicking Select All checkbox (jsname='YPqjbf')...")
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                    await select_all_checkbox.first.click()
                    await _page_from_surface(surface).wait_for_timeout(
                        random.randint(browser_config.human_delay_range_ms[0], browser_config.human_delay_range_ms[1])
                    )
                    LOGGER.info("✅ Successfully clicked Select All checkbox (jsname='YPqjbf')")
                    return
                else:
                    LOGGER.info("✅ Select All checkbox already checked, skipping")
                    return
        except Exception as jsname_exc:
            LOGGER.debug("Method 1 (jsname) failed: %s", jsname_exc)
        
        # METHOD 2: Try to find by text "Select all" and related labels
        select_all_locators = [
            surface.locator("text='Select all'"),
            surface.locator("text='Вибрати все'"),
            surface.locator("text='Выбрать все'"),
        ]
        # Fix: Check counts first, then iterate
        counts = [await locator.count() for locator in select_all_locators]
        if any(counts):
            LOGGER.info("🔍 Method 2: Found 'Select all' text, clicking...")
            for locator in select_all_locators:
                if await locator.count():
                    # Human-like pause before clicking
                    await asyncio.sleep(random.uniform(0.3, 0.7))
                    LOGGER.info("🖱️  Clicking 'Select all' text element...")
                    await locator.first.click()
                    # Longer pause after clicking (humans pause after actions)
                    await _page_from_surface(surface).wait_for_timeout(
                        random.randint(browser_config.human_delay_range_ms[0], browser_config.human_delay_range_ms[1])
                    )
                    LOGGER.info("✅ Successfully clicked 'Select all' text element")
                    return

        # METHOD 3: Fallback - click all unchecked checkboxes individually
        LOGGER.info("🔍 Method 3: Falling back to clicking individual checkboxes...")
        checkboxes = surface.locator('input[type="checkbox"]')
        total = await checkboxes.count()
        LOGGER.info("   Found %d checkboxes total", total)
        for idx in range(total):
            checkbox = checkboxes.nth(idx)
            if not await checkbox.is_checked():
                # Variable pause between checkbox clicks (more human-like)
                await asyncio.sleep(random.uniform(0.15, 0.4))
                LOGGER.info("🖱️  Clicking unchecked checkbox %d/%d", idx + 1, total)
                await checkbox.click()
                # Small pause after each click
                await _page_from_surface(surface).wait_for_timeout(random.randint(80, 200))
        LOGGER.info("✅ Finished clicking individual checkboxes")
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning("⚠️  Unable to toggle consent checkboxes: %s", exc)


async def _simulate_human_activity(page_obj: "Page", browser_config: BrowserConfig) -> None:
    """Simulate human-like activity before clicking to avoid detection."""
    try:
        # More extensive random mouse movements (humans don't keep mouse still)
        num_movements = random.randint(2, 5)
        for _ in range(num_movements):
            x = random.randint(50, 1800)
            y = random.randint(50, 1000)
            # Use more steps for smoother, more human-like movement
            steps = random.randint(10, 25)
            await page_obj.mouse.move(x, y, steps=steps)
            # Variable pause between movements (humans pause randomly)
            await asyncio.sleep(random.uniform(0.15, 0.5))
        
        # Small random scrolls (humans scroll to read)
        num_scrolls = random.randint(1, 3)
        for _ in range(num_scrolls):
            scroll_amount = random.randint(-200, 200)
            await page_obj.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(0.3, 0.7))
        
        # Final pause to simulate reading
        await asyncio.sleep(random.uniform(0.5, 1.5))
    except Exception:
        pass  # Ignore errors in human simulation


async def _click_consent_button(
    surface: FrameLike,
    browser_config: BrowserConfig,
    credential: AutomationCredential,
) -> bool:
    page_obj = _page_from_surface(surface)
    LOGGER.info("🔍 Starting consent button click process for %s", credential.channel_name)
    
    # Wait for page to be fully loaded first
    try:
        await page_obj.wait_for_load_state("networkidle", timeout=15000)
        LOGGER.info("✅ Page loaded (networkidle) for %s", credential.channel_name)
    except Exception:
        try:
            await page_obj.wait_for_load_state("domcontentloaded", timeout=10000)
            LOGGER.info("✅ Page loaded (domcontentloaded) for %s", credential.channel_name)
        except Exception:
            LOGGER.debug("Page load timeout for %s, continuing anyway", credential.channel_name)
            pass
    
    # Important: Wait longer before interacting (humans read the page first)
    initial_pause = random.uniform(2.0, 4.0)
    await page_obj.wait_for_timeout(int(initial_pause * 1000))
    
    # Scroll down slowly to simulate reading
    await _scroll_to_bottom(surface)
    
    # Additional pause after scrolling (humans pause after scrolling)
    await asyncio.sleep(random.uniform(1.0, 2.5))
    
    # Extensive human activity simulation before clicking
    await _simulate_human_activity(page_obj, browser_config)
    
    # Final pause before attempting to click (critical for avoiding detection)
    await asyncio.sleep(random.uniform(0.8, 1.8))
    
    # METHOD 1: Try waiting for selector to appear (Playwright's built-in wait)
    try:
        LOGGER.info("🔍 Method 1: Waiting for element with jsname='V67aGc' to appear for %s...", credential.channel_name)
        await surface.wait_for_selector("div[jsname='V67aGc']", state="visible", timeout=15000)
        button = surface.locator("div[jsname='V67aGc']").first
        LOGGER.info("✅ Found button with jsname='V67aGc' for %s", credential.channel_name)
        await button.scroll_into_view_if_needed()
        
        # Additional pause after scrolling to button (humans read before clicking)
        await asyncio.sleep(random.uniform(0.8, 1.5))
        
        # Use human-like click with mouse movement
        await _human_pause(browser_config)
        LOGGER.info("🖱️  Attempting human-like click on V67aGc button for %s", credential.channel_name)
        if not await _human_like_click(button, page_obj, browser_config):
            # Fallback to regular click if human-like fails (but still with delay)
            LOGGER.info("🖱️  Human-like click failed, trying regular click for %s", credential.channel_name)
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await button.click(timeout=5000, delay=random.randint(100, 200))
        await page_obj.wait_for_timeout(random.randint(2000, 3500))
        LOGGER.info("✅ Successfully clicked Continue button via wait_for_selector for %s.", credential.channel_name)
        return await _handle_consent_click_success(page_obj, credential, "Method 1 (wait_for_selector)")
    except Exception as wait_exc:
        LOGGER.debug("wait_for_selector method failed: %s", wait_exc)
    
    # METHOD 2: Search by text "Continue" and check jsname attribute
    try:
        LOGGER.info("🔍 Method 2: Searching for Continue button by text and jsname for %s...", credential.channel_name)
        button_info = await surface.evaluate("""
() => {
  // Find all elements with text containing "Continue"
  const allElements = Array.from(document.querySelectorAll('*'));
  for (let el of allElements) {
    const text = (el.textContent || '').trim().toLowerCase();
    if (text === 'continue' || text.includes('continue')) {
      // Check if this element or any parent has jsname="V67aGc"
      let current = el;
      while (current && current !== document.body) {
        const jsname = current.getAttribute('jsname');
        if (jsname === 'V67aGc') {
          return {
            element: current,
            tagName: current.tagName,
            text: text
          };
        }
        current = current.parentElement;
      }
    }
  }
  return null;
}
""")
        if button_info:
            element_handle = await surface.evaluate_handle("""
() => {
  const allElements = Array.from(document.querySelectorAll('*'));
  for (let el of allElements) {
    const text = (el.textContent || '').trim().toLowerCase();
    if (text === 'continue' || text.includes('continue')) {
      let current = el;
      while (current && current !== document.body) {
        if (current.getAttribute('jsname') === 'V67aGc') {
          return current;
        }
        current = current.parentElement;
      }
    }
  }
  return null;
}
""")
            if element_handle:
                await surface.evaluate("""
(el) => {
  el.scrollIntoView({ behavior: 'instant', block: 'center' });
  if (el.click) el.click();
}
""", element_handle)
                await page_obj.wait_for_timeout(2000)
                LOGGER.info("✅ Successfully clicked Continue button found by text for %s.", credential.channel_name)
                return await _handle_consent_click_success(page_obj, credential, "Method 2 (text search)")
    except Exception as text_exc:
        LOGGER.debug("Text-based search failed: %s", text_exc)
    
    # METHOD 3: Search in Shadow DOM
    try:
        LOGGER.info("Method 3: Searching in Shadow DOM for %s...", credential.channel_name)
        shadow_result = await surface.evaluate("""
() => {
  function findInShadow(root) {
    let found = null;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
    let node;
    while (node = walker.nextNode()) {
      if (node.shadowRoot) {
        const shadowEl = node.shadowRoot.querySelector('[jsname="V67aGc"]');
        if (shadowEl) {
          found = shadowEl;
          break;
        }
        found = findInShadow(node.shadowRoot);
        if (found) break;
      }
      if (node.getAttribute && node.getAttribute('jsname') === 'V67aGc') {
        found = node;
        break;
      }
    }
    return found;
  }
  return findInShadow(document.body);
}
""")
        if shadow_result:
            # If we found it, we need to click it differently
            LOGGER.info("Found element in Shadow DOM, attempting click for %s.", credential.channel_name)
    except Exception as shadow_exc:
        LOGGER.debug("Shadow DOM search failed: %s", shadow_exc)
    
    # METHOD 4: Find all buttons/clickable elements and check their jsname
    try:
        LOGGER.info("Method 4: Searching all clickable elements for jsname='V67aGc' for %s...", credential.channel_name)
        all_buttons = await surface.evaluate("""
() => {
  const selectors = ['button', 'div[role="button"]', 'a', '[onclick]', '[tabindex]'];
  const candidates = [];
  for (let selector of selectors) {
    const elements = document.querySelectorAll(selector);
    for (let el of elements) {
      const jsname = el.getAttribute('jsname');
      if (jsname === 'V67aGc') {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          candidates.push(el);
        }
      }
      // Also check parent
      let parent = el.parentElement;
      let depth = 0;
      while (parent && depth < 3) {
        if (parent.getAttribute('jsname') === 'V67aGc') {
          const rect = el.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            candidates.push(el);
            break;
          }
        }
        parent = parent.parentElement;
        depth++;
      }
    }
  }
  return candidates.length > 0 ? candidates[0] : null;
}
""")
        if all_buttons:
            element_handle = await surface.evaluate_handle("""
() => {
  const selectors = ['button', 'div[role="button"]', 'a', '[onclick]', '[tabindex]'];
  for (let selector of selectors) {
    const elements = document.querySelectorAll(selector);
    for (let el of elements) {
      if (el.getAttribute('jsname') === 'V67aGc') {
        return el;
      }
      let parent = el.parentElement;
      let depth = 0;
      while (parent && depth < 3) {
        if (parent.getAttribute('jsname') === 'V67aGc') {
          return el;
        }
        parent = parent.parentElement;
        depth++;
      }
    }
  }
  return null;
}
""")
            if element_handle:
                await surface.evaluate("""
(el) => {
  el.scrollIntoView({ behavior: 'instant', block: 'center' });
  if (el.click) el.click();
}
""", element_handle)
                await page_obj.wait_for_timeout(2000)
                LOGGER.info("Successfully clicked Continue button found via clickable elements search for %s.", credential.channel_name)
                return await _handle_consent_click_success(page_obj, credential, "Method 4 (clickable elements)")
    except Exception as buttons_exc:
        LOGGER.debug("Clickable elements search failed: %s", buttons_exc)
    
    # METHOD 5: XPath search
    try:
        LOGGER.info("Method 5: Searching via XPath for %s...", credential.channel_name)
        # Try XPath to find element with jsname="V67aGc"
        xpath_selectors = [
            "//div[@jsname='V67aGc']",
            "//*[@jsname='V67aGc']",
            "//div[contains(@jsname, 'V67aGc')]",
        ]
        for xpath in xpath_selectors:
            try:
                element = surface.locator(f"xpath={xpath}").first
                if await element.count() > 0:
                    is_visible = await element.is_visible()
                    if is_visible:
                        await element.scroll_into_view_if_needed()
                        # Use human-like click
                        await _human_pause(browser_config)
                        element_locator = surface.locator(f"xpath={xpath}").first
                        if not await _human_like_click(element_locator, page_obj, browser_config):
                            await element.click(timeout=5000, delay=random.randint(50, 150))
                        await page_obj.wait_for_timeout(random.randint(1500, 2500))
                        LOGGER.info("Successfully clicked Continue button via XPath for %s.", credential.channel_name)
                        return await _handle_consent_click_success(page_obj, credential, "Method 5 (XPath)")
            except Exception:
                continue
    except Exception as xpath_exc:
        LOGGER.debug("XPath search failed: %s", xpath_exc)
    
    # METHOD 6: Search by text in multiple languages and find parent with jsname
    try:
        LOGGER.info("Method 6: Searching by text in multiple languages for %s...", credential.channel_name)
        continue_texts = ['continue', 'продолжить', 'продовжити', 'allow', 'разрешить', 'дозволити']
        element_handle = await surface.evaluate_handle(f"""
() => {{
  const texts = {json.dumps(continue_texts)};
  const allElements = Array.from(document.querySelectorAll('*'));
  
  for (let el of allElements) {{
    const text = (el.textContent || '').trim().toLowerCase();
    const matches = texts.some(t => text === t || text.includes(t));
    
    if (matches) {{
      // Check element itself
      if (el.getAttribute('jsname') === 'V67aGc') {{
        return el;
      }}
      // Check parents up to 5 levels
      let current = el.parentElement;
      let depth = 0;
      while (current && depth < 5) {{
        if (current.getAttribute('jsname') === 'V67aGc') {{
          // Return the clickable child, not the parent
          return el;
        }}
        current = current.parentElement;
        depth++;
      }}
    }}
  }}
  return null;
}}
""")
        if element_handle:
            clicked = await surface.evaluate("""
(el) => {
  try {
    el.scrollIntoView({ behavior: 'instant', block: 'center' });
    // Try clicking the element or finding the parent with jsname
    let current = el;
    while (current && current !== document.body) {
      if (current.getAttribute('jsname') === 'V67aGc') {
        if (current.click) {
          current.click();
          return true;
        }
      }
      current = current.parentElement;
    }
    // Fallback: click the element itself
    if (el.click) {
      el.click();
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}
""", element_handle)
            if clicked:
                await page_obj.wait_for_timeout(2000)
                LOGGER.info("Successfully clicked Continue button found by multilingual text search for %s.", credential.channel_name)
                return await _handle_consent_click_success(page_obj, credential, "Method 6 (multilingual)")
    except Exception as multi_exc:
        LOGGER.debug("Multilingual text search failed: %s", multi_exc)
    
    # METHOD 7: Comprehensive page dump for debugging
    try:
        LOGGER.info("Method 7: Performing comprehensive page analysis for %s...", credential.channel_name)
        page_analysis = await surface.evaluate("""
() => {
  const analysis = {
    allJsname: [],
    buttons: [],
    continueText: [],
    clickable: []
  };
  
  // Find all jsname attributes
  const allWithJsname = Array.from(document.querySelectorAll('[jsname]'));
  analysis.allJsname = allWithJsname.map(el => ({
    jsname: el.getAttribute('jsname'),
    tag: el.tagName,
    text: (el.textContent || '').trim().substring(0, 50),
    visible: el.offsetWidth > 0 && el.offsetHeight > 0
  })).slice(0, 20);
  
  // Find all buttons
  const buttons = Array.from(document.querySelectorAll('button, div[role="button"], [onclick]'));
  analysis.buttons = buttons.map(el => ({
    text: (el.textContent || '').trim().substring(0, 50),
    jsname: el.getAttribute('jsname'),
    tag: el.tagName
  })).slice(0, 10);
  
  // Find elements with "continue" text
  const allElements = Array.from(document.querySelectorAll('*'));
  for (let el of allElements) {
    const text = (el.textContent || '').trim().toLowerCase();
    if (text.includes('continue') || text.includes('продолжить') || text.includes('продовжити')) {
      analysis.continueText.push({
        text: (el.textContent || '').trim().substring(0, 50),
        tag: el.tagName,
        jsname: el.getAttribute('jsname'),
        parentJsname: el.parentElement ? el.parentElement.getAttribute('jsname') : null
      });
      if (analysis.continueText.length >= 5) break;
    }
  }
  
  return analysis;
}
""")
        LOGGER.info("Page analysis for %s: %d jsname elements, %d buttons, %d continue text elements", 
                  credential.channel_name,
                  len(page_analysis.get('allJsname', [])),
                  len(page_analysis.get('buttons', [])),
                  len(page_analysis.get('continueText', [])))
        LOGGER.debug("Sample jsname elements: %s", page_analysis.get('allJsname', [])[:5])
        LOGGER.debug("Continue text elements: %s", page_analysis.get('continueText', []))
    except Exception as analysis_exc:
        LOGGER.debug("Page analysis failed: %s", analysis_exc)
    
    # METHOD 8: Original retry-based search
    LOGGER.info("Method 8: Retry-based search for Continue button (jsname='V67aGc') for %s...", credential.channel_name)
    
    max_wait_attempts = 10
    for attempt in range(max_wait_attempts):
        try:
            # Debug: Log what elements with jsname we can find
            if attempt == 0:
                debug_info = await surface.evaluate("""
() => {
  const allJsname = Array.from(document.querySelectorAll('[jsname]'));
  return {
    total: allJsname.length,
    names: allJsname.map(el => el.getAttribute('jsname')).slice(0, 10),
    hasV67aGc: !!document.querySelector('div[jsname="V67aGc"]')
  };
}
""")
                LOGGER.info("Debug: Found %d elements with jsname attribute. Has V67aGc: %s. Sample names: %s", 
                          debug_info.get('total', 0), 
                          debug_info.get('hasV67aGc', False),
                          debug_info.get('names', []))
            
            # Try to find the element
            button_handle = await surface.evaluate_handle(
                """
() => {
  // Try multiple selectors
  let element = document.querySelector('div[jsname="V67aGc"]');
  if (!element) {
    element = document.querySelector('[jsname="V67aGc"]');
  }
  if (!element) {
    // Try to find any element with this jsname
    const all = document.querySelectorAll('[jsname]');
    for (let el of all) {
      if (el.getAttribute('jsname') === 'V67aGc') {
        element = el;
        break;
      }
    }
  }
  
  if (element) {
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    return {
      element: element,
      visible: rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden',
      rect: { width: rect.width, height: rect.height, top: rect.top, left: rect.left }
    };
  }
  return null;
}
"""
            )
            
            if button_handle:
                result = await surface.evaluate("(obj) => obj", button_handle)
                if result and result.get('visible'):
                    LOGGER.info("Found visible Continue button (jsname='V67aGc') on attempt %d for %s", attempt + 1, credential.channel_name)
                    # Get the actual element handle
                    element_handle = await surface.evaluate_handle("() => document.querySelector('div[jsname=\"V67aGc\"]') || document.querySelector('[jsname=\"V67aGc\"]')")
                    
                    if element_handle:
                        # Click using JavaScript directly
                        clicked = await surface.evaluate("""
(el) => {
  try {
    el.scrollIntoView({ behavior: 'instant', block: 'center' });
    // Try multiple click methods
    if (typeof el.click === 'function') {
      el.click();
      return true;
    }
    if (el.dispatchEvent) {
      const clickEvent = new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        view: window,
        buttons: 1
      });
      el.dispatchEvent(clickEvent);
      return true;
    }
    // Try mousedown + mouseup
    if (el.dispatchEvent) {
      el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
      el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}
""", element_handle)
                        
                        if clicked:
                            await page_obj.wait_for_timeout(2000)
                            LOGGER.info("Successfully clicked Continue button (jsname='V67aGc') for %s.", credential.channel_name)
                            return await _handle_consent_click_success(page_obj, credential, "Method 8 (retry loop)")
                else:
                    LOGGER.debug("Element found but not visible yet (attempt %d)", attempt + 1)
            
            if attempt < max_wait_attempts - 1:
                await page_obj.wait_for_timeout(1000)
        except Exception as js_exc:
            LOGGER.debug("Attempt %d to find jsname='V67aGc' failed: %s", attempt + 1, js_exc)
            if attempt < max_wait_attempts - 1:
                await page_obj.wait_for_timeout(1000)
    
    LOGGER.warning("Could not find Continue button (jsname='V67aGc') after %d attempts for %s", max_wait_attempts, credential.channel_name)
    
    # Second: Try Playwright locator approach
    try:
        continue_button = surface.locator("div[jsname='V67aGc']")
        count = await continue_button.count()
        if count > 0:
            LOGGER.info("Found Continue button (jsname='V67aGc') via locator for %s, attempting to click.", credential.channel_name)
            await continue_button.first.scroll_into_view_if_needed()
            await page_obj.wait_for_timeout(500)
            
            # Try multiple click strategies
            if await _try_click_strategies(continue_button.first, surface, browser_config):
                LOGGER.info("Successfully clicked Continue button (jsname='V67aGc') for %s.", credential.channel_name)
                return await _handle_consent_click_success(page_obj, credential, "Method 8 (retry loop - JS click)")
            else:
                LOGGER.warning("Continue button (jsname='V67aGc') found but click failed for %s.", credential.channel_name)
    except Exception as exc:
        LOGGER.debug("Locator approach for jsname='V67aGc' failed: %s", exc)
    
    # Third: Try searching in all frames if surface is a page (with retries)
    if hasattr(surface, 'frames'):
        LOGGER.info("Searching for Continue button (jsname='V67aGc') in all frames for %s...", credential.channel_name)
        for frame_attempt in range(3):
            try:
                for frame_idx, frame in enumerate(surface.frames):
                    try:
                        # Debug first frame
                        if frame_attempt == 0 and frame_idx == 0:
                            frame_debug = await frame.evaluate("""
() => {
  const allJsname = Array.from(document.querySelectorAll('[jsname]'));
  return {
    total: allJsname.length,
    hasV67aGc: !!document.querySelector('[jsname="V67aGc"]'),
    url: window.location.href
  };
}
""")
                            LOGGER.info("Frame %d debug: %d jsname elements, has V67aGc: %s, URL: %s", 
                                      frame_idx, frame_debug.get('total', 0), 
                                      frame_debug.get('hasV67aGc', False),
                                      frame_debug.get('url', 'unknown'))
                        
                        element_handle = await frame.evaluate_handle(
                            """
() => {
  let element = document.querySelector('div[jsname="V67aGc"]') || document.querySelector('[jsname="V67aGc"]');
  if (element) {
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
      return element;
    }
  }
  return null;
}
"""
                        )
                        if element_handle:
                            LOGGER.info("Found Continue button (jsname='V67aGc') in frame %d, clicking for %s.", frame_idx, credential.channel_name)
                            clicked = await frame.evaluate("""
(el) => {
  try {
    el.scrollIntoView({ behavior: 'instant', block: 'center' });
    if (typeof el.click === 'function') {
      el.click();
      return true;
    }
    if (el.dispatchEvent) {
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window, buttons: 1 }));
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}
""", element_handle)
                            if clicked:
                                await page_obj.wait_for_timeout(2000)
                                LOGGER.info("Successfully clicked Continue button in frame for %s.", credential.channel_name)
                                return True
                    except Exception as frame_err:
                        LOGGER.debug("Error checking frame %d: %s", frame_idx, frame_err)
                        continue
                
                if frame_attempt < 2:
                    await page_obj.wait_for_timeout(1000)
            except Exception as frame_exc:
                LOGGER.debug("Frame search attempt %d failed: %s", frame_attempt + 1, frame_exc)
                if frame_attempt < 2:
                    await page_obj.wait_for_timeout(1000)
    
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
                return await _handle_consent_click_success(page_obj, credential, "Approve locators")

    # Fallback: search via JS for the Continue button by jsname or text
    try:
        # First try to find by jsname attribute
        button_handle = await surface.evaluate_handle(
            """
() => {
  const byJsname = document.querySelector('div[jsname="V67aGc"]');
  if (byJsname) return byJsname;
  
  const candidates = Array.from(document.querySelectorAll('button, div[role="button"], div[jsname]'));
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
            return await _handle_consent_click_success(page_obj, credential, "JS fallback")
    except Exception as js_exc:  # pragma: no cover - defensive logging
        LOGGER.debug("JS fallback consent click failed: %s", js_exc)

    return False


async def _handle_unverified_app_screen(
    page: "Page",
    browser_config: BrowserConfig,
    credential: AutomationCredential,
) -> bool:
    """Handle 'Google hasn't verified this app' screen by clicking Continue button (V67aGc)."""
    LOGGER.info("🔍 Checking for unverified app screen for %s", credential.channel_name)
    await _log_page_state(page, "checking unverified app screen", credential)
    
    try:
        # Wait for page to be fully loaded
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
        
        # Check if we're on the unverified app screen
        page_text = ""
        try:
            page_text = await page.evaluate("() => document.body.innerText.toLowerCase()")
        except Exception:
            pass
        
        # Look for indicators of unverified app screen
        unverified_indicators = [
            "hasn't verified",
            "hasn't verified this app",
            "google hasn't verified",
            "не проверено",
            "не верифіковано",
            "unverified app",
        ]
        
        is_unverified_screen = any(indicator in page_text for indicator in unverified_indicators)
        
        if not is_unverified_screen:
            # Also check URL
            try:
                url = await page.evaluate("() => window.location.href")
                url_lower = url.lower()
                if "unverified" in url_lower or ("oauth" in url_lower and "warning" in url_lower):
                    is_unverified_screen = True
            except Exception:
                pass
        
        if not is_unverified_screen:
            LOGGER.debug("Not on unverified app screen for %s", credential.channel_name)
            return False
        
        LOGGER.info("Unverified app screen detected for %s, looking for Continue button (V67aGc)...", credential.channel_name)
        
        # Wait a bit for page to fully render
        await page.wait_for_timeout(random.randint(1000, 2000))
        
        # Try to find and click the button with jsname="V67aGc"
        # Use similar logic as _click_consent_button but simplified
        
        # METHOD 1: Direct selector wait
        try:
            LOGGER.info("🔍 Method 1: Waiting for element with jsname='V67aGc' on unverified screen for %s...", credential.channel_name)
            await page.wait_for_selector("div[jsname='V67aGc']", state="visible", timeout=10000)
            button = page.locator("div[jsname='V67aGc']").first
            LOGGER.info("✅ Found button with jsname='V67aGc' for %s", credential.channel_name)
            await button.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            if await _human_like_click(button, page, browser_config):
                await page.wait_for_timeout(random.randint(2000, 3000))
                LOGGER.info("✅ Successfully clicked Continue button (V67aGc) on unverified screen for %s via human-like click", credential.channel_name)
                return True
            else:
                LOGGER.info("🖱️  Attempting regular click on V67aGc button for %s", credential.channel_name)
                await button.click(timeout=5000, delay=random.randint(100, 200))
                await page.wait_for_timeout(random.randint(2000, 3000))
                LOGGER.info("✅ Successfully clicked Continue button (V67aGc) on unverified screen for %s", credential.channel_name)
                return True
        except Exception as wait_exc:
            LOGGER.debug("Method 1 failed for unverified screen: %s", wait_exc)
        
        # METHOD 2: Search by text and check jsname
        try:
            LOGGER.info("🔍 Method 2: Searching for Continue button by text on unverified screen for %s...", credential.channel_name)
            button_handle = await page.evaluate_handle("""
() => {
  const allElements = Array.from(document.querySelectorAll('*'));
  for (let el of allElements) {
    const text = (el.textContent || '').trim().toLowerCase();
    if (text === 'continue' || text.includes('continue') || 
        text === 'продолжить' || text === 'продовжити') {
      let current = el;
      while (current && current !== document.body) {
        if (current.getAttribute('jsname') === 'V67aGc') {
          return current;
        }
        current = current.parentElement;
      }
    }
  }
  return null;
}
""")
            if button_handle:
                await page.evaluate("""
(el) => {
  el.scrollIntoView({ behavior: 'instant', block: 'center' });
  if (el.click) el.click();
}
""", button_handle)
                await page.wait_for_timeout(2000)
                LOGGER.info("✅ Successfully clicked Continue button found by text on unverified screen for %s", credential.channel_name)
                return True
        except Exception as text_exc:
            LOGGER.debug("Method 2 failed for unverified screen: %s", text_exc)
        
        # METHOD 3: Direct JavaScript click
        try:
            LOGGER.info("🔍 Method 3: Trying direct JavaScript click for V67aGc on unverified screen for %s...", credential.channel_name)
            clicked = await page.evaluate("""
() => {
  const button = document.querySelector('div[jsname="V67aGc"]') || 
                 document.querySelector('[jsname="V67aGc"]');
  if (button) {
    button.scrollIntoView({ behavior: 'instant', block: 'center' });
    if (button.click) {
      button.click();
      return true;
    }
    // Try dispatchEvent
    const clickEvent = new MouseEvent('click', {
      bubbles: true,
      cancelable: true,
      view: window
    });
    button.dispatchEvent(clickEvent);
    return true;
  }
  return false;
}
""")
            if clicked:
                await page.wait_for_timeout(2000)
                LOGGER.info("✅ Successfully clicked Continue button via JavaScript on unverified screen for %s", credential.channel_name)
                return True
        except Exception as js_exc:
            LOGGER.debug("Method 3 failed for unverified screen: %s", js_exc)
        
        LOGGER.warning("⚠️  Could not find or click Continue button (V67aGc) on unverified screen for %s", credential.channel_name)
        return False
        
    except Exception as exc:
        LOGGER.error("Error handling unverified app screen for %s: %s", credential.channel_name, exc, exc_info=True)
        return False


async def _handle_consent_click_success(
    page_obj: "Page",
    credential: AutomationCredential,
    method_name: str,
) -> bool:
    """
    Handle successful consent button click by waiting for callback redirect.
    Returns True if redirect detected or if we should proceed anyway.
    """
    LOGGER.info("Consent button clicked successfully via %s for %s, waiting for callback redirect...", 
                method_name, credential.channel_name)
    redirect_detected = await _wait_for_callback_redirect(page_obj, credential)
    if redirect_detected:
        return True
    else:
        LOGGER.warning(
            "Consent button clicked via %s but callback redirect not detected for %s. "
            "Callback server might receive code via other means.",
            method_name, credential.channel_name
        )
        # Still return True as button was clicked - callback server might receive code
        return True


async def _wait_for_callback_redirect(
    page_obj: "Page",
    credential: AutomationCredential,
    timeout_ms: int = 30000,
) -> bool:
    """
    Wait for redirect to OAuth callback URL after consent button click.
    
    The callback URL should be http://localhost:{port}/callback?code=...
    Returns True if redirect to callback URL is detected, False on timeout.
    
    Note: We don't actually need to wait for the redirect in Playwright - the callback
    server will receive the request independently. This function is mainly for logging
    and verification purposes.
    """
    LOGGER.info("Waiting for callback redirect for %s (timeout: %dms)...", credential.channel_name, timeout_ms)
    
    def is_callback_url(url: str) -> bool:
        """Check if URL is the OAuth callback URL with authorization code."""
        if not url:
            return False
        url_lower = url.lower()
        # Check if it's a localhost callback URL
        if "localhost" not in url_lower and "127.0.0.1" not in url_lower:
            return False
        # Check if it contains /callback
        if "/callback" not in url_lower:
            return False
        # Check if it has code parameter
        if "code=" in url_lower:
            return True
        return False
    
    try:
        # First, check current URL immediately (redirect might have already happened)
        current_url = page_obj.url
        if is_callback_url(current_url):
            LOGGER.info("Callback redirect already detected for %s: %s", credential.channel_name, current_url[:100])
            return True
        
        # Check all frames in the page
        try:
            for frame in page_obj.frames:
                frame_url = frame.url
                if is_callback_url(frame_url):
                    LOGGER.info("Callback redirect detected in frame for %s: %s", credential.channel_name, frame_url[:100])
                    return True
        except Exception as frame_exc:
            LOGGER.debug("Error checking frames: %s", frame_exc)
        
        # Try using wait_for_url with glob pattern (more reliable than lambda)
        try:
            # Use glob pattern to match callback URL
            await page_obj.wait_for_url(
                "**/callback?code=*",
                timeout=timeout_ms,
                wait_until="domcontentloaded"
            )
            callback_url = page_obj.url
            LOGGER.info("Callback redirect detected via wait_for_url for %s: %s", credential.channel_name, callback_url[:100])
            return True
        except Exception as nav_exc:
            # Fallback: poll URL periodically
            LOGGER.debug("wait_for_url failed, using polling fallback: %s", nav_exc)
            
            start_time = asyncio.get_event_loop().time()
            check_interval = 0.5  # Check every 500ms
            
            while True:
                # Check if timeout exceeded
                elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                if elapsed_ms >= timeout_ms:
                    current_url = page_obj.url
                    LOGGER.info(
                        "Timeout waiting for callback redirect in Playwright for %s after %dms. "
                        "Current URL: %s. Note: Callback server may still receive the request independently.",
                        credential.channel_name,
                        int(elapsed_ms),
                        current_url[:200] if current_url else "unknown"
                    )
                    # Don't return False - callback server might receive it independently
                    return False
                
                # Check current URL
                try:
                    current_url = page_obj.url
                    if is_callback_url(current_url):
                        LOGGER.info("Callback redirect detected via polling for %s: %s", credential.channel_name, current_url[:100])
                        return True
                    
                    # Also check all frames
                    for frame in page_obj.frames:
                        frame_url = frame.url
                        if is_callback_url(frame_url):
                            LOGGER.info("Callback redirect detected in frame (polling) for %s: %s", credential.channel_name, frame_url[:100])
                            return True
                except Exception as url_exc:
                    LOGGER.debug("Error getting current URL: %s", url_exc)
                
                # Wait before next check
                await asyncio.sleep(check_interval)
                
    except Exception as exc:
        LOGGER.error("Error waiting for callback redirect for %s: %s", credential.channel_name, exc, exc_info=True)
        # Final check before returning False
        try:
            current_url = page_obj.url
            if is_callback_url(current_url):
                LOGGER.info("Callback redirect detected in error handler for %s: %s", credential.channel_name, current_url[:100])
                return True
            
            # Check frames one more time
            for frame in page_obj.frames:
                frame_url = frame.url
                if is_callback_url(frame_url):
                    LOGGER.info("Callback redirect detected in frame (error handler) for %s: %s", credential.channel_name, frame_url[:100])
                    return True
        except Exception:
            pass
        # Don't fail completely - callback server might receive it
        LOGGER.warning("Could not detect callback redirect in Playwright for %s, but callback server may receive it independently", credential.channel_name)
        return False


async def _scroll_to_bottom(surface: FrameLike) -> None:
    try:
        page_obj = _page_from_surface(surface)
        
        # Get page height for smooth scrolling
        page_height = await surface.evaluate("document.body.scrollHeight")
        viewport_height = await surface.evaluate("window.innerHeight")
        
        # Scroll in multiple smaller steps (more human-like than one big scroll)
        scroll_steps = random.randint(3, 6)
        scroll_per_step = (page_height - viewport_height) / scroll_steps
        
        for step in range(scroll_steps):
            scroll_position = scroll_per_step * (step + 1)
            await surface.evaluate(f"window.scrollTo({{ top: {scroll_position}, behavior: 'smooth' }})")
            # Variable pause between scroll steps (humans pause while reading)
            await page_obj.wait_for_timeout(random.randint(200, 500))
        
        # Final small scroll with mouse wheel (humans use mouse wheel)
        await page_obj.mouse.wheel(0, random.randint(300, 800))
        await page_obj.wait_for_timeout(random.randint(300, 600))
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.debug("Unable to scroll consent page: %s", exc)


async def _human_like_click(
    button: "Locator",
    page_obj: "Page",
    browser_config: BrowserConfig,
) -> bool:
    """
    Perform a human-like click with mouse movement, hover, and delays.
    This helps avoid detection by anti-bot systems.
    """
    try:
        # Get element bounding box
        box = await button.bounding_box()
        if not box:
            return False
        
        # Calculate center of element
        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2
        
        # Add larger random offset to make it more human-like (humans don't click exactly center)
        offset_x = random.uniform(-8, 8)
        offset_y = random.uniform(-8, 8)
        target_x = center_x + offset_x
        target_y = center_y + offset_y
        
        # Get current mouse position (if available) for smoother movement
        try:
            # Move mouse away first (humans often move mouse before clicking)
            current_x = random.randint(100, 500)
            current_y = random.randint(100, 400)
            await page_obj.mouse.move(current_x, current_y, steps=random.randint(5, 10))
            await asyncio.sleep(random.uniform(0.2, 0.4))
        except Exception:
            pass
        
        # Move mouse to element with smooth, human-like movement
        # Use more steps for smoother curve
        steps = random.randint(15, 30)
        await page_obj.mouse.move(target_x, target_y, steps=steps)
        
        # Hover for a moment (humans pause before clicking)
        hover_time = random.uniform(0.3, 0.7)
        await asyncio.sleep(hover_time)
        
        # Small micro-movement before click (humans adjust position slightly)
        micro_offset_x = random.uniform(-2, 2)
        micro_offset_y = random.uniform(-2, 2)
        await page_obj.mouse.move(
            target_x + micro_offset_x, 
            target_y + micro_offset_y, 
            steps=random.randint(3, 6)
        )
        await asyncio.sleep(random.uniform(0.1, 0.2))
        
        # Click with variable delay (humans have variable click speed)
        click_delay = random.randint(80, 200)
        await page_obj.mouse.click(target_x, target_y, delay=click_delay)
        
        # Small pause after click (humans don't move instantly after clicking)
        await asyncio.sleep(random.uniform(0.2, 0.4))
        
        return True
    except Exception as exc:
        LOGGER.debug("Human-like click failed: %s", exc)
        return False


async def _try_click_strategies(
    button: "Locator",
    surface: FrameLike,
    browser_config: BrowserConfig,
) -> bool:
    try:
        await button.scroll_into_view_if_needed()
    except Exception:
        pass

    page_obj = _page_from_surface(surface)
    
    # Try human-like click first (most likely to work and avoid detection)
    strategies = ("human_like", "normal", "force", "js", "enter")
    for attempt in strategies:
        try:
            if attempt == "human_like":
                # Use mouse movement and click for more human-like interaction
                if await _human_like_click(button, page_obj, browser_config):
                    await asyncio.sleep(random.uniform(0.2, 0.5))  # Human-like pause after click
                    LOGGER.debug("Consent button clicked using 'human_like' strategy.")
                    return True
            elif attempt == "normal":
                # Add delay before click
                await _human_pause(browser_config)
                await button.click(timeout=browser_config.navigation_timeout_ms, delay=random.randint(50, 150))
            elif attempt == "force":
                await _human_pause(browser_config)
                await button.click(timeout=browser_config.navigation_timeout_ms, force=True, delay=random.randint(50, 150))
            elif attempt == "js":
                # Try hover first, then click
                try:
                    await button.hover(timeout=2000)
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                except Exception:
                    pass
                handle = await button.element_handle()
                if handle:
                    # Use more realistic mouse events
                    await surface.evaluate("""
(el) => {
  // Create realistic mouse events
  const rect = el.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;
  
  const mouseMove = new MouseEvent('mousemove', {
    view: window,
    bubbles: true,
    cancelable: true,
    clientX: x,
    clientY: y
  });
  el.dispatchEvent(mouseMove);
  
  const mouseOver = new MouseEvent('mouseover', {
    view: window,
    bubbles: true,
    cancelable: true,
    clientX: x,
    clientY: y
  });
  el.dispatchEvent(mouseOver);
  
  const mouseDown = new MouseEvent('mousedown', {
    view: window,
    bubbles: true,
    cancelable: true,
    clientX: x,
    clientY: y,
    button: 0
  });
  el.dispatchEvent(mouseDown);
  
  setTimeout(() => {
    const mouseUp = new MouseEvent('mouseup', {
      view: window,
      bubbles: true,
      cancelable: true,
      clientX: x,
      clientY: y,
      button: 0
    });
    el.dispatchEvent(mouseUp);
    
    const clickEvent = new MouseEvent('click', {
      view: window,
      bubbles: true,
      cancelable: true,
      clientX: x,
      clientY: y,
      button: 0
    });
    el.dispatchEvent(clickEvent);
  }, 50);
}
""", handle)
                else:
                    raise RuntimeError("No element handle for JS click")
            elif attempt == "enter":
                # Focus element first
                try:
                    await button.focus(timeout=2000)
                    await asyncio.sleep(random.uniform(0.1, 0.2))
                except Exception:
                    pass
                await _page_from_surface(surface).keyboard.press("Enter")
            
            # Wait a bit after click (human-like)
            await asyncio.sleep(random.uniform(0.2, 0.5))
            await surface.wait_for_load_state("networkidle", timeout=browser_config.navigation_timeout_ms)
            LOGGER.debug("Consent button clicked using '%s' strategy.", attempt)
            return True
        except Exception as exc:
            LOGGER.debug("Consent click strategy '%s' failed: %s", attempt, exc)
            continue
    return False


def _page_from_surface(surface: FrameLike) -> "Page":
    return surface.page if hasattr(surface, "page") else surface  # type: ignore[return-value]


def _notify_manual_intervention(channel_name: str, message: str, critical: bool = True) -> None:
    """
    Send Telegram alert informing operators about required manual action.
    
    Args:
        channel_name: Name of the channel
        message: Message describing the issue
        critical: If False, don't send notification (for non-blocking issues)
    """
    # Skip notification for non-critical issues
    if not critical:
        LOGGER.debug("Skipping notification for non-critical issue: %s", message)
        return
    
    global NOTIFIER, BROADCASTER
    if NOTIFIER is None:
        NOTIFIER = NotificationManager()
    if BROADCASTER is None:
        BROADCASTER = TelegramBroadcast()

    # Escape Markdown special characters
    def escape_markdown(text: str) -> str:
        """Escape Markdown special characters."""
        special_chars = ['*', '_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    safe_channel = escape_markdown(channel_name)
    safe_message = escape_markdown(message)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    alert_message = (
        f"🚨 *Проблема з авторизацією YouTube*\n\n"
        f"*Канал:* {safe_channel}\n"
        f"*Потрібна дія:* {safe_message}\n\n"
        f"⚠️ Потрібен ручний ввід MFA коду або підтвердження\n"
        f"Будь ласка, завершіть верифікацію в браузері автоматизації.\n\n"
        f"_Час: {timestamp}_"
    )
    try:
        # Try broadcast first (like daily_report)
        if BROADCASTER:
            subscribers = BROADCASTER.get_subscribers()
            if not subscribers:
                # If no subscribers - add TELEGRAM_CHAT_ID as subscriber
                telegram_chat_id = NOTIFIER.notification_config.telegram_chat_id
                if telegram_chat_id:
                    try:
                        chat_id_int = int(telegram_chat_id)
                        BROADCASTER.add_subscriber(chat_id_int)
                        LOGGER.info(f"Added TELEGRAM_CHAT_ID {chat_id_int} as subscriber")
                    except (ValueError, TypeError):
                        LOGGER.error(f"Invalid TELEGRAM_CHAT_ID: {telegram_chat_id}")
            
            result = BROADCASTER.broadcast_message(alert_message)
            if result['success'] > 0:
                LOGGER.info(f"MFA notification sent to {result['success']}/{result['total']} subscribers")
                return
        
        # Fallback to single user notification
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
    LOGGER.info("Starting _complete_login_flow for %s", credential.channel_name)
    await _log_page_state(page, "starting login flow", credential)
    max_attempts = 5
    for attempt in range(max_attempts):
        LOGGER.debug("Login flow attempt %d/%d for %s", attempt + 1, max_attempts, credential.channel_name)
        await _log_page_state(page, f"attempt {attempt + 1}", credential)
        try:
            if await _handle_account_chooser_if_present(page, credential):
                LOGGER.info("✅ Handled account chooser for %s", credential.channel_name)
                await _log_page_state(page, "after account chooser", credential)
                continue

            if await _enter_email_if_needed(page, credential, browser_config):
                LOGGER.info("✅ Entered email for %s", credential.channel_name)
                await _log_page_state(page, "after entering email", credential)
                continue

            if await _enter_password_if_needed(page, credential, browser_config):
                LOGGER.info("✅ Entered password for %s", credential.channel_name)
                await _log_page_state(page, "after entering password", credential)
                continue

            LOGGER.debug("Handling MFA and account data prompts for %s", credential.channel_name)
            await _handle_mfa_if_needed(page, credential, browser_config)
            await _handle_account_data_prompt(page, credential, browser_config)
            await _log_page_state(page, "after MFA/account data", credential)
            
            # Handle "Google hasn't verified this app" screen
            if await _handle_unverified_app_screen(page, browser_config, credential):
                LOGGER.info("✅ Unverified app screen handled for %s", credential.channel_name)
                await _log_page_state(page, "after unverified app screen", credential)
                continue
            
            LOGGER.debug("Checking for consent screen for %s", credential.channel_name)
            if await _approve_consent_if_present(page, browser_config, credential):
                LOGGER.info("✅ Consent approved for %s", credential.channel_name)
                await _log_page_state(page, "after consent approval", credential)
                continue
            LOGGER.debug("No further steps needed for %s", credential.channel_name)
            break  # exit loop once no further automated steps are needed
        except Exception as exc:
            LOGGER.error("Error in login flow attempt %d for %s: %s", attempt + 1, credential.channel_name, exc, exc_info=True)
            raise
    LOGGER.info("Completed _complete_login_flow for %s", credential.channel_name)


async def _enter_email_if_needed(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> bool:
    email_field = page.locator('input[type="email"]:visible')
    if not await email_field.count():
        return False

    LOGGER.info("🔍 Found email field, filling for %s", credential.channel_name)
    await email_field.first.fill(credential.login_email, timeout=browser_config.navigation_timeout_ms)
    LOGGER.info("✅ Filled email: %s", credential.login_email)
    await _human_pause(browser_config)
    identifier_button = page.locator("#identifierNext button:visible")
    if await identifier_button.count():
        LOGGER.info("🖱️  Clicking 'Next' button after email for %s", credential.channel_name)
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

    LOGGER.info("🔍 Found password field, filling for %s", credential.channel_name)
    await password_field.first.fill(credential.login_password)
    LOGGER.info("✅ Filled password (hidden)")
    await _human_pause(browser_config)
    password_next = page.locator("#passwordNext button:visible")
    if await password_next.count():
        try:
            LOGGER.info("🖱️  Clicking 'Next' button after password for %s", credential.channel_name)
            await password_next.first.click(timeout=browser_config.navigation_timeout_ms)
        except Exception:
            LOGGER.info("⌨️  Pressing Enter after password for %s", credential.channel_name)
            await page.keyboard.press("Enter")
    else:
        LOGGER.info("⌨️  Pressing Enter after password for %s", credential.channel_name)
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
