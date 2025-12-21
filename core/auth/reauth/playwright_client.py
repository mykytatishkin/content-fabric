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
    human_delay_range_ms: tuple[int, int] = (200, 400)  # Reduced delays for faster execution


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
        # Ensure proper cleanup of Playwright resources to prevent memory corruption
        # Close resources in reverse order of creation
        try:
            if storage_state_path and not use_persistent_context:
                try:
                    await context.storage_state(path=storage_state_path)
                except Exception as e:
                    LOGGER.warning(f"Failed to save storage state: {e}")
        except Exception as e:
            LOGGER.warning(f"Error in storage state cleanup: {e}")
        
        try:
            await context.close()
        except Exception as e:
            LOGGER.warning(f"Error closing context: {e}")
        
        try:
            if browser:  # Only close if we created it (not persistent context)
                await browser.close()
        except Exception as e:
            LOGGER.warning(f"Error closing browser: {e}")
        
        try:
            await playwright.stop()
        except Exception as e:
            LOGGER.warning(f"Error stopping Playwright: {e}")
        
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


async def _handle_youtube_channel_chooser_if_present(
    page: "Page",
    credential: AutomationCredential,
    browser_config: BrowserConfig,
) -> bool:
    """Handle YouTube channel/brand account selection screen if shown.
    
    This screen appears when a Google account has multiple YouTube channels.
    The function automatically selects the correct channel based on channel_id or channel_name.
    
    Returns:
        True if channel chooser was detected and handled, False otherwise
    """
    if not credential.channel_id:
        LOGGER.debug("No channel_id in credential for %s, skipping YouTube channel chooser", credential.channel_name)
        return False
    
    LOGGER.info("🔍 Checking for YouTube channel chooser screen for %s (channel_id: %s)", 
                credential.channel_name, credential.channel_id)
    
    try:
        # Wait a bit for the page to load
        await page.wait_for_timeout(1000)
        
        # Check URL for channel selection indicators
        page_url = page.url.lower()
        url_indicators = ['channel', 'brand', 'account', 'select', 'choose']
        is_channel_selection_page = any(indicator in page_url for indicator in url_indicators)
        
        if not is_channel_selection_page:
            # Also check page title and text for channel selection hints
            try:
                page_title = (await page.title() or "").lower()
                page_text = (await page.locator('body').inner_text() or "").lower()
                is_channel_selection_page = (
                    'channel' in page_title or 
                    'channel' in page_text[:500] or
                    'канал' in page_text[:500] or
                    'select' in page_title or
                    'choose' in page_title
                )
            except Exception:
                pass
        
        # Check if we're on a channel selection page
        # Google shows channel selection in various formats:
        # 1. List of channel tiles/cards
        # 2. Radio buttons or selectable items
        # 3. Dropdown or selection menu
        
        # Method 1: Look for channel tiles/cards (common pattern)
        # These usually have channel names or channel IDs in data attributes or text
        channel_selectors = [
            # Common selectors for channel selection
            'div[role="option"]',  # Generic option selector
            'div[data-channel-id]',  # Channel ID in data attribute
            'div[data-value]',  # Value in data attribute
            'li[role="option"]',  # List item option
            'div[jsname]',  # Google's jsname pattern
            'div[aria-label*="channel" i]',  # Aria label with channel
            'div[aria-label*="канал" i]',  # Ukrainian/Russian
        ]
        
        found_channels = False
        selected_channel = False
        
        for selector in channel_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                
                if count > 0:
                    LOGGER.info("🔍 Found %d potential channel elements with selector '%s' for %s", 
                               count, selector, credential.channel_name)
                    found_channels = True
                    
                    # Log all available channels for debugging
                    LOGGER.info("📋 Available channels on selection screen for %s:", credential.channel_name)
                    available_channels = []
                    for idx in range(min(count, 10)):  # Log first 10 channels
                        element = elements.nth(idx)
                        text = (await element.inner_text() or "").strip()
                        data_channel_id = await element.get_attribute("data-channel-id")
                        data_value = await element.get_attribute("data-value")
                        aria_label = await element.get_attribute("aria-label") or ""
                        available_channels.append({
                            'index': idx + 1,
                            'text': text[:100],
                            'data-channel-id': data_channel_id,
                            'data-value': data_value,
                            'aria-label': aria_label[:100]
                        })
                        LOGGER.info("   Channel %d: text='%s', data-channel-id='%s', data-value='%s', aria-label='%s'",
                                   idx + 1, text[:50], data_channel_id, data_value, aria_label[:50])
                    
                    # Try to find the correct channel
                    for idx in range(count):
                        element = elements.nth(idx)
                        
                        # Get text content and attributes
                        text = (await element.inner_text() or "").lower()
                        data_channel_id = await element.get_attribute("data-channel-id")
                        data_value = await element.get_attribute("data-value")
                        aria_label = await element.get_attribute("aria-label") or ""
                        
                        # Normalize channel_id for comparison (remove @ prefix, lowercase)
                        def normalize_id(ch_id: str) -> str:
                            if not ch_id:
                                return ""
                            return ch_id.lstrip('@').lower()
                        
                        target_channel_id = normalize_id(credential.channel_id)
                        target_channel_name = credential.channel_name.lower()
                        
                        # Check if this element matches our channel
                        # Priority: channel_id > custom URL > channel name
                        matches = False
                        match_reason = ""
                        
                        # Method 1: Match by channel_id in data attribute (MOST RELIABLE)
                        if data_channel_id:
                            data_id_normalized = normalize_id(data_channel_id)
                            if data_id_normalized == target_channel_id:
                                matches = True
                                match_reason = f"channel_id in data-channel-id: {data_channel_id}"
                        
                        # Method 2: Match by channel_id in data-value
                        if not matches and data_value:
                            data_value_normalized = normalize_id(data_value)
                            if data_value_normalized == target_channel_id:
                                matches = True
                                match_reason = f"channel_id in data-value: {data_value}"
                        
                        # Method 3: Match by channel_id in text (sometimes shown as UC... or @handle)
                        if not matches and target_channel_id:
                            # Check if channel_id appears in text (could be full ID or part of URL)
                            text_normalized = text.lower()
                            if target_channel_id in text_normalized:
                                # Make sure it's not a partial match (e.g., "UC123" matching "UC1234")
                                # Check if it's a complete match or followed by non-alphanumeric
                                pattern = re.escape(target_channel_id) + r'(?![a-zA-Z0-9])'
                                if re.search(pattern, text_normalized):
                                    matches = True
                                    match_reason = f"channel_id in text: {text[:50]}"
                        
                        # Method 4: Match by channel_id in aria-label
                        if not matches and target_channel_id:
                            aria_normalized = aria_label.lower()
                            if target_channel_id in aria_normalized:
                                matches = True
                                match_reason = f"channel_id in aria-label: {aria_label[:50]}"
                        
                        # Method 5: Match by channel name (LESS RELIABLE - use only if channel_id didn't match)
                        # Only use name matching if we have no channel_id or channel_id matching failed
                        if not matches:
                            # Exact name match is preferred
                            text_stripped = text.strip().lower()
                            aria_stripped = aria_label.strip().lower()
                            
                            # Check for exact match first
                            if target_channel_name == text_stripped or target_channel_name == aria_stripped:
                                matches = True
                                match_reason = f"exact channel_name match: {text[:50]}"
                            # Then check for name as whole word (not substring)
                            elif target_channel_name:
                                # Split into words and check if channel name appears as complete word
                                text_normalized = text.lower()
                                aria_normalized = aria_label.lower()
                                text_words = set(re.findall(r'\b\w+\b', text_normalized))
                                if target_channel_name in text_words:
                                    matches = True
                                    match_reason = f"channel_name as whole word in text: {text[:50]}"
                                elif target_channel_name in aria_normalized:
                                    # Check if it's a whole word in aria-label
                                    aria_words = set(re.findall(r'\b\w+\b', aria_normalized))
                                    if target_channel_name in aria_words:
                                        matches = True
                                        match_reason = f"channel_name as whole word in aria-label: {aria_label[:50]}"
                        
                        if matches:
                            LOGGER.info("✅ Found matching channel element %d for %s: %s", 
                                       idx + 1, credential.channel_name, match_reason)
                            try:
                                # Scroll element into view if needed
                                await element.scroll_into_view_if_needed()
                                await page.wait_for_timeout(300)
                                
                                # Click the channel
                                await element.click(timeout=browser_config.navigation_timeout_ms)
                                LOGGER.info("✅ Clicked channel element %d for %s", idx + 1, credential.channel_name)
                                
                                # Wait for navigation/update
                                await page.wait_for_timeout(1500)
                                selected_channel = True
                                break
                            except Exception as click_exc:
                                LOGGER.warning("Failed to click channel element %d: %s", idx + 1, click_exc)
                                # Try alternative click methods
                                try:
                                    await element.click(force=True)
                                    await page.wait_for_timeout(1500)
                                    selected_channel = True
                                    break
                                except Exception:
                                    pass
                    
                    if selected_channel:
                        break
                        
            except Exception as selector_exc:
                LOGGER.debug("Error with selector '%s': %s", selector, selector_exc)
                continue
        
        # Method 2: Look for "Continue" or "Next" button if channel selection is implicit
        # Sometimes Google auto-selects a channel but shows a confirmation
        if not selected_channel and found_channels:
            LOGGER.error(
                "❌ CRITICAL: Found channel chooser but couldn't match correct channel '%s' (channel_id: %s). "
                "This will likely result in tokens being saved to the wrong channel. "
                "Please check that channel_id is correct in the database.",
                credential.channel_name,
                credential.channel_id
            )
            # DON'T use fallback - let it fail so user knows there's a problem
            # The token verification will catch this and prevent saving to wrong channel
            LOGGER.warning(
                "⚠️  NOT using fallback selection to prevent saving tokens to wrong channel. "
                "OAuth will continue but token verification will fail if wrong channel is selected."
            )
        
        if selected_channel:
            LOGGER.info("✅ Successfully handled YouTube channel chooser for %s", credential.channel_name)
            return True
        elif found_channels:
            LOGGER.warning("⚠️  Found channel chooser but couldn't select correct channel for %s", credential.channel_name)
            return False
        else:
            LOGGER.debug("No YouTube channel chooser found for %s", credential.channel_name)
            return False
            
    except Exception as exc:
        LOGGER.debug("Error checking for YouTube channel chooser for %s: %s", credential.channel_name, exc)
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
                    # Check if Select All is already checked before selecting
                    select_all_checked = await _check_select_all_status(surface, credential)
                    if not select_all_checked:
                        await _select_all_scopes(surface, browser_config, credential)
                    else:
                        LOGGER.info("Select All already checked, skipping selection in fallback")
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
                    # Check if Select All is already checked before selecting
                    select_all_checked = await _check_select_all_status(surface, credential)
                    if not select_all_checked:
                        await _select_all_scopes(surface, browser_config, credential)
                    else:
                        LOGGER.info("Select All already checked, skipping selection in text-based fallback")
                    if await _click_consent_button(surface, browser_config, credential):
                        LOGGER.info("Successfully clicked consent button (text-based fallback) for %s", credential.channel_name)
                        return True
            except Exception as force_exc:
                LOGGER.debug("Failed to force click button: %s", force_exc)
            return False

        LOGGER.info("✅ Consent screen detected for %s, checking Select All checkbox...", credential.channel_name)
        
        # First check if Select All is already checked
        select_all_checked = await _check_select_all_status(surface, credential)
        
        if not select_all_checked:
            LOGGER.info("🔍 Select All checkbox is not checked, clicking it for %s...", credential.channel_name)
            await _select_all_scopes(surface, browser_config, credential)
            LOGGER.info("✅ Scopes selected for %s, immediately clicking Continue...", credential.channel_name)
        else:
            LOGGER.info("✅ Select All checkbox already checked for %s, clicking Continue immediately", credential.channel_name)

        # Immediately click Continue after selecting scopes - no delays, no checks
        LOGGER.info("🖱️  Calling _click_consent_button for %s...", credential.channel_name)
        if await _click_consent_button(surface, browser_config, credential):
            LOGGER.info("✅ Successfully clicked consent button for %s", credential.channel_name)
            
            # Don't check for dialog here - just return success
            # If dialog appears, it will be handled by callback server or next attempt
            # The key is: if checkbox is checked, just click Continue and don't wait for dialog
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


