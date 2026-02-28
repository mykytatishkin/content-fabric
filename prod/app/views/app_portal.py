"""User-facing web portal — SSR pages with cookie-based JWT auth."""

import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, Request, UploadFile
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


def _is_admin(user: dict) -> bool:
    return user.get("status") == "admin"


def _user_filter(user: dict, table_alias: str = "") -> tuple[str, dict]:
    """Return (WHERE clause, params) for user-scoped queries. Admins see all."""
    if _is_admin(user):
        return "1=1", {}
    prefix = f"{table_alias}." if table_alias else ""
    return f"{prefix}created_by = :user_id", {"user_id": user["id"]}


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
        "channels_total": 0, "channels_active": 0,
        "tasks_pending": 0, "tasks_completed": 0, "tasks_failed": 0, "tasks_total": 0,
        "success_rate": 0, "recent_tasks": [], "upcoming_tasks": [],
    }
    ch_where, ch_params = _user_filter(user)
    t_where, t_params = _user_filter(user, "t")
    try:
        with get_connection() as conn:
            row = conn.execute(text(
                f"SELECT COUNT(*), SUM(enabled) FROM platform_channels WHERE {ch_where}"
            ), ch_params).fetchone()
            ctx["channels_total"] = row[0] or 0
            ctx["channels_active"] = int(row[1] or 0)

            rows = conn.execute(text(
                f"SELECT status, COUNT(*) FROM content_upload_queue_tasks t WHERE {t_where} GROUP BY status"
            ), t_params).fetchall()
            status_map = {0: "tasks_pending", 1: "tasks_completed", 2: "tasks_failed"}
            total = 0
            for r in rows:
                key = status_map.get(r[0])
                if key:
                    ctx[key] = r[1]
                total += r[1]
            ctx["tasks_total"] = total
            done = ctx["tasks_completed"] + ctx["tasks_failed"]
            ctx["success_rate"] = round(ctx["tasks_completed"] / done * 100) if done > 0 else 0

            recent = conn.execute(text(
                f"SELECT t.id, t.channel_id, pc.name, t.title, t.status, t.scheduled_at, t.created_at "
                f"FROM content_upload_queue_tasks t "
                f"LEFT JOIN platform_channels pc ON t.channel_id = pc.id "
                f"WHERE {t_where} "
                f"ORDER BY t.created_at DESC LIMIT 10"
            ), t_params).fetchall()
            ctx["recent_tasks"] = [
                {"id": r[0], "channel_id": r[1], "channel_name": r[2] or "?",
                 "title": r[3], "status": r[4], "scheduled_at": r[5], "created_at": r[6]}
                for r in recent
            ]

            upcoming = conn.execute(text(
                f"SELECT t.id, t.channel_id, pc.name, t.title, t.scheduled_at "
                f"FROM content_upload_queue_tasks t "
                f"LEFT JOIN platform_channels pc ON t.channel_id = pc.id "
                f"WHERE t.status = 0 AND t.scheduled_at > NOW() AND {t_where} "
                f"ORDER BY t.scheduled_at ASC LIMIT 5"
            ), t_params).fetchall()
            ctx["upcoming_tasks"] = [
                {"id": r[0], "channel_id": r[1], "channel_name": r[2] or "?",
                 "title": r[3], "scheduled_at": r[4]}
                for r in upcoming
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

    ch_where, ch_params = _user_filter(user)
    channels = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text(f"""
                SELECT id, name, platform_channel_id, enabled, processing_status,
                       access_token IS NOT NULL as has_tokens, created_at
                FROM platform_channels WHERE {ch_where} ORDER BY id
            """), ch_params).fetchall()
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
        created_by=user["id"],
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


