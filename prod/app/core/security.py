"""JWT token creation and verification."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY environment variable is not set. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
# RFC 7518 §3.2: HS256 keys MUST be ≥ key-output (256 bits / 32 bytes).
# PyJWT logs ``InsecureKeyLengthWarning`` once per token decode otherwise — see
# 37 occurrences in /var/log/cff-api.log on 2026-05-09.  Allow the user to
# explicitly opt-out only for local/test setups via JWT_ALLOW_SHORT_KEY=1.
_MIN_KEY_BYTES = 32
if len(SECRET_KEY.encode("utf-8")) < _MIN_KEY_BYTES:
    if os.environ.get("JWT_ALLOW_SHORT_KEY", "").lower() in {"1", "true", "yes"}:
        logger.warning(
            "JWT_SECRET_KEY is %d bytes (< %d). Continuing because "
            "JWT_ALLOW_SHORT_KEY=1, but this is insecure for production.",
            len(SECRET_KEY.encode("utf-8")), _MIN_KEY_BYTES,
        )
    else:
        raise RuntimeError(
            f"JWT_SECRET_KEY is {len(SECRET_KEY.encode('utf-8'))} bytes; "
            f"HS256 requires at least {_MIN_KEY_BYTES} bytes per RFC 7518 §3.2. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            " — or set JWT_ALLOW_SHORT_KEY=1 to override (NOT recommended)."
        )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))  # 24h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    # "sub" must be a string per JWT spec
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate JWT. Returns payload or None on failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except PyJWTError:
        return None