async def _handle_no_access_dialog(
    page: "Page",
    surface: FrameLike,
    browser_config: BrowserConfig,
    credential: AutomationCredential,
) -> bool:
    """Handle 'You did not allow any access' dialog by clicking Cancel/Go back."""
    LOGGER.info("🔍 Checking for 'no access' dialog for %s", credential.channel_name)
    
    try:
        # Wait a bit for dialog to appear (reduced)
        await page.wait_for_timeout(500)
        
        # METHOD 1: Check for dialog by jsname and role attributes (most reliable)
        try:
            # Check for dialog with role="dialog" and aria-modal="true"
            dialog_by_role = page.locator('div[role="dialog"][aria-modal="true"]')
            if await dialog_by_role.count() > 0:
                # Check if it contains the "You did not allow any access" text
                dialog_text = await dialog_by_role.first.inner_text()
                if "did not allow any access" in dialog_text.lower() or "continue without allowing" in dialog_text.lower():
                    LOGGER.info("⚠️  'No access' dialog detected by role attribute for %s", credential.channel_name)
                    has_dialog = True
                else:
                    has_dialog = False
            else:
                has_dialog = False
        except Exception:
            has_dialog = False
        
        # METHOD 2: Check for specific jsname attributes
        if not has_dialog:
            try:
                # Check for button with jsname="K4efff" (Go back button in no-access dialog)
                go_back_button = surface.locator('button[jsname="K4efff"]')
                if await go_back_button.count() > 0:
                    # Verify it's in a dialog context by checking parent
                    parent_dialog = await go_back_button.first.evaluate("""
(el) => {
  let current = el.parentElement;
  let depth = 0;
  while (current && depth < 5) {
    const role = current.getAttribute('role');
    const ariaModal = current.getAttribute('aria-modal');
    if (role === 'dialog' && ariaModal === 'true') {
      const text = current.innerText || '';
      if (text.includes('did not allow') || text.includes('no access')) {
        return true;
      }
    }
    current = current.parentElement;
    depth++;
  }
  return false;
}
""")
                    if parent_dialog:
                        LOGGER.info("⚠️  'No access' dialog detected by jsname='K4efff' button for %s", credential.channel_name)
                        has_dialog = True
            except Exception:
                pass
        
        # METHOD 3: Check for dialog text indicators (fallback)
        if not has_dialog:
            dialog_indicators = [
                "You did not allow any access",
                "did not allow any access",
                "Do you want to continue without allowing",
                "не предоставили доступ",
                "не надали доступ",
            ]
            
            page_text = ""
            try:
                page_text = await page.evaluate("() => document.body.innerText")
            except Exception:
                pass
            
            # Check if dialog is present
            has_dialog = any(indicator.lower() in page_text.lower() for indicator in dialog_indicators)
            
            if not has_dialog:
                # Also check for dialog buttons
                cancel_buttons = [
                    surface.locator("text='Go back'"),
                    surface.locator("text='Cancel'"),
                    surface.locator("button:has-text('Go back')"),
                    surface.locator("button:has-text('Cancel')"),
                ]
                
                for cancel_btn in cancel_buttons:
                    if await cancel_btn.count() > 0:
                        # Check if it's in a dialog context
                        try:
                            # Try to find dialog container
                            dialog_container = await page.evaluate("""
() => {
  const dialogs = document.querySelectorAll('[role="dialog"], .dialog, [class*="dialog"]');
  for (let dialog of dialogs) {
    const text = dialog.innerText || '';
    if (text.includes('did not allow') || text.includes('no access')) {
      return true;
    }
  }
  return false;
}
""")
                            if dialog_container:
                                has_dialog = True
                                break
                        except Exception:
                            pass
        
        if not has_dialog:
            LOGGER.debug("No 'no access' dialog found for %s", credential.channel_name)
            return False
        
        LOGGER.info("⚠️  'No access' dialog detected for %s, clicking Cancel/Go back...", credential.channel_name)
        
        # METHOD 1: Try to find and click by jsname="K4efff" (Go back button in no-access dialog)
        try:
            go_back_by_jsname = surface.locator('button[jsname="K4efff"]')
            if await go_back_by_jsname.count() > 0:
                LOGGER.info("🖱️  Clicking 'Go back' button (jsname='K4efff') in no-access dialog for %s", credential.channel_name)
                await go_back_by_jsname.first.click(timeout=5000)
                await page.wait_for_timeout(1000)
                LOGGER.info("✅ Successfully clicked 'Go back' (jsname='K4efff') in no-access dialog for %s", credential.channel_name)
                return True
        except Exception as exc:
            LOGGER.debug("Failed to click by jsname='K4efff': %s", exc)
        
        # METHOD 2: Try to find and click Cancel/Go back button by text
        cancel_texts = ["Go back", "Cancel", "Назад", "Скасувати"]
        for cancel_text in cancel_texts:
            try:
                cancel_button = surface.locator(f"text='{cancel_text}'").first
                if await cancel_button.count() > 0:
                    # Verify it's in the no-access dialog
                    is_in_dialog = await cancel_button.first.evaluate("""
(el) => {
  let current = el.parentElement;
  let depth = 0;
  while (current && depth < 5) {
    const role = current.getAttribute('role');
    const text = current.innerText || '';
    if (role === 'dialog' && (text.includes('did not allow') || text.includes('no access'))) {
      return true;
    }
    current = current.parentElement;
    depth++;
  }
  return false;
}
""")
                    if is_in_dialog:
                        LOGGER.info("🖱️  Clicking '%s' button in no-access dialog for %s", cancel_text, credential.channel_name)
                        await cancel_button.click(timeout=5000)
                        await page.wait_for_timeout(1000)
                        LOGGER.info("✅ Successfully clicked '%s' in no-access dialog for %s", cancel_text, credential.channel_name)
                        return True
            except Exception as exc:
                LOGGER.debug("Failed to click '%s': %s", cancel_text, exc)
        
        # METHOD 3: Fallback - try to find by button role or common selectors
        try:
            go_back_button = surface.locator("button:has-text('Go back')").first
            if await go_back_button.count() > 0:
                LOGGER.info("🖱️  Clicking 'Go back' button (fallback) for %s", credential.channel_name)
                await go_back_button.click(timeout=5000)
                await page.wait_for_timeout(1500)
                return True
        except Exception as exc:
            LOGGER.debug("Fallback Go back click failed: %s", exc)
        
        LOGGER.warning("⚠️  Found 'no access' dialog but couldn't click Cancel/Go back for %s", credential.channel_name)
        return False
        
    except Exception as exc:
        LOGGER.debug("Error checking for no-access dialog: %s", exc)
        return False


