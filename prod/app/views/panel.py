"""SSR admin panel — Jinja2 server-side rendered pages (admin-only)."""

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.security import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter()

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

COOKIE_NAME = "cff_token"


def _require_admin(request: Request):
    """Check cookie for admin user. Returns (user, redirect)."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None, RedirectResponse("/app/login", status_code=302)
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None, RedirectResponse("/app/login", status_code=302)
    from shared.db.repositories import user_repo
    user = user_repo.get_user_by_id(int(payload["sub"]))
    if not user or user.get("status") != 1:  # UserStatus.ADMIN
        return None, RedirectResponse("/app/", status_code=302)
    return user, None


@router.get("/")
async def dashboard(request: Request):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    ctx = {
        "request": request, "active": "dashboard",
        "channels_total": 0, "channels_active": 0, "users_total": 0,
        "tasks_pending": 0, "tasks_completed": 0, "tasks_failed": 0,
        "queue_total": 0, "recent_failures": [], "reauth_channels": [],
    }

    try:
        with get_connection() as conn:
            # Channel counts
            row = conn.execute(text("SELECT COUNT(*), SUM(enabled) FROM platform_channels")).fetchone()
            ctx["channels_total"] = row[0] or 0
            ctx["channels_active"] = int(row[1] or 0)

            # User count
            row = conn.execute(text("SELECT COUNT(*) FROM platform_users")).fetchone()
            ctx["users_total"] = row[0] or 0

            # Task stats
            rows = conn.execute(text(
                "SELECT status, COUNT(*) FROM content_upload_queue_tasks GROUP BY status"
            )).fetchall()
            status_map = {0: "tasks_pending", 1: "tasks_completed", 2: "tasks_failed", 3: "tasks_processing"}
            for r in rows:
                key = status_map.get(r[0])
                if key:
                    ctx[key] = r[1]

            # Recent failures
            failures = conn.execute(text(
                "SELECT id, channel_id, title, error_message, completed_at "
                "FROM content_upload_queue_tasks WHERE status = 2 "
                "ORDER BY completed_at DESC LIMIT 10"
            )).fetchall()
            ctx["recent_failures"] = [
                {"id": f[0], "channel_id": f[1], "title": f[2], "error_message": f[3], "completed_at": f[4]}
                for f in failures
            ]

            # Channels needing reauth
            reauth = conn.execute(text("""
                SELECT pc.id, pc.name, pclc.login_email,
                       pclc.totp_secret IS NOT NULL as has_totp, pclc.last_error
                FROM platform_channels pc
                LEFT JOIN platform_channel_login_credentials pclc ON pc.id = pclc.channel_id
                WHERE pc.enabled = 1 AND pc.processing_status = 0
                  AND pc.access_token IS NULL
                ORDER BY pc.id
            """)).fetchall()
            ctx["reauth_channels"] = [
                {"id": r[0], "name": r[1], "login_email": r[2], "has_totp": bool(r[3]), "last_error": r[4]}
                for r in reauth
            ]

        # Redis queue
        try:
            from shared.queue.config import get_redis
            r = get_redis()
            ctx["queue_total"] = (
                r.llen("rq:queue:publishing") +
                r.llen("rq:queue:notifications") +
                r.llen("rq:queue:voice")
            )
        except Exception:
            ctx["queue_total"] = 0

    except Exception as e:
        logger.error("Dashboard data error: %s", e)

    return templates.TemplateResponse("dashboard.html", ctx)


@router.get("/channels")
async def channels_page(request: Request):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    channels = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text("""
                SELECT id, name, platform_channel_id, enabled, processing_status,
                       access_token IS NOT NULL as has_tokens, created_at
                FROM platform_channels ORDER BY id
            """)).fetchall()
            channels = [
                {"id": r[0], "name": r[1], "platform_channel_id": r[2], "enabled": bool(r[3]),
                 "processing_status": bool(r[4]), "has_tokens": bool(r[5]), "created_at": r[6]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Channels page error: %s", e)

    return templates.TemplateResponse("channels.html", {
        "request": request, "active": "channels", "channels": channels,
    })


@router.get("/tasks")
async def tasks_page(request: Request):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    tasks = []
    stats = {}
    try:
        with get_connection() as conn:
            rows = conn.execute(text(
                "SELECT status, COUNT(*) FROM content_upload_queue_tasks GROUP BY status"
            )).fetchall()
            names = {0: "pending", 1: "completed", 2: "failed", 3: "processing", 4: "cancelled"}
            stats = {names.get(r[0], "unknown"): r[1] for r in rows}

            rows = conn.execute(text("""
                SELECT id, channel_id, media_type, title, status, scheduled_at, created_at
                FROM content_upload_queue_tasks
                ORDER BY created_at DESC LIMIT 200
            """)).fetchall()
            tasks = [
                {"id": r[0], "channel_id": r[1], "media_type": r[2], "title": r[3],
                 "status": r[4], "scheduled_at": r[5], "created_at": r[6]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Tasks page error: %s", e)

    return templates.TemplateResponse("tasks.html", {
        "request": request, "active": "tasks", "tasks": tasks, "stats": stats,
    })


@router.get("/users")
async def users_page(request: Request):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    users = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text(
                "SELECT id, username, email, display_name, status, totp_enabled, created_at "
                "FROM platform_users ORDER BY id"
            )).fetchall()
            users = [
                {"id": r[0], "username": r[1], "email": r[2], "display_name": r[3],
                 "status": r[4], "totp_enabled": bool(r[5]), "created_at": r[6]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Users page error: %s", e)

    return templates.TemplateResponse("users.html", {
        "request": request, "active": "users", "users": users,
    })


@router.get("/credentials")
async def credentials_page(request: Request):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    credentials = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text("""
                SELECT channel_id, login_email, totp_secret IS NOT NULL as has_totp,
                       backup_codes IS NOT NULL as has_backup, proxy_host,
                       enabled, last_success_at, last_error
                FROM platform_channel_login_credentials ORDER BY channel_id
            """)).fetchall()
            credentials = [
                {"channel_id": r[0], "login_email": r[1], "has_totp": bool(r[2]),
                 "has_backup": bool(r[3]), "proxy_host": r[4], "enabled": bool(r[5]),
                 "last_success_at": r[6], "last_error": r[7]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Credentials page error: %s", e)

    return templates.TemplateResponse("credentials.html", {
        "request": request, "active": "credentials", "credentials": credentials,
    })


@router.get("/payment")
async def payment_page(request: Request):
    user, redirect = _require_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse("payment.html", {
        "request": request, "active": "payment",
    })
