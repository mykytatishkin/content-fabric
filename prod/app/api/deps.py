"""FastAPI dependencies — authentication.

Accepts either:
  - Authorization: Bearer <jwt>   (machine clients, CLI, tests)
  - Cookie cff_token=<jwt>        (browser pages — same cookie set by /app/login)

When both are present, Bearer wins. CSRFMiddleware (see main.py) covers the
cookie path so cross-site POSTs are still rejected.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from shared.db.repositories import user_repo

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)
_COOKIE_NAME = "cff_token"


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate JWT (Bearer header OR cff_token cookie) and return the user dict."""
    token: str | None = None
    if creds is not None:
        token = creds.credentials
    else:
        token = request.cookies.get(_COOKIE_NAME)

    if not token:
        logger.debug("Auth failed: no Bearer header and no cff_token cookie")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(token)
    if payload is None:
        logger.warning("Auth failed: invalid/expired JWT token")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id: int | None = payload.get("sub")
    if user_id is None:
        logger.warning("Auth failed: JWT missing 'sub' claim")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = user_repo.get_user_by_id(int(user_id))
    if user is None:
        logger.warning("Auth failed: user_id=%s not found in DB", user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    logger.debug("Authenticated user_id=%s email=%s", user["id"], user.get("email"))
    return user


async def get_current_admin(user: dict = Depends(get_current_user)) -> dict:
    """Validate Bearer token and require admin status. Raises 403 if not admin."""
    from app.core.auth import is_admin

    if not is_admin(user):
        logger.warning("Admin access denied: user_id=%s is not admin", user.get("id"))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