async def _check_select_all_status(
    surface: FrameLike,
    credential: AutomationCredential,
) -> bool:
    """Check if Select All checkbox (jsname='YPqjbf' or class='VfPpkd-muHVFf-bMcfAe') is already checked."""
    try:
        # METHOD 1: Check by jsname='YPqjbf'
        select_all_checkbox = surface.locator('input[jsname="YPqjbf"]')
        if await select_all_checkbox.count() > 0:
            is_checked = await select_all_checkbox.first.is_checked()
            LOGGER.info("🔍 Select All checkbox (jsname='YPqjbf') status for %s: %s", 
                       credential.channel_name, "checked" if is_checked else "unchecked")
            return is_checked
        
        # METHOD 2: Check by class='VfPpkd-muHVFf-bMcfAe'
        select_all_by_class = surface.locator('input.VfPpkd-muHVFf-bMcfAe[type="checkbox"]')
        if await select_all_by_class.count() > 0:
            is_checked = await select_all_by_class.first.is_checked()
            LOGGER.info("🔍 Select All checkbox (class='VfPpkd-muHVFf-bMcfAe') status for %s: %s", 
                       credential.channel_name, "checked" if is_checked else "unchecked")
            return is_checked
        
        # METHOD 3: Check by combination of jsname and class
        select_all_combined = surface.locator('input[jsname="YPqjbf"].VfPpkd-muHVFf-bMcfAe[type="checkbox"]')
        if await select_all_combined.count() > 0:
            is_checked = await select_all_combined.first.is_checked()
            LOGGER.info("🔍 Select All checkbox (jsname='YPqjbf' + class='VfPpkd-muHVFf-bMcfAe') status for %s: %s", 
                       credential.channel_name, "checked" if is_checked else "unchecked")
            return is_checked
        
        LOGGER.debug("Select All checkbox not found (tried jsname='YPqjbf' and class='VfPpkd-muHVFf-bMcfAe') for %s", credential.channel_name)
        return False
    except Exception as exc:
        LOGGER.debug("Error checking Select All status: %s", exc)
        return False


