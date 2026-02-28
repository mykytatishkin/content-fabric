"""User-facing web portal — SSR pages with cookie-based JWT auth."""

import logging
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

COOKIE_NAME = "cff_token"


# ── Helpers ──────────────────────────────────────────────────────────

def _get_current_user(request: Request) -> dict | None:
    """Read JWT from cookie and return user dict or None."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    from shared.db.repositories import user_repo
    user = user_repo.get_user_by_id(int(payload["sub"]))
    return user


def _require_user(request: Request):
    """Return user or redirect to login."""
    user = _get_current_user(request)
    if not user:
        return None, RedirectResponse("/app/login", status_code=302)
    return user, None


def _set_token_cookie(response, user_id: int):
    token = create_access_token({"sub": user_id})
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite="lax", path="/", max_age=86400,
    )
    return response


# ── Auth Pages (public) ─────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = _get_current_user(request)
    if user:
        return RedirectResponse("/app/", status_code=302)
    return templates.TemplateResponse("app_login.html", {
        "request": request, "error": None,
    })


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(""),
):
    from shared.db.repositories import user_repo
    user = user_repo.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse("app_login.html", {
            "request": request, "error": "Wrong email or password",
        })

    # 2FA check
    if user.get("totp_enabled"):
        if not totp_code:
            return templates.TemplateResponse("app_login.html", {
                "request": request, "error": "2FA code required", "email": email,
            })
        import pyotp
        totp = pyotp.TOTP(user["totp_secret"])
        if not totp.verify(totp_code, valid_window=1):
            # Try backup code
            if not user_repo.consume_backup_code(user["id"], totp_code):
                return templates.TemplateResponse("app_login.html", {
                    "request": request, "error": "Invalid 2FA code", "email": email,
                })

    user_repo.update_last_login(user["id"])
    resp = RedirectResponse("/app/", status_code=302)
    return _set_token_cookie(resp, user["id"])


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = _get_current_user(request)
    if user:
        return RedirectResponse("/app/", status_code=302)
    return templates.TemplateResponse("app_register.html", {
        "request": request, "error": None,
    })


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(""),
):
    import uuid as _uuid
    from shared.db.repositories import user_repo

    if user_repo.get_user_by_email(email):
        return templates.TemplateResponse("app_register.html", {
            "request": request, "error": "Email already registered",
        })
    if user_repo.get_user_by_username(username):
        return templates.TemplateResponse("app_register.html", {
            "request": request, "error": "Username already taken",
        })
    if len(password) < 6:
        return templates.TemplateResponse("app_register.html", {
            "request": request, "error": "Password must be at least 6 characters",
        })

    uid = user_repo.create_user(
        uuid=str(_uuid.uuid4()),
        username=username,
        email=email,
        password_hash=hash_password(password),
        auth_key=str(_uuid.uuid4()),
        display_name=display_name or username,
    )
    resp = RedirectResponse("/app/", status_code=302)
    return _set_token_cookie(resp, uid)


@router.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse("/app/login", status_code=302)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


# ── Dashboard ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    ctx = {
        "request": request, "user": user, "active": "dashboard",
        "channels_total": 0, "tasks_pending": 0, "tasks_completed": 0,
        "tasks_failed": 0, "recent_tasks": [],
    }
    try:
        with get_connection() as conn:
            row = conn.execute(text(
                "SELECT COUNT(*) FROM platform_channels WHERE project_id = 1"
            )).fetchone()
            ctx["channels_total"] = row[0] or 0

            rows = conn.execute(text(
                "SELECT status, COUNT(*) FROM content_upload_queue_tasks GROUP BY status"
            )).fetchall()
            status_map = {0: "tasks_pending", 1: "tasks_completed", 2: "tasks_failed"}
            for r in rows:
                key = status_map.get(r[0])
                if key:
                    ctx[key] = r[1]

            recent = conn.execute(text(
                "SELECT id, channel_id, title, status, scheduled_at, created_at "
                "FROM content_upload_queue_tasks ORDER BY created_at DESC LIMIT 10"
            )).fetchall()
            ctx["recent_tasks"] = [
                {"id": r[0], "channel_id": r[1], "title": r[2],
                 "status": r[3], "scheduled_at": r[4], "created_at": r[5]}
                for r in recent
            ]
    except Exception as e:
        logger.error("Dashboard error: %s", e)

    return templates.TemplateResponse("app_dashboard.html", ctx)


# ── Channels ─────────────────────────────────────────────────────────

@router.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request):
    user, redirect = _require_user(request)
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
                {"id": r[0], "name": r[1], "platform_channel_id": r[2],
                 "enabled": bool(r[3]), "processing_status": bool(r[4]),
                 "has_tokens": bool(r[5]), "created_at": r[6]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Channels error: %s", e)

    return templates.TemplateResponse("app_channels.html", {
        "request": request, "user": user, "active": "channels", "channels": channels,
    })


@router.get("/channels/add", response_class=HTMLResponse)
async def channel_add_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import console_repo
    consoles = console_repo.list_consoles_brief(enabled_only=True)

    return templates.TemplateResponse("app_channel_add.html", {
        "request": request, "user": user, "active": "channels",
        "consoles": consoles, "error": None, "success": None,
    })


@router.post("/channels/add", response_class=HTMLResponse)
async def channel_add_submit(
    request: Request,
    name: str = Form(...),
    platform_channel_id: str = Form(...),
    console_id: int = Form(...),
    enabled: bool = Form(False),
    login_email: str = Form(""),
    login_password: str = Form(""),
    totp_secret: str = Form(""),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo, console_repo

    consoles = console_repo.list_consoles_brief(enabled_only=True)
    ctx = {
        "request": request, "user": user, "active": "channels",
        "consoles": consoles, "error": None, "success": None,
    }

    if channel_repo.channel_exists_by_name(name):
        ctx["error"] = f"Channel '{name}' already exists"
        return templates.TemplateResponse("app_channel_add.html", ctx)

    project_id = channel_repo.get_default_project_id() or 1
    ch_id = channel_repo.add_channel(
        project_id=project_id,
        name=name,
        platform_channel_id=platform_channel_id.strip(),
        console_id=console_id,
        enabled=enabled,
    )
    if not ch_id:
        ctx["error"] = "Failed to create channel (duplicate?)"
        return templates.TemplateResponse("app_channel_add.html", ctx)

    if login_email:
        channel_repo.add_login_credentials(
            channel_id=ch_id,
            login_email=login_email,
            login_password=login_password,
            totp_secret=totp_secret or None,
        )

    return RedirectResponse("/app/channels", status_code=302)


# ── Tasks ────────────────────────────────────────────────────────────

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    status_filter = request.query_params.get("status", "")
    channel_filter = request.query_params.get("channel_id", "")

    tasks = []
    stats = {}
    channels = []
    try:
        with get_connection() as conn:
            # Stats
            rows = conn.execute(text(
                "SELECT status, COUNT(*) FROM content_upload_queue_tasks GROUP BY status"
            )).fetchall()
            names = {0: "pending", 1: "completed", 2: "failed", 3: "processing", 4: "cancelled"}
            stats = {names.get(r[0], "unknown"): r[1] for r in rows}

            # Channels for filter dropdown
            ch_rows = conn.execute(text(
                "SELECT id, name FROM platform_channels ORDER BY name"
            )).fetchall()
            channels = [{"id": r[0], "name": r[1]} for r in ch_rows]

            # Tasks
            where = "1=1"
            params = {}
            if status_filter:
                where += " AND status = :status"
                params["status"] = int(status_filter)
            if channel_filter:
                where += " AND channel_id = :channel_id"
                params["channel_id"] = int(channel_filter)

            rows = conn.execute(text(f"""
                SELECT t.id, t.channel_id, pc.name, t.media_type, t.title,
                       t.status, t.scheduled_at, t.created_at, t.error_message
                FROM content_upload_queue_tasks t
                LEFT JOIN platform_channels pc ON t.channel_id = pc.id
                WHERE {where}
                ORDER BY t.created_at DESC LIMIT 100
            """), params).fetchall()
            tasks = [
                {"id": r[0], "channel_id": r[1], "channel_name": r[2] or "?",
                 "media_type": r[3], "title": r[4], "status": r[5],
                 "scheduled_at": r[6], "created_at": r[7], "error_message": r[8]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Tasks error: %s", e)

    return templates.TemplateResponse("app_tasks.html", {
        "request": request, "user": user, "active": "tasks",
        "tasks": tasks, "stats": stats, "channels": channels,
        "status_filter": status_filter, "channel_filter": channel_filter,
    })


@router.get("/tasks/new", response_class=HTMLResponse)
async def task_new_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    channels = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text(
                "SELECT id, name FROM platform_channels WHERE enabled = 1 ORDER BY name"
            )).fetchall()
            channels = [{"id": r[0], "name": r[1]} for r in rows]
    except Exception as e:
        logger.error("Task new error: %s", e)

    return templates.TemplateResponse("app_task_new.html", {
        "request": request, "user": user, "active": "tasks",
        "channels": channels, "error": None,
    })


@router.post("/tasks/new", response_class=HTMLResponse)
async def task_new_submit(
    request: Request,
    channel_id: int = Form(...),
    title: str = Form(...),
    source_file_path: str = Form(...),
    scheduled_at: str = Form(""),
    description: str = Form(""),
    keywords: str = Form(""),
    thumbnail_path: str = Form(""),
    post_comment: str = Form(""),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import task_repo

    from datetime import datetime
    scheduled = datetime.utcnow()
    if scheduled_at:
        try:
            scheduled = datetime.fromisoformat(scheduled_at)
        except ValueError:
            pass

    task_repo.create_task(
        channel_id=channel_id,
        source_file_path=source_file_path,
        title=title,
        description=description or None,
        keywords=keywords or None,
        thumbnail_path=thumbnail_path or None,
        post_comment=post_comment or None,
        scheduled_at=scheduled,
    )
    return RedirectResponse("/app/tasks", status_code=302)


# ── Templates ────────────────────────────────────────────────────────

@router.get("/templates", response_class=HTMLResponse)
async def templates_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    tpls = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text("""
                SELECT st.id, st.name, st.description, st.timezone, st.is_active,
                       COUNT(ss.id) as slot_count
                FROM schedule_templates st
                LEFT JOIN schedule_template_slots ss ON st.id = ss.template_id
                GROUP BY st.id
                ORDER BY st.created_at DESC
            """)).fetchall()
            tpls = [
                {"id": r[0], "name": r[1], "description": r[2],
                 "timezone": r[3], "is_active": bool(r[4]), "slot_count": r[5]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Templates error: %s", e)

    return templates.TemplateResponse("app_templates.html", {
        "request": request, "user": user, "active": "templates", "templates_list": tpls,
    })


# ── Settings ─────────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    return templates.TemplateResponse("app_settings.html", {
        "request": request, "user": user, "active": "settings",
        "message": None,
    })
