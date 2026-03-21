"""Automated Google OAuth login via Selenium + undetected-chromedriver.

Navigates the Google sign-in flow (email → password → optional TOTP → consent)
then waits for the OAuth redirect back to localhost so InstalledAppFlow can
capture the authorization code.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyotp

logger = logging.getLogger(__name__)

SCREENSHOT_DIR = Path("data/logs/reauth_failures")

_HUMAN_DELAY = 1.5  # seconds between major steps to mimic human pacing


def run_automated_oauth(
    auth_url: str,
    login_email: str,
    login_password: str,
    totp_secret: Optional[str] = None,
    headless: bool = False,
    timeout: int = 120,
) -> None:
    """Open Chrome via undetected-chromedriver, walk through Google login.

    This function is designed to run in a separate thread while
    ``InstalledAppFlow.run_local_server(open_browser=False)`` listens on
    localhost for the callback.  Once the consent screen is approved the
    browser will redirect to ``http://localhost:<port>/...`` and the flow
    picks up the authorization code.

    Raises on hard failures; caller should handle gracefully.
    """
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    chrome_ver = _detect_chrome_version()
    logger.info("Selenium: detected Chrome version_main=%s", chrome_ver)
    driver = uc.Chrome(options=options, version_main=chrome_ver)
    driver.set_page_load_timeout(timeout)
    wait = WebDriverWait(driver, 30)

    try:
        logger.info("Selenium: navigating to auth URL for %s", login_email)
        driver.get(auth_url)
        time.sleep(_HUMAN_DELAY)

        # --- Step 1: Email ---
        _enter_email(driver, wait, login_email)

        # --- Step 2: Password ---
        _enter_password(driver, wait, login_password)

        # --- Step 3: Security challenges (2FA, phone verify, etc.) ---
        _handle_security_challenge(driver, totp_secret)

        # --- Step 4: Consent / "Allow" buttons ---
        _approve_consent(driver)

        # --- Step 5: Wait for redirect to localhost (InstalledAppFlow captures it) ---
        logger.info("Selenium: waiting for localhost redirect…")
        WebDriverWait(driver, timeout).until(
            lambda d: "localhost" in d.current_url or "127.0.0.1" in d.current_url
        )
        logger.info("Selenium: redirect captured — %s", driver.current_url.split("?")[0])

    except TimeoutException:
        _save_screenshot(driver, "timeout")
        logger.error("Selenium: timed out during OAuth flow")
        raise
    except Exception as exc:
        _save_screenshot(driver, "error")
        logger.error("Selenium: OAuth automation error — %s", exc)
        raise
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _enter_email(driver, wait, email: str) -> None:
    """Fill in the email field and click Next."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    logger.debug("Selenium: entering email")
    email_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="email"]')))
    email_input.clear()
    _human_type(email_input, email)
    time.sleep(0.5)
    _click_next(driver)
    time.sleep(_HUMAN_DELAY)


def _enter_password(driver, wait, password: str) -> None:
    """Fill in the password field and click Next."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC

    logger.debug("Selenium: entering password")
    pw_input = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="password"]')))
    pw_input.clear()
    _human_type(pw_input, password)
    time.sleep(0.5)
    _click_next(driver)
    time.sleep(_HUMAN_DELAY)


def _handle_security_challenge(driver, totp_secret: Optional[str]) -> None:
    """Handle Google security challenges after password entry.

    Covers: direct TOTP prompt, "Verify it's you" phone challenge
    (clicks "Try another way" to find TOTP/authenticator option),
    and unknown challenges (saves screenshot, waits for manual action).
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    time.sleep(_HUMAN_DELAY)

    # Check if we landed on a challenge page at all
    if _is_on_consent_or_redirect(driver):
        logger.debug("Selenium: no security challenge, already on consent/redirect")
        return

    # Case 1: Direct TOTP input (input[type="tel"] for 6-digit code)
    if totp_secret and _try_enter_totp(driver, totp_secret):
        return

    # Case 2: "Try another way" link present (phone verify, etc.)
    if _click_try_another_way(driver):
        time.sleep(_HUMAN_DELAY)

        # Look for authenticator/TOTP option on the methods page
        if totp_secret and _select_totp_method(driver):
            time.sleep(_HUMAN_DELAY)
            if _try_enter_totp(driver, totp_secret):
                return

    # Case 3: Unknown challenge — save screenshot and wait for manual action
    logger.warning("Selenium: unhandled security challenge, waiting for manual intervention")
    _save_screenshot(driver, "challenge")

    # Wait up to 120s for user to complete the challenge manually
    try:
        WebDriverWait(driver, 120).until(
            lambda d: _is_on_consent_or_redirect(d)
        )
        logger.info("Selenium: security challenge resolved (manual)")
    except TimeoutException:
        logger.error("Selenium: security challenge was not resolved within timeout")
        _save_screenshot(driver, "challenge_timeout")
        raise