async def _verify_all_checkboxes_checked(
    surface: FrameLike,
    credential: AutomationCredential,
) -> None:
    """Verify that all checkboxes are checked after selecting all."""
    try:
        checkboxes = surface.locator('input[type="checkbox"]')
        total = await checkboxes.count()
        unchecked_count = 0
        for idx in range(total):
            checkbox = checkboxes.nth(idx)
            if not await checkbox.is_checked():
                unchecked_count += 1
        
        if unchecked_count > 0:
            LOGGER.warning("⚠️  Found %d unchecked checkboxes out of %d total for %s", unchecked_count, total, credential.channel_name)
        else:
            LOGGER.info("✅ All %d checkboxes are checked for %s", total, credential.channel_name)
    except Exception as exc:
        LOGGER.debug("Error verifying checkboxes: %s", exc)


async def _select_all_scopes(surface: FrameLike, browser_config: BrowserConfig, credential: Optional[AutomationCredential] = None) -> None:
    """Select all scopes by clicking 'Select all' checkbox or individual checkboxes."""
    try:
        LOGGER.info("🔍 Looking for 'Select all' checkbox...")
        
        # FIRST: Check if Select All is already checked - if yes, skip everything
        # This check should ALWAYS happen, even if credential is None (we'll use a dummy check)
        select_all_checked = False
        if credential:
            select_all_checked = await _check_select_all_status(surface, credential)
        else:
            # Even without credential, try to check status to avoid double-clicking
            try:
                select_all_checkbox = surface.locator('input[jsname="YPqjbf"]')
                if await select_all_checkbox.count() == 0:
                    select_all_checkbox = surface.locator('input.VfPpkd-muHVFf-bMcfAe[type="checkbox"]')
                if await select_all_checkbox.count() > 0:
                    select_all_checked = await select_all_checkbox.first.is_checked()
            except Exception:
                pass  # If check fails, continue with selection
        
        if select_all_checked:
            channel_name = credential.channel_name if credential else "unknown"
            LOGGER.info("✅ Select All checkbox already checked for %s, skipping _select_all_scopes", channel_name)
            return
        
        # Pause before interacting with checkboxes (reduced)
        await asyncio.sleep(random.uniform(0.2, 0.4))
        
        # METHOD 1: Try to find checkbox by jsname="YPqjbf" or class="VfPpkd-muHVFf-bMcfAe" (the actual Select All checkbox)
        try:
            LOGGER.info("🔍 Method 1: Searching for checkbox with jsname='YPqjbf' or class='VfPpkd-muHVFf-bMcfAe' (Select All)...")
            # Try jsname first
            select_all_checkbox = surface.locator('input[jsname="YPqjbf"]')
            if await select_all_checkbox.count() == 0:
                # Fallback to class
                select_all_checkbox = surface.locator('input.VfPpkd-muHVFf-bMcfAe[type="checkbox"]')
            if await select_all_checkbox.count() == 0:
                # Try combination
                select_all_checkbox = surface.locator('input[jsname="YPqjbf"].VfPpkd-muHVFf-bMcfAe[type="checkbox"]')
            
            if await select_all_checkbox.count() > 0:
                is_checked = await select_all_checkbox.first.is_checked()
                channel_name = credential.channel_name if credential else "unknown"
                LOGGER.info("✅ Found Select All checkbox for %s, currently checked: %s", channel_name, is_checked)
                if not is_checked:
                    # CRITICAL: Double-check state right before clicking to avoid double-click
                    # Sometimes state can change between checks
                    await asyncio.sleep(random.uniform(0.1, 0.2))
                    is_checked_before_click = await select_all_checkbox.first.is_checked()
                    if is_checked_before_click:
                        LOGGER.info("✅ Select All checkbox became checked before click, skipping click to avoid unchecking")
                        if credential:
                            await _verify_all_checkboxes_checked(surface, credential)
                        return
                    
                    LOGGER.info("🖱️  Clicking Select All checkbox...")
                    await asyncio.sleep(random.uniform(0.1, 0.2))
                    await select_all_checkbox.first.click()
                    # Minimal wait for DOM to update - just enough for checkbox state to change
                    await _page_from_surface(surface).wait_for_timeout(300)
                    
                    # Quick verification that checkbox is checked (non-blocking)
                    is_checked_after = await select_all_checkbox.first.is_checked()
                    LOGGER.info("✅ Clicked Select All checkbox, now checked: %s", is_checked_after)
                    
                    # Return immediately - Continue will be clicked right after, no delays
                    return
                else:
                    channel_name = credential.channel_name if credential else "unknown"
                    LOGGER.info("✅ Select All checkbox already checked for %s, skipping", channel_name)
                    # Still verify to make sure all checkboxes are checked
                    if credential:
                        await _verify_all_checkboxes_checked(surface, credential)
                    return
        except Exception as jsname_exc:
            LOGGER.debug("Method 1 (jsname/class) failed: %s", jsname_exc)
        
        # METHOD 2: Try to find by text "Select all" and related labels
        # BUT: First check if checkbox is already checked to avoid double-clicking
        if credential:
            select_all_checked = await _check_select_all_status(surface, credential)
            if select_all_checked:
                LOGGER.info("✅ Select All checkbox already checked for %s, skipping Method 2", credential.channel_name)
                return
        
        select_all_locators = [
            surface.locator("text='Select all'"),
            surface.locator("text='Вибрати все'"),
            surface.locator("text='Выбрать все'"),
        ]
        # Fix: Check counts first, then iterate
        counts = [await locator.count() for locator in select_all_locators]
        if any(counts):
            # Double-check status before clicking (in case it changed)
            if credential:
                select_all_checked = await _check_select_all_status(surface, credential)
                if select_all_checked:
                    LOGGER.info("✅ Select All checkbox already checked for %s, skipping Method 2 click", credential.channel_name)
                    return
            
            LOGGER.info("🔍 Method 2: Found 'Select all' text, clicking...")
            for locator in select_all_locators:
                if await locator.count():
                    # CRITICAL: Final check before clicking to avoid double-click
                    if credential:
                        select_all_checked_final = await _check_select_all_status(surface, credential)
                        if select_all_checked_final:
                            LOGGER.info("✅ Select All checkbox already checked for %s, skipping Method 2 click to avoid unchecking", credential.channel_name)
                            return
                    
                    # Minimal pause before clicking
                    await asyncio.sleep(random.uniform(0.1, 0.2))
                    LOGGER.info("🖱️  Clicking 'Select all' text element...")
                    await locator.first.click()
                    # Minimal wait for DOM to update
                    await _page_from_surface(surface).wait_for_timeout(300)
                    LOGGER.info("✅ Successfully clicked 'Select all' text element")
                    # Return immediately - Continue will be clicked right after
                    return

        # METHOD 3: Fallback - click all unchecked checkboxes individually
        # BUT: Only if Select All checkbox is not available or not working
        # First check if Select All checkbox exists and is checked
        try:
            # Try jsname first
            select_all_checkbox = surface.locator('input[jsname="YPqjbf"]')
            if await select_all_checkbox.count() == 0:
                # Fallback to class
                select_all_checkbox = surface.locator('input.VfPpkd-muHVFf-bMcfAe[type="checkbox"]')
            if await select_all_checkbox.count() == 0:
                # Try combination
                select_all_checkbox = surface.locator('input[jsname="YPqjbf"].VfPpkd-muHVFf-bMcfAe[type="checkbox"]')
            
            if await select_all_checkbox.count() > 0:
                is_checked = await select_all_checkbox.first.is_checked()
                if is_checked:
                    channel_name = credential.channel_name if credential else "unknown"
                    LOGGER.info("✅ Select All checkbox is checked for %s, skipping individual checkbox clicks", channel_name)
                    if credential:
                        await _verify_all_checkboxes_checked(surface, credential)
                    return
        except Exception:
            pass
        
        LOGGER.info("🔍 Method 3: Falling back to clicking individual checkboxes...")
        checkboxes = surface.locator('input[type="checkbox"]')
        total = await checkboxes.count()
        LOGGER.info("   Found %d checkboxes total", total)
        
        # Only click checkboxes that are NOT the Select All checkbox (jsname='YPqjbf' or class='VfPpkd-muHVFf-bMcfAe')
        for idx in range(total):
            checkbox = checkboxes.nth(idx)
            try:
                # Skip the Select All checkbox itself
                jsname = await checkbox.get_attribute('jsname')
                class_attr = await checkbox.get_attribute('class')
                if jsname == 'YPqjbf' or (class_attr and 'VfPpkd-muHVFf-bMcfAe' in class_attr):
                    LOGGER.debug("Skipping Select All checkbox in individual click loop")
                    continue
            except Exception:
                pass
            
            if not await checkbox.is_checked():
                # Variable pause between checkbox clicks (reduced)
                await asyncio.sleep(random.uniform(0.05, 0.15))
                LOGGER.info("🖱️  Clicking unchecked checkbox %d/%d", idx + 1, total)
                await checkbox.click()
                # Small pause after each click (reduced)
                await _page_from_surface(surface).wait_for_timeout(random.randint(50, 100))
        LOGGER.info("✅ Finished clicking individual checkboxes")
        if credential:
            await _verify_all_checkboxes_checked(surface, credential)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.warning("⚠️  Unable to toggle consent checkboxes: %s", exc)