@router.get("/channels/{channel_id}", response_class=HTMLResponse)
async def channel_detail(request: Request, channel_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import channel_repo
    from sqlalchemy import text

    channel = channel_repo.get_channel_by_id(channel_id)
    if not channel:
        return RedirectResponse("/app/channels", status_code=302)
    if not _is_admin(user) and channel.get("created_by") != user["id"]:
        return RedirectResponse("/app/channels", status_code=302)

    stats = {}
    recent_tasks = []
    credentials = None
    try:
        with get_connection() as conn:
            # Task stats for this channel
            rows = conn.execute(text(
                "SELECT status, COUNT(*) FROM content_upload_queue_tasks "
                "WHERE channel_id = :cid GROUP BY status"
            ), {"cid": channel_id}).fetchall()
            names = {0: "pending", 1: "completed", 2: "failed", 3: "processing", 4: "cancelled"}
            stats = {names.get(r[0], "unknown"): r[1] for r in rows}
            stats["total"] = sum(r[1] for r in rows)

            # Recent tasks
            task_rows = conn.execute(text(
                "SELECT id, title, status, scheduled_at, created_at, error_message "
                "FROM content_upload_queue_tasks WHERE channel_id = :cid "
                "ORDER BY created_at DESC LIMIT 20"
            ), {"cid": channel_id}).fetchall()
            recent_tasks = [
                {"id": r[0], "title": r[1], "status": r[2],
                 "scheduled_at": r[3], "created_at": r[4], "error_message": r[5]}
                for r in task_rows
            ]

            # Login credentials
            cred_row = conn.execute(text(
                "SELECT login_email, totp_secret IS NOT NULL as has_totp, "
                "proxy_host, enabled, last_success_at, last_error "
                "FROM platform_channel_login_credentials WHERE channel_id = :cid"
            ), {"cid": channel_id}).fetchone()
            if cred_row:
                credentials = {
                    "login_email": cred_row[0], "has_totp": bool(cred_row[1]),
                    "proxy_host": cred_row[2], "enabled": bool(cred_row[3]),
                    "last_success_at": cred_row[4], "last_error": cred_row[5],
                }
    except Exception as e:
        logger.error("Channel detail error: %s", e)

    return templates.TemplateResponse("app_channel_detail.html", {
        "request": request, "user": user, "active": "channels",
        "channel": channel, "stats": stats, "recent_tasks": recent_tasks,
        "credentials": credentials,
    })


@router.post("/channels/{channel_id}/delete")
async def channel_delete(request: Request, channel_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo
    channel = channel_repo.get_channel_by_id(channel_id)
    if not channel or (not _is_admin(user) and channel.get("created_by") != user["id"]):
        return RedirectResponse("/app/channels", status_code=302)
    channel_repo.delete_channel(channel_id)
    return RedirectResponse("/app/channels", status_code=302)


@router.get("/channels/{channel_id}/edit", response_class=HTMLResponse)
async def channel_edit_page(request: Request, channel_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import channel_repo, console_repo
    from sqlalchemy import text

    channel = channel_repo.get_channel_by_id(channel_id)
    if not channel:
        return RedirectResponse("/app/channels", status_code=302)
    if not _is_admin(user) and channel.get("created_by") != user["id"]:
        return RedirectResponse("/app/channels", status_code=302)

    consoles = console_repo.list_consoles_brief(enabled_only=True)

    credentials = None
    try:
        with get_connection() as conn:
            row = conn.execute(text(
                "SELECT login_email, login_password, totp_secret, proxy_host, enabled "
                "FROM platform_channel_login_credentials WHERE channel_id = :cid"
            ), {"cid": channel_id}).fetchone()
            if row:
                credentials = {
                    "login_email": row[0], "login_password": row[1],
                    "totp_secret": row[2], "proxy_host": row[3], "enabled": bool(row[4]),
                }
    except Exception as e:
        logger.error("Channel edit load error: %s", e)

    return templates.TemplateResponse("app_channel_edit.html", {
        "request": request, "user": user, "active": "channels",
        "channel": channel, "consoles": consoles, "credentials": credentials,
        "error": None, "message": None,
    })


@router.post("/channels/{channel_id}/edit", response_class=HTMLResponse)
async def channel_edit_submit(
    request: Request,
    channel_id: int,
    name: str = Form(...),
    enabled: bool = Form(False),
    login_email: str = Form(""),
    login_password: str = Form(""),
    totp_secret: str = Form(""),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo

    channel = channel_repo.get_channel_by_id(channel_id)
    if not channel or (not _is_admin(user) and channel.get("created_by") != user["id"]):
        return RedirectResponse("/app/channels", status_code=302)

    channel_repo.update_channel(channel_id, name=name.strip(), enabled=enabled)

    if login_email:
        updated = channel_repo.update_login_credentials(
            channel_id, login_email=login_email,
            login_password=login_password or None,
            totp_secret=totp_secret or None,
        )
        if not updated:
            channel_repo.add_login_credentials(
                channel_id=channel_id,
                login_email=login_email,
                login_password=login_password,
                totp_secret=totp_secret or None,
            )

    return RedirectResponse(f"/app/channels/{channel_id}", status_code=302)


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
    t_where, t_params = _user_filter(user, "t")
    ch_where, ch_params = _user_filter(user)
    try:
        with get_connection() as conn:
            # Stats (user-scoped)
            rows = conn.execute(text(
                f"SELECT status, COUNT(*) FROM content_upload_queue_tasks t WHERE {t_where} GROUP BY status"
            ), t_params).fetchall()
            names = {0: "pending", 1: "completed", 2: "failed", 3: "processing", 4: "cancelled"}
            stats = {names.get(r[0], "unknown"): r[1] for r in rows}

            # Channels for filter dropdown (user-scoped)
            ch_rows = conn.execute(text(
                f"SELECT id, name FROM platform_channels WHERE {ch_where} ORDER BY name"
            ), ch_params).fetchall()
            channels = [{"id": r[0], "name": r[1]} for r in ch_rows]

            # Tasks (user-scoped)
            where = t_where
            params = dict(t_params)
            if status_filter:
                where += " AND t.status = :status"
                params["status"] = int(status_filter)
            if channel_filter:
                where += " AND t.channel_id = :channel_id"
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
    ch_where, ch_params = _user_filter(user)
    try:
        with get_connection() as conn:
            rows = conn.execute(text(
                f"SELECT id, name FROM platform_channels WHERE enabled = 1 AND {ch_where} ORDER BY name"
            ), ch_params).fetchall()
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
        created_by=user["id"],
    )
    return RedirectResponse("/app/tasks", status_code=302)


@router.post("/tasks/{task_id}/cancel")
async def task_cancel(request: Request, task_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import task_repo
    task = task_repo.get_task(task_id)
    if not task or (not _is_admin(user) and task.get("created_by") != user["id"]):
        return RedirectResponse("/app/tasks", status_code=302)
    task_repo.cancel_task(task_id)
    return RedirectResponse("/app/tasks", status_code=302)


@router.post("/tasks/{task_id}/retry")
async def task_retry(request: Request, task_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import task_repo
    task = task_repo.get_task(task_id)
    if not task or (not _is_admin(user) and task.get("created_by") != user["id"]):
        return RedirectResponse("/app/tasks", status_code=302)
    task_repo.retry_task(task_id)
    return RedirectResponse(f"/app/tasks/{task_id}", status_code=302)


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_detail(request: Request, task_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import task_repo
    from sqlalchemy import text

    task = task_repo.get_task(task_id)
    if not task:
        return RedirectResponse("/app/tasks", status_code=302)
    if not _is_admin(user) and task.get("created_by") != user["id"]:
        return RedirectResponse("/app/tasks", status_code=302)

    channel_name = "?"
    try:
        with get_connection() as conn:
            row = conn.execute(text(
                "SELECT name FROM platform_channels WHERE id = :cid"
            ), {"cid": task["channel_id"]}).fetchone()
            if row:
                channel_name = row[0]
    except Exception:
        pass
    task["channel_name"] = channel_name

    return templates.TemplateResponse("app_task_detail.html", {
        "request": request, "user": user, "active": "tasks",
        "task": task, "error": None, "message": None,
    })


@router.post("/tasks/{task_id}/reschedule", response_class=HTMLResponse)
async def task_reschedule(
    request: Request,
    task_id: int,
    scheduled_at: str = Form(...),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from datetime import datetime
    from shared.db.repositories import task_repo

    task = task_repo.get_task(task_id)
    if not task or (not _is_admin(user) and task.get("created_by") != user["id"]):
        return RedirectResponse("/app/tasks", status_code=302)

    try:
        new_time = datetime.fromisoformat(scheduled_at)
    except ValueError:
        return RedirectResponse(f"/app/tasks/{task_id}", status_code=302)

    task_repo.update_task_scheduled_at(task_id, new_time)
    return RedirectResponse(f"/app/tasks/{task_id}", status_code=302)


# ── Templates ────────────────────────────────────────────────────────

@router.get("/templates", response_class=HTMLResponse)
async def templates_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    tpls = []
    st_where, st_params = _user_filter(user, "st")
    try:
        with get_connection() as conn:
            rows = conn.execute(text(f"""
                SELECT st.id, st.name, st.description, st.timezone, st.is_active,
                       COUNT(ss.id) as slot_count
                FROM schedule_templates st
                LEFT JOIN schedule_template_slots ss ON st.id = ss.template_id
                WHERE {st_where}
                GROUP BY st.id
                ORDER BY st.created_at DESC
            """), st_params).fetchall()
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


@router.get("/templates/new", response_class=HTMLResponse)
async def template_new_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    return templates.TemplateResponse("app_template_new.html", {
        "request": request, "user": user, "active": "templates", "error": None,
    })


@router.post("/templates/new", response_class=HTMLResponse)
async def template_new_submit(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    timezone: str = Form("UTC"),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import template_repo, channel_repo
    project_id = channel_repo.get_default_project_id() or 1

    tid = template_repo.create_template(
        project_id=project_id,
        created_by=user["id"],
        name=name,
        description=description or None,
        timezone=timezone,
    )
    return RedirectResponse(f"/app/templates/{tid}", status_code=302)


@router.get("/templates/{template_id}", response_class=HTMLResponse)
async def template_detail(request: Request, template_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import template_repo
    from sqlalchemy import text

    tpl = template_repo.get_template(template_id)
    if not tpl:
        return RedirectResponse("/app/templates", status_code=302)

    slots = template_repo.get_slots(template_id)

    channels = []
    ch_where, ch_params = _user_filter(user)
    try:
        with get_connection() as conn:
            rows = conn.execute(text(
                f"SELECT id, name FROM platform_channels WHERE enabled = 1 AND {ch_where} ORDER BY name"
            ), ch_params).fetchall()
            channels = [{"id": r[0], "name": r[1]} for r in rows]
    except Exception:
        pass

    day_names = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
                 4: "Friday", 5: "Saturday", 6: "Sunday"}

    return templates.TemplateResponse("app_template_detail.html", {
        "request": request, "user": user, "active": "templates",
        "template": tpl, "slots": slots, "channels": channels,
        "day_names": day_names, "error": None, "message": None,
    })


@router.post("/templates/{template_id}/slots", response_class=HTMLResponse)
async def template_add_slot(
    request: Request,
    template_id: int,
    day_of_week: int = Form(...),
    time_utc: str = Form(...),
    channel_id: int = Form(0),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import template_repo
    template_repo.add_slot(
        template_id=template_id,
        day_of_week=day_of_week,
        time_utc=time_utc,
        channel_id=channel_id if channel_id else None,
    )
    return RedirectResponse(f"/app/templates/{template_id}", status_code=302)


@router.post("/templates/{template_id}/slots/{slot_id}/delete")
async def template_delete_slot(request: Request, template_id: int, slot_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import template_repo
    template_repo.delete_slot(slot_id)
    return RedirectResponse(f"/app/templates/{template_id}", status_code=302)


@router.post("/templates/{template_id}/delete")
async def template_delete(request: Request, template_id: int):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import template_repo
    template_repo.clear_slots(template_id)
    template_repo.delete_template(template_id)
    return RedirectResponse("/app/templates", status_code=302)


# ── Settings ─────────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    return templates.TemplateResponse("app_settings.html", {
        "request": request, "user": user, "active": "settings",
        "message": None, "error": None, "totp_uri": None, "backup_codes": None,
    })


@router.post("/settings/profile", response_class=HTMLResponse)
async def settings_update_profile(
    request: Request,
    display_name: str = Form(""),
    timezone: str = Form(""),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import user_repo
    user_repo.update_profile(user["id"], display_name=display_name or None, timezone=timezone or None)
    user = user_repo.get_user_by_id(user["id"])

    return templates.TemplateResponse("app_settings.html", {
        "request": request, "user": user, "active": "settings",
        "message": "Profile updated successfully", "error": None,
        "totp_uri": None, "backup_codes": None,
    })


@router.post("/settings/2fa/setup", response_class=HTMLResponse)
async def settings_2fa_setup(request: Request):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    if user.get("totp_enabled"):
        return templates.TemplateResponse("app_settings.html", {
            "request": request, "user": user, "active": "settings",
            "message": None, "error": "2FA is already enabled",
            "totp_uri": None, "backup_codes": None,
        })

    import pyotp
    from shared.db.repositories import user_repo

    secret = pyotp.random_base32()
    user_repo.set_totp_secret(user["id"], secret)
    totp_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user["email"], issuer_name="Content Fabric",
    )

    return templates.TemplateResponse("app_settings.html", {
        "request": request, "user": user, "active": "settings",
        "message": None, "error": None,
        "totp_uri": totp_uri, "totp_secret": secret, "backup_codes": None,
    })


@router.post("/settings/2fa/verify", response_class=HTMLResponse)
async def settings_2fa_verify(
    request: Request,
    totp_code: str = Form(...),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    import pyotp
    import secrets
    from shared.db.repositories import user_repo

    user = user_repo.get_user_by_id(user["id"])
    if not user.get("totp_secret"):
        return templates.TemplateResponse("app_settings.html", {
            "request": request, "user": user, "active": "settings",
            "message": None, "error": "Run setup first",
            "totp_uri": None, "backup_codes": None,
        })

    totp = pyotp.TOTP(user["totp_secret"])
    if not totp.verify(totp_code, valid_window=1):
        totp_uri = totp.provisioning_uri(name=user["email"], issuer_name="Content Fabric")
        return templates.TemplateResponse("app_settings.html", {
            "request": request, "user": user, "active": "settings",
            "message": None, "error": "Invalid code, try again",
            "totp_uri": totp_uri, "totp_secret": user["totp_secret"], "backup_codes": None,
        })

    backup_codes = [secrets.token_hex(4) for _ in range(8)]
    user_repo.enable_totp(user["id"], backup_codes)
    user = user_repo.get_user_by_id(user["id"])

    return templates.TemplateResponse("app_settings.html", {
        "request": request, "user": user, "active": "settings",
        "message": "2FA enabled successfully! Save your backup codes.",
        "error": None, "totp_uri": None, "backup_codes": backup_codes,
    })


@router.post("/settings/2fa/disable", response_class=HTMLResponse)
async def settings_2fa_disable(
    request: Request,
    password: str = Form(...),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    if not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse("app_settings.html", {
            "request": request, "user": user, "active": "settings",
            "message": None, "error": "Wrong password",
            "totp_uri": None, "backup_codes": None,
        })

    from shared.db.repositories import user_repo
    user_repo.disable_totp(user["id"])
    user = user_repo.get_user_by_id(user["id"])

    return templates.TemplateResponse("app_settings.html", {
        "request": request, "user": user, "active": "settings",
        "message": "2FA disabled", "error": None,
        "totp_uri": None, "backup_codes": None,
    })


@router.post("/settings/password", response_class=HTMLResponse)
async def settings_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    user, redirect = _require_user(request)
    if redirect:
        return redirect

    ctx = {
        "request": request, "user": user, "active": "settings",
        "message": None, "error": None, "totp_uri": None, "backup_codes": None,
    }

    if not verify_password(current_password, user["password_hash"]):
        ctx["error"] = "Current password is incorrect"
        return templates.TemplateResponse("app_settings.html", ctx)

    if len(new_password) < 6:
        ctx["error"] = "New password must be at least 6 characters"
        return templates.TemplateResponse("app_settings.html", ctx)

    if new_password != confirm_password:
        ctx["error"] = "Passwords do not match"
        return templates.TemplateResponse("app_settings.html", ctx)

    from shared.db.repositories import user_repo
    user_repo.change_password(user["id"], hash_password(new_password))

    ctx["message"] = "Password changed successfully"
    return templates.TemplateResponse("app_settings.html", ctx)


# ── File Upload (portal) ────────────────────────────────────────────

@router.post("/upload/video", response_class=HTMLResponse)
async def portal_upload_video(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload video via portal, return JSON with file path."""
    import os
    import uuid as _uuid
    from pathlib import Path
    from fastapi.responses import JSONResponse

    user = _get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    upload_dir = Path(os.environ.get("UPLOAD_DIR", "/opt/content-fabric/uploads")) / "videos"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "video.mp4").suffix.lower()
    allowed = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"}
    if ext not in allowed:
        return JSONResponse({"error": f"Invalid format: {ext}"}, status_code=400)

    unique_name = f"{_uuid.uuid4().hex}{ext}"
    dest = upload_dir / unique_name

    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    return JSONResponse({"path": str(dest), "filename": file.filename, "size": dest.stat().st_size})


@router.post("/upload/thumbnail", response_class=HTMLResponse)
async def portal_upload_thumbnail(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload thumbnail via portal, return JSON with file path."""
    import os
    import uuid as _uuid
    from pathlib import Path
    from fastapi.responses import JSONResponse

    user = _get_current_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    upload_dir = Path(os.environ.get("UPLOAD_DIR", "/opt/content-fabric/uploads")) / "thumbnails"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "thumb.jpg").suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    if ext not in allowed:
        return JSONResponse({"error": f"Invalid format: {ext}"}, status_code=400)

    unique_name = f"{_uuid.uuid4().hex}{ext}"
    dest = upload_dir / unique_name

    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    return JSONResponse({"path": str(dest), "filename": file.filename, "size": dest.stat().st_size})
