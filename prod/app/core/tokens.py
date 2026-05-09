"""Token utilities for password reset and email verification.

Mirrors the Yii convention where tokens encode the issuance timestamp:
    <random_hex>_<unix_timestamp>

This lets us validate TTL without a separate column. Reference:
.legacy/yii/yii/common/models/User.php:193-204
.legacy/yii/yii/common/config/params.php (passwordResetTokenExpire = 3600)
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone

# TTLs (seconds). Yii used 3600 for password reset.
PASSWORD_RESET_TTL_SEC = 3600          # 1 hour
VERIFICATION_TOKEN_TTL_SEC = 86400      # 24 hours


def generate_token() -> str:
    """Return a 64-hex-char random token (no embedded timestamp)."""
    return secrets.token_hex(32)


def make_reset_token() -> str:
    """Return a token with embedded unix timestamp: <hex>_<ts>.

    Mirrors Yii's `generatePasswordResetToken`:
        $this->password_reset_token = generateRandomString() . '_' . time();
    """
    return f"{secrets.token_hex(32)}_{int(time.time())}"


def make_verification_token() -> str:
    """Return a token with embedded unix timestamp for email verification.

    Mirrors Yii's `generateEmailVerificationToken`.
    """
    return f"{secrets.token_hex(32)}_{int(time.time())}"


def parse_token_ts(token: str) -> int | None:
    """Extract the unix timestamp from a `<hex>_<ts>` token, or None if malformed."""
    if not token or "_" not in token:
        return None
    try:
        _hex, ts = token.rsplit("_", 1)
        if not _hex or not ts:
            return None
        # Sanity check: the hex part should be hex-like and reasonably long.
        if len(_hex) < 16:
            return None
        return int(ts)
    except (ValueError, AttributeError):
        return None


def is_token_expired(issued_at: datetime, ttl_sec: int) -> bool:
    """Return True if `issued_at + ttl_sec` is in the past.

    `ttl_sec=0` means "always expired" (anything past the issue moment).
    """
    if issued_at is None:
        return True
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - issued_at).total_seconds()
    if ttl_sec <= 0:
        return True
    return age > ttl_sec


def is_token_ts_expired(token: str, ttl_sec: int) -> bool:
    """Return True if the timestamp embedded in the token is older than ttl_sec.

    Returns True for malformed tokens (no timestamp parseable). `ttl_sec=0`
    is treated as "always expired".
    """
    ts = parse_token_ts(token)
    if ts is None:
        return True
    if ttl_sec <= 0:
        return True
    return (int(time.time()) - ts) > ttl_sec
