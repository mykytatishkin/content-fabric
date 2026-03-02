"""FastAPI dependencies — authentication."""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from shared.db.repositories import user_repo

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate Bearer token and return the authenticated user dict.

    Raises 401 if token is missing/invalid or user not found.
    """
    if creds is None:
        logger.debug("Auth failed: no credentials provided")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(creds.credentials)
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
