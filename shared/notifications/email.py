"""Email notification sender."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

def send(
    recipients: list[str],
    subject: str,
    body: str,
) -> bool:
    """Send an email. Returns True on success."""
    SMTP_SERVER = os.environ.get("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
    USERNAME = os.environ.get("EMAIL_USERNAME", "")
    PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
    if not USERNAME or not PASSWORD:
        logger.warning("Email credentials not configured")
        return False
    if not recipients:
        logger.warning("No email recipients")
        return False

    msg = MIMEMultipart()
    msg["From"] = USERNAME
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls(context=ctx)
            server.login(USERNAME, PASSWORD)
            server.sendmail(USERNAME, recipients, msg.as_string())
        logger.info("Email sent to %s", recipients)
        return True
    except Exception:
        logger.exception("Email send error")
        return False