async def _simulate_human_activity(page_obj: "Page", browser_config: BrowserConfig) -> None:
    """Simulate human-like activity before clicking to avoid detection."""
    try:
        # Reduced random mouse movements
        num_movements = random.randint(1, 2)
        for _ in range(num_movements):
            x = random.randint(50, 1800)
            y = random.randint(50, 1000)
            # Use fewer steps for faster movement
            steps = random.randint(5, 10)
            await page_obj.mouse.move(x, y, steps=steps)
            # Variable pause between movements (reduced)
            await asyncio.sleep(random.uniform(0.05, 0.15))
        
        # Small random scrolls (reduced)
        num_scrolls = random.randint(0, 1)
        for _ in range(num_scrolls):
            scroll_amount = random.randint(-100, 100)
            await page_obj.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(0.1, 0.2))
        
        # Final pause to simulate reading (reduced)
        await asyncio.sleep(random.uniform(0.2, 0.4))
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
    
    # Wait before interacting (reduced delay)
    initial_pause = random.uniform(0.5, 1.0)
    await page_obj.wait_for_timeout(int(initial_pause * 1000))
    
    # Scroll down slowly to simulate reading
    await _scroll_to_bottom(surface)
    
    # Additional pause after scrolling (reduced)
    await asyncio.sleep(random.uniform(0.3, 0.6))
    
    # Reduced human activity simulation before clicking
    await _simulate_human_activity(page_obj, browser_config)
    
    # Final pause before attempting to click (reduced)
    await asyncio.sleep(random.uniform(0.3, 0.6))
    
    # METHOD 1: Try waiting for the SPECIFIC Continue button (not Cancel)
    # Priority: id="submit_approve_access" > button with jsname="LgbsSe" inside submit_approve_access > button with jsname="V67aGc" inside submit_approve_access
    try:
        LOGGER.info("🔍 Method 1: Looking for Continue button with id='submit_approve_access' for %s...", credential.channel_name)
        
        # First try: Look for button inside element with id="submit_approve_access" (most specific)
        submit_approve = surface.locator("#submit_approve_access button[jsname='LgbsSe']")
        if await submit_approve.count() > 0:
            button = submit_approve.first
            LOGGER.info("✅ Found Continue button via id='submit_approve_access' + button[jsname='LgbsSe'] for %s", credential.channel_name)
        else:
            # Second try: Look for span with jsname="V67aGc" inside submit_approve_access
            submit_approve_span = surface.locator("#submit_approve_access span[jsname='V67aGc']")
            if await submit_approve_span.count() > 0:
                # Get the button parent
                button = submit_approve_span.locator("xpath=ancestor::button").first
                if await button.count() == 0:
                    button = submit_approve_span.locator("xpath=ancestor::div[@role='button']").first
                LOGGER.info("✅ Found Continue button via id='submit_approve_access' + span[jsname='V67aGc'] for %s", credential.channel_name)
            else:
                # Third try: Look for any button inside submit_approve_access
                submit_approve_any = surface.locator("#submit_approve_access button")
                if await submit_approve_any.count() > 0:
                    button = submit_approve_any.first
                    LOGGER.info("✅ Found Continue button via id='submit_approve_access' + button for %s", credential.channel_name)
                else:
                    # Fallback: Wait for the element with id to appear, then find button inside
                    await surface.wait_for_selector("#submit_approve_access", state="visible", timeout=15000)
                    button = surface.locator("#submit_approve_access button").first
                    LOGGER.info("✅ Found Continue button via id='submit_approve_access' (fallback) for %s", credential.channel_name)
        
        await button.scroll_into_view_if_needed()
        
        # Additional pause after scrolling to button (reduced)
        await asyncio.sleep(random.uniform(0.3, 0.5))
        
        # Use human-like click with mouse movement
        await _human_pause(browser_config)
        LOGGER.info("🖱️  Attempting human-like click on Continue button (submit_approve_access) for %s", credential.channel_name)
        if not await _human_like_click(button, page_obj, browser_config):
            # Fallback to regular click if human-like fails (but still with delay)
            LOGGER.info("🖱️  Human-like click failed, trying regular click for %s", credential.channel_name)
            await asyncio.sleep(random.uniform(0.1, 0.2))
            await button.click(timeout=5000, delay=random.randint(50, 100))
        await page_obj.wait_for_timeout(random.randint(1000, 1500))
        LOGGER.info("✅ Successfully clicked Continue button via submit_approve_access for %s.", credential.channel_name)
        
        # Don't check for dialog here - let _approve_consent_if_present handle it
        # Checking here causes issues and unnecessary delays
        
        return await _handle_consent_click_success(page_obj, credential, "Method 1 (submit_approve_access)")
    except Exception as wait_exc:
        LOGGER.debug("Method 1 (submit_approve_access) failed: %s", wait_exc)
        
        # Fallback: Try the old method with jsname="V67aGc" but verify it's not Cancel
        try:
            LOGGER.info("🔍 Method 1 (fallback): Waiting for element with jsname='V67aGc' to appear for %s...", credential.channel_name)
            await surface.wait_for_selector("div[jsname='V67aGc'], span[jsname='V67aGc']", state="visible", timeout=15000)
            
            # Find all elements with jsname="V67aGc" and filter to find Continue (not Cancel)
            all_v67agc = surface.locator("[jsname='V67aGc']")
            count = await all_v67agc.count()
            LOGGER.info("Found %d elements with jsname='V67aGc' for %s", count, credential.channel_name)
            
            button = None
            for i in range(count):
                element = all_v67agc.nth(i)
                # Check if this element is inside submit_approve_access or has Continue-like text
                is_continue = await element.evaluate("""
                (el) => {
                    // Check if inside submit_approve_access
                    let current = el;
                    while (current && current !== document.body) {
                        if (current.id === 'submit_approve_access') {
                            return true;
                        }
                        current = current.parentElement;
                    }
                    // Check text content (Continue, Продовжити, etc.)
                    const text = (el.textContent || '').trim().toLowerCase();
                    const continueTexts = ['continue', 'продовжити', 'continuar', 'fortfahren', 'continuer'];
                    return continueTexts.some(ct => text.includes(ct));
                }
                """)
                
                if is_continue:
                    # Get the clickable parent (button or div with role="button")
                    button = element.locator("xpath=ancestor::button | ancestor::div[@role='button']").first
                    if await button.count() == 0:
                        button = element
                    LOGGER.info("✅ Found Continue button (filtered from %d candidates) for %s", count, credential.channel_name)
                    break
            
            if button is None or await button.count() == 0:
                # Last resort: use first one
                button = all_v67agc.first
                LOGGER.warning("⚠️  Using first V67aGc element as fallback for %s (may be Cancel button!)", credential.channel_name)
            
            await button.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.3, 0.5))
            await _human_pause(browser_config)
            LOGGER.info("🖱️  Attempting human-like click on V67aGc button (fallback) for %s", credential.channel_name)
            if not await _human_like_click(button, page_obj, browser_config):
                await asyncio.sleep(random.uniform(0.1, 0.2))
                await button.click(timeout=5000, delay=random.randint(50, 100))
            await page_obj.wait_for_timeout(random.randint(1000, 1500))
            LOGGER.info("✅ Successfully clicked Continue button via V67aGc (fallback) for %s.", credential.channel_name)
            return await _handle_consent_click_success(page_obj, credential, "Method 1 (V67aGc fallback)")
        except Exception as fallback_exc:
            LOGGER.debug("Method 1 fallback (V67aGc) also failed: %s", fallback_exc)
    
    # METHOD 2: Search by text "Continue" and verify it's inside submit_approve_access
    try:
        LOGGER.info("🔍 Method 2: Searching for Continue button by text and submit_approve_access for %s...", credential.channel_name)
        button_info = await surface.evaluate("""
() => {
  // Find all elements with text containing "Continue" (in multiple languages)
  const continueTexts = ['continue', 'продовжити', 'continuar', 'fortfahren', 'continuer', '続ける', '继续'];
  const allElements = Array.from(document.querySelectorAll('*'));
  for (let el of allElements) {
    const text = (el.textContent || '').trim().toLowerCase();
    const isContinueText = continueTexts.some(ct => text === ct || text.includes(ct));
    
    if (isContinueText) {
      // Check if this element is inside submit_approve_access (most reliable)
      let current = el;
      while (current && current !== document.body) {
        if (current.id === 'submit_approve_access') {
          // Found it! Now find the clickable button/span
          let clickable = el;
          while (clickable && clickable !== document.body) {
            const jsname = clickable.getAttribute('jsname');
            if (jsname === 'V67aGc' || jsname === 'LgbsSe' || clickable.tagName === 'BUTTON') {
              return {
                element: clickable,
                tagName: clickable.tagName,
                text: text,
                insideSubmitApprove: true
              };
            }
            clickable = clickable.parentElement;
          }
          // If no specific jsname found, return the element itself
          return {
            element: el,
            tagName: el.tagName,
            text: text,
            insideSubmitApprove: true
          };
        }
        // Also check for jsname="V67aGc" as fallback
        const jsname = current.getAttribute('jsname');
        if (jsname === 'V67aGc') {
          return {
            element: current,
            tagName: current.tagName,
            text: text,
            insideSubmitApprove: false
          };
        }
        current = current.parentElement;
      }
    }
  }
  return null;
}
""")
        if button_info and button_info.get('insideSubmitApprove'):
            # Prefer elements inside submit_approve_access
            element_handle = await surface.evaluate_handle("""
() => {
  const continueTexts = ['continue', 'продовжити', 'continuar', 'fortfahren', 'continuer', '続ける', '继续'];
  const allElements = Array.from(document.querySelectorAll('*'));
  for (let el of allElements) {
    const text = (el.textContent || '').trim().toLowerCase();
    const isContinueText = continueTexts.some(ct => text === ct || text.includes(ct));
    
    if (isContinueText) {
      let current = el;
      while (current && current !== document.body) {
        if (current.id === 'submit_approve_access') {
          // Find the clickable element (button or span with jsname)
          let clickable = el;
          while (clickable && clickable !== document.body) {
            const jsname = clickable.getAttribute('jsname');
            if (jsname === 'V67aGc' || jsname === 'LgbsSe' || clickable.tagName === 'BUTTON') {
              return clickable;
            }
            clickable = clickable.parentElement;
          }
          return el;
        }
        current = current.parentElement;
      }
    }
  }
  return null;
}
""")
        elif button_info:
            # Fallback: use old method but verify it's not Cancel
            element_handle = await surface.evaluate_handle("""
() => {
  const continueTexts = ['continue', 'продовжити', 'continuar', 'fortfahren', 'continuer', '続ける', '继续'];
  const allElements = Array.from(document.querySelectorAll('*'));
  for (let el of allElements) {
    const text = (el.textContent || '').trim().toLowerCase();
    const isContinueText = continueTexts.some(ct => text === ct || text.includes(ct));
    
    if (isContinueText) {
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
                
                # Don't check for dialog here - let _approve_consent_if_present handle it
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
            
            # First priority: Try to find submit_approve_access
            submit_approve = surface.locator("#submit_approve_access")
            if await submit_approve.count() > 0:
                button_inside = submit_approve.locator("button[jsname='LgbsSe'], button, span[jsname='V67aGc']").first
                if await button_inside.count() > 0:
                    button_handle = await button_inside.evaluate_handle("(el) => el")
                    if button_handle:
                        LOGGER.info("Found Continue button via submit_approve_access on attempt %d for %s", attempt + 1, credential.channel_name)
                        clicked = await surface.evaluate("""
(el) => {
  try {
    el.scrollIntoView({ behavior: 'instant', block: 'center' });
    if (el.click) {
      el.click();
      return true;
    }
    return false;
  } catch (e) {
    return false;
  }
}
""", button_handle)
                        if clicked:
                            await page_obj.wait_for_timeout(random.randint(1000, 1500))
                            LOGGER.info("Successfully clicked Continue button (submit_approve_access) for %s.", credential.channel_name)
                            return await _handle_consent_click_success(page_obj, credential, "Method 8 (submit_approve_access)")
            
            # Try to find the element (fallback to V67aGc but verify it's Continue)
            button_handle = await surface.evaluate_handle(
                """
() => {
  // First try: Look for submit_approve_access
  const submitApprove = document.getElementById('submit_approve_access');
  if (submitApprove) {
    const button = submitApprove.querySelector('button[jsname="LgbsSe"]') || 
                   submitApprove.querySelector('button') ||
                   submitApprove.querySelector('span[jsname="V67aGc"]');
    if (button) {
      const rect = button.getBoundingClientRect();
      const style = window.getComputedStyle(button);
      return {
        element: button,
        visible: rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden',
        rect: { width: rect.width, height: rect.height, top: rect.top, left: rect.left }
      };
    }
  }
  
  // Fallback: Try multiple selectors for V67aGc but verify it's Continue
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
  
  // Verify it's Continue (not Cancel) - check if inside submit_approve_access or has Continue text
  if (element) {
    let current = element;
    let isInsideSubmitApprove = false;
    while (current && current !== document.body) {
      if (current.id === 'submit_approve_access') {
        isInsideSubmitApprove = true;
        break;
      }
      current = current.parentElement;
    }
    
    // Check text content
    const text = (element.textContent || '').trim().toLowerCase();
    const continueTexts = ['continue', 'продовжити', 'continuar', 'fortfahren', 'continuer'];
    const isContinueText = continueTexts.some(ct => text.includes(ct));
    
    // Only return if it's inside submit_approve_access or has Continue text
    if (isInsideSubmitApprove || isContinueText) {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return {
        element: element,
        visible: rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden',
        rect: { width: rect.width, height: rect.height, top: rect.top, left: rect.left }
      };
    }
  }
  
  return null;
}
"""
            )
            
            if button_handle:
                result = await surface.evaluate("(obj) => obj", button_handle)
                if result and result.get('visible'):
                    LOGGER.info("Found visible Continue button on attempt %d for %s", attempt + 1, credential.channel_name)
                    # Get the actual element handle - try submit_approve_access first
                    element_handle = None
                    try:
                        # First try: get from submit_approve_access
                        submit_approve = surface.locator("#submit_approve_access")
                        if await submit_approve.count() > 0:
                            button_inside = submit_approve.locator("button[jsname='LgbsSe'], button, span[jsname='V67aGc']").first
                            if await button_inside.count() > 0:
                                element_handle = await button_inside.evaluate_handle("(el) => el")
                    except:
                        pass
                    
                    # Fallback: get by V67aGc but verify it's Continue
                    if not element_handle:
                        element_handle = await surface.evaluate_handle("""
() => {
  // First try submit_approve_access
  const submitApprove = document.getElementById('submit_approve_access');
  if (submitApprove) {
    const btn = submitApprove.querySelector('button[jsname="LgbsSe"]') || 
                submitApprove.querySelector('button') ||
                submitApprove.querySelector('span[jsname="V67aGc"]');
    if (btn) return btn;
  }
  
  // Fallback: V67aGc but verify it's Continue
  let el = document.querySelector('[jsname="V67aGc"]');
  if (el) {
    let current = el;
    while (current && current !== document.body) {
      if (current.id === 'submit_approve_access') return el;
      current = current.parentElement;
    }
    const text = (el.textContent || '').trim().toLowerCase();
    const continueTexts = ['continue', 'продовжити', 'continuar', 'fortfahren', 'continuer'];
    if (continueTexts.some(ct => text.includes(ct))) return el;
  }
  return null;
}
""")
                    
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
        
        # Wait a bit for page to fully render (reduced)
        await page.wait_for_timeout(random.randint(500, 1000))
        
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
                await page.wait_for_timeout(random.randint(1000, 1500))
                LOGGER.info("✅ Successfully clicked Continue button (V67aGc) on unverified screen for %s via human-like click", credential.channel_name)
                return True
            else:
                LOGGER.info("🖱️  Attempting regular click on V67aGc button for %s", credential.channel_name)
                await button.click(timeout=5000, delay=random.randint(50, 100))
                await page.wait_for_timeout(random.randint(1000, 1500))
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
                await page.wait_for_timeout(1000)
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
                await page.wait_for_timeout(1000)
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
            
            # Handle YouTube channel chooser if multiple channels exist on the account
            if await _handle_youtube_channel_chooser_if_present(page, credential, browser_config):
                LOGGER.info("✅ Handled YouTube channel chooser for %s", credential.channel_name)
                await _log_page_state(page, "after YouTube channel chooser", credential)
                continue
            
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
