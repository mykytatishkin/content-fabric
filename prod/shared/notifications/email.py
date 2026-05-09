"""Email notification sender."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Mapping

logger = logging.getLogger(__name__)


def _smtp_creds() -> tuple[str, int, str, str]:
    """Read SMTP creds from env. Empty user/pass => not configured."""
    server = os.environ.get("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    port = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    username = os.environ.get("EMAIL_USERNAME", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    return server, port, username, password


def send(
    recipients: list[str],
    subject: str,
    body: str,
) -> bool:
    """Send a plain-text email. Returns True on success."""
    server_addr, port, username, password = _smtp_creds()
    if not username or not password:
        logger.warning("Email credentials not configured")
        return False
    if not recipients:
        logger.warning("No email recipients")
        return False

    msg = MIMEMultipart()
    msg["From"] = username
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with smtplib.SMTP(server_addr, port) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(username, password)
            smtp.sendmail(username, recipients, msg.as_string())
        logger.info("Email sent to %s", recipients)
        return True
    except Exception:
        logger.exception("Email send error")
        return False


def send_html(
    recipients: list[str],
    subject: str,
    text_body: str,
    html_body: str,
) -> bool:
    """Send a multipart/alternative (text+html) email. Returns True on success."""
    server_addr, port, username, password = _smtp_creds()
    if not username or not password:
        logger.warning("Email credentials not configured — HTML mail to %s skipped", recipients)
        return False
    if not recipients:
        logger.warning("No email recipients")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = username
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with smtplib.SMTP(server_addr, port) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(username, password)
            smtp.sendmail(username, recipients, msg.as_string())
        logger.info("Email sent to %s (subject=%s)", recipients, subject)
        return True
    except Exception:
        logger.exception("Email send error")
        return False


# ── Template rendering (Jinja, lazy) ───────────────────────────────────


_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2] / "app" / "templates" / "email"
)
_jinja_env = None


def _env():
    global _jinja_env
    if _jinja_env is None:
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        _jinja_env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(("html",)),
        )
    return _jinja_env


def _render(name: str, ctx: Mapping[str, object]) -> str:
    return _env().get_template(name).render(**dict(ctx))


def send_password_reset_email(to: str, reset_url: str, user_name: str | None = None) -> bool:
    """Send the password-reset email (HTML + plain alternative).

    Mirrors Yii's PasswordResetRequestForm::sendEmail().
    Subject is in Russian per spec.
    Returns False (without crashing) if SMTP creds are absent.
    """
    if not to:
        logger.warning("send_password_reset_email called with empty recipient")
        return False
    ctx = {"reset_url": reset_url, "user_name": user_name or ""}
    try:
        text_body = _render("password_reset.txt", ctx)
        html_body = _render("password_reset.html", ctx)
    except Exception:
        logger.exception("Failed to render password reset email")
        return False
    return send_html([to], "Сброс пароля Content Fabric", text_body, html_body)


def send_verification_email(to: str, verify_url: str, user_name: str | None = None) -> bool:
    """Send the email-verification email (HTML + plain alternative)."""
    if not to:
        logger.warning("send_verification_email called with empty recipient")
        return False
    ctx = {"verify_url": verify_url, "user_name": user_name or ""}
    try:
        text_body = _render("verify_email.txt", ctx)
        html_body = _render("verify_email.html", ctx)
    except Exception:
        logger.exception("Failed to render verification email")
        return False
    return send_html([to], "Подтверждение email Content Fabric", text_body, html_body)