def _is_on_consent_or_redirect(driver) -> bool:
    """Check if the browser is on the consent screen or already redirected."""
    url = driver.current_url
    if "localhost" in url or "127.0.0.1" in url:
        return True
    if "/o/oauth2/v2/auth/oauthchooseaccount" in url:
        return False
    if "/signin/oauth/consent" in url or "/consent" in url:
        return True
    # Check page content for consent indicators
    try:
        from selenium.webdriver.common.by import By
        page_text = driver.find_element(By.TAG_NAME, "body").text
        consent_phrases = ["is requesting access", "wants to access", "запрашивает доступ",
                           "хоче отримати доступ", "Grant access", "Allow"]
        return any(phrase in page_text for phrase in consent_phrases)
    except Exception:
        return False


def _try_enter_totp(driver, totp_secret: str) -> bool:
    """Try to find a TOTP input field and enter the code. Returns True on success."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    try:
        totp_input = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="tel"]'))
        )
    except TimeoutException:
        return False

    logger.info("Selenium: entering TOTP code")
    code = pyotp.TOTP(totp_secret).now()
    totp_input.clear()
    _human_type(totp_input, code)
    time.sleep(0.5)
    _click_next(driver)
    time.sleep(_HUMAN_DELAY)
    return True


def _click_try_another_way(driver) -> bool:
    """Click 'Try another way' link if present. Returns True if clicked."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    try_texts = ["Try another way", "Другой способ", "Інший спосіб", "try another way"]
    for text in try_texts:
        try:
            link = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')] | "
                    f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]"
                ))
            )
            logger.info("Selenium: clicking '%s'", text)
            link.click()
            return True
        except TimeoutException:
            continue
    return False


def _select_totp_method(driver) -> bool:
    """On the 'Choose verification method' page, select Authenticator app."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    totp_keywords = [
        "authenticator", "google authenticator", "verification code",
        "аутентификатор", "автентифікатор", "код подтверждения",
        "get a verification code", "use your authenticator app",
    ]
    for keyword in totp_keywords:
        try:
            option = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    f"//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{keyword}')]"
                ))
            )
            logger.info("Selenium: selecting TOTP method via '%s'", keyword)
            option.click()
            return True
        except TimeoutException:
            continue
    logger.warning("Selenium: TOTP/Authenticator option not found in verification methods")
    return False


def _approve_consent(driver) -> None:
    """Click through the Google OAuth consent screen ("Allow" / "Continue")."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    time.sleep(_HUMAN_DELAY)

    button_texts = ["Allow", "Continue", "Разрешить", "Продовжити", "Далее", "Next"]
    for btn_text in button_texts:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    f"//button[contains(., '{btn_text}')] | //span[contains(., '{btn_text}')]/ancestor::button",
                ))
            )
            logger.debug("Selenium: clicking '%s'", btn_text)
            btn.click()
            time.sleep(_HUMAN_DELAY)
        except TimeoutException:
            continue

    # Google sometimes shows a multi-step consent with checkboxes then "Continue"
    _click_all_checkboxes(driver)
    time.sleep(0.5)

    for btn_text in ["Allow", "Continue", "Разрешить", "Продовжити"]:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    f"//button[contains(., '{btn_text}')] | //span[contains(., '{btn_text}')]/ancestor::button",
                ))
            )
            btn.click()
            time.sleep(_HUMAN_DELAY)
        except TimeoutException:
            continue


def _click_next(driver) -> None:
    """Click the 'Next' / 'Далее' button on a Google sign-in page."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    next_selectors = [
        "//button[contains(., 'Next')]",
        "//button[contains(., 'Далее')]",
        "//button[contains(., 'Далі')]",
        "//span[contains(., 'Next')]/ancestor::button",
        "//span[contains(., 'Далее')]/ancestor::button",
        "//span[contains(., 'Далі')]/ancestor::button",
        "#identifierNext",
        "#passwordNext",
    ]
    for selector in next_selectors:
        try:
            if selector.startswith("//"):
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
            else:
                btn = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
            btn.click()
            return
        except TimeoutException:
            continue

    logger.warning("Selenium: could not find Next button, trying Enter key")
    from selenium.webdriver.common.keys import Keys
    driver.switch_to.active_element.send_keys(Keys.RETURN)


def _click_all_checkboxes(driver) -> None:
    """Check any unchecked consent checkboxes on the page."""
    from selenium.webdriver.common.by import By

    try:
        checkboxes = driver.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]:not(:checked)')
        for cb in checkboxes:
            try:
                cb.click()
            except Exception:
                pass
    except Exception:
        pass


def _detect_chrome_version() -> int:
    """Detect installed Chrome/Chromium major version number."""
    import subprocess
    import platform
    import re

    system = platform.system()
    candidates = []
    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Linux":
        candidates = ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]
    else:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]

    for binary in candidates:
        try:
            out = subprocess.check_output([binary, "--version"], stderr=subprocess.DEVNULL, timeout=5)
            match = re.search(r"(\d+)\.\d+\.\d+", out.decode())
            if match:
                return int(match.group(1))
        except Exception:
            continue

    logger.warning("Could not detect Chrome version, defaulting to 145")
    return 145


def _human_type(element, text: str) -> None:
    """Type text character by character with small random delays."""
    import random
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.03, 0.12))


def _save_screenshot(driver, label: str) -> None:
    """Save a debug screenshot on failure."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOT_DIR / f"selenium_{label}_{ts}.png"
        driver.save_screenshot(str(path))
        logger.info("Selenium: screenshot saved to %s", path)
    except Exception as exc:
        logger.debug("Selenium: could not save screenshot — %s", exc)
