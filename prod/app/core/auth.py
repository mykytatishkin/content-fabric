"""Centralized auth helpers — cookie, bearer, admin checks, user-scoped filtering."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from app.core.security import decode_access_token
from shared.db.models import UserStatus

logger = logging.getLogger(__name__)

COOKIE_NAME = "cff_token"


# ── Core: JWT → User lookup ─────────────────────────────────────────

def user_from_token(token: str) -> dict | None:
    """Decode a JWT and fetch the user from DB. Returns user dict or None."""
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    from shared.db.repositories import user_repo
    return user_repo.get_user_by_id(int(payload["sub"]))


def user_from_cookie(request: Request) -> dict | None:
    """Extract JWT from cookie and return user dict or None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return user_from_token(token)


# ── Access checks ────────────────────────────────────────────────────

def is_admin(user: dict) -> bool:
    """Check if user has admin status."""
    return user.get("status") == UserStatus.ADMIN


def require_user(request: Request) -> tuple[dict | None, RedirectResponse | None]:
    """Require authenticated user via cookie. Returns (user, redirect)."""
    user = user_from_cookie(request)
    if not user:
        return None, RedirectResponse("/app/login", status_code=302)
    return user, None


def require_admin(request: Request) -> tuple[dict | None, RedirectResponse | None]:
    """Require admin user via cookie. Returns (user, redirect)."""
    user = user_from_cookie(request)
    if not user:
        logger.debug("Admin access denied: no valid cookie")
        return None, RedirectResponse("/app/login", status_code=302)
    if not is_admin(user):
        logger.warning("Admin access denied: user_id=%s is not admin", user.get("id"))
        return None, RedirectResponse("/app/", status_code=302)
    return user, None


def require_admin_api(user: dict) -> dict:
    """Require admin for API endpoints. Raises HTTPException(403)."""
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── User-scoped filtering ───────────────────────────────────────────

def scoped_user_id(user: dict) -> int | None:
    """Return user ID for repo filtering, or None if admin (sees all)."""
    if is_admin(user):
        return None
    return user["id"]


def scoped_where(user: dict, table_alias: str = "") -> tuple[str, dict]:
    """Return (WHERE clause, params) for user-scoped raw SQL queries."""
    if is_admin(user):
        return "1=1", {}
    prefix = f"{table_alias}." if table_alias else ""
    return f"{prefix}created_by = :user_id", {"user_id": user["id"]}


def check_owner(resource: dict, user: dict, owner_field: str = "created_by") -> bool:
    """Check if user owns the resource. Admins always pass."""
    if is_admin(user):
        return True
    return resource.get(owner_field) == user["id"]


def check_owner_or_404(resource: dict, user: dict, owner_field: str = "created_by") -> None:
    """Raise 404 if non-admin user doesn't own the resource."""
    if not check_owner(resource, user, owner_field):
        raise HTTPException(status_code=404, detail="Not found")
