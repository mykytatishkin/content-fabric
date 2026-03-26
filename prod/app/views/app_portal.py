"""User-facing web portal — SSR pages with cookie-based JWT auth."""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.responses import HTMLResponse

from app.core.auth import (
    COOKIE_NAME,
    is_admin,
    require_user,
    scoped_where,
    user_from_cookie,
)
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

# ── Helpers ──────────────────────────────────────────────────────────


def _set_token_cookie(response, user_id: int):
    import os
    token = create_access_token({"sub": user_id})
    _use_secure = os.environ.get("HTTPS_ENABLED", "").lower() in ("1", "true", "yes")
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, secure=_use_secure, samesite="lax", path="/", max_age=86400,
    )
    return response


# ── Auth Pages (public) ─────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = user_from_cookie(request)
    if user:
        return RedirectResponse("/app/", status_code=302)
    return templates.TemplateResponse("app_login.html", {
        "request": request, "error": None,
    })


@router.post("/login", response_class=HTMLResponse)
@_limiter.limit("10/minute")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    totp_code: str = Form(""),
):
    from shared.db.repositories import user_repo
    user = user_repo.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        logger.warning("Login failed: email=%s (invalid credentials)", email)
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
    logger.info("Login success: user_id=%s email=%s", user["id"], email)
    resp = RedirectResponse("/app/", status_code=302)
    return _set_token_cookie(resp, user["id"])


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = user_from_cookie(request)
    if user:
        return RedirectResponse("/app/", status_code=302)
    return templates.TemplateResponse("app_register.html", {
        "request": request, "error": None,
    })


@router.post("/register", response_class=HTMLResponse)
@_limiter.limit("5/minute")
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
    if len(password) < 8:
        return templates.TemplateResponse("app_register.html", {
            "request": request, "error": "Password must be at least 8 characters",
        })

    uid = user_repo.create_user(
        uuid=str(_uuid.uuid4()),
        username=username,
        email=email,
        password_hash=hash_password(password),
        auth_key=str(_uuid.uuid4()),
        display_name=display_name or username,
    )
    logger.info("User registered: id=%s email=%s username=%s", uid, email, username)
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
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    ctx = {
        "request": request, "user": user, "active": "dashboard",
        "channels_total": 0, "channels_active": 0,
        "tasks_pending": 0, "tasks_completed": 0, "tasks_failed": 0,
        "tasks_processing": 0, "tasks_cancelled": 0, "tasks_total": 0,
        "success_rate": 0, "recent_tasks": [], "upcoming_tasks": [],
    }
    ch_where, ch_params = scoped_where(user)
    t_where, t_params = scoped_where(user, "t")
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
            status_map = {0: "tasks_pending", 1: "tasks_completed", 2: "tasks_failed", 3: "tasks_processing", 4: "tasks_cancelled"}
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
                f"SELECT t.id, t.uuid, t.channel_id, pc.name, pc.uuid, t.title, t.status, "
                f"t.scheduled_at, t.created_at, t.error_message "
                f"FROM content_upload_queue_tasks t "
                f"LEFT JOIN platform_channels pc ON t.channel_id = pc.id "
                f"WHERE {t_where} "
                f"ORDER BY t.created_at DESC LIMIT 10"
            ), t_params).fetchall()
            ctx["recent_tasks"] = [
                {"id": r[0], "uuid": r[1], "channel_id": r[2], "channel_name": r[3] or "?",
                 "channel_uuid": r[4] or "", "title": r[5], "status": r[6],
                 "scheduled_at": r[7], "created_at": r[8], "error_message": r[9]}
                for r in recent
            ]

            upcoming = conn.execute(text(
                f"SELECT t.id, t.uuid, t.channel_id, pc.name, pc.uuid, t.title, t.scheduled_at "
                f"FROM content_upload_queue_tasks t "
                f"LEFT JOIN platform_channels pc ON t.channel_id = pc.id "
                f"WHERE t.status = 0 AND t.scheduled_at > NOW() AND {t_where} "
                f"ORDER BY t.scheduled_at ASC LIMIT 5"
            ), t_params).fetchall()
            ctx["upcoming_tasks"] = [
                {"id": r[0], "uuid": r[1], "channel_id": r[2], "channel_name": r[3] or "?",
                 "channel_uuid": r[4] or "", "title": r[5], "scheduled_at": r[6]}
                for r in upcoming
            ]
    except Exception as e:
        logger.error("Dashboard error: %s", e)

    return templates.TemplateResponse("app_dashboard.html", ctx)


# ── Channels ─────────────────────────────────────────────────────────

@router.get("/channels", response_class=HTMLResponse)
async def channels_page(request: Request):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    ch_where, ch_params = scoped_where(user)
    channels = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text(f"""
                SELECT id, uuid, name, platform_channel_id, enabled, processing_status,
                       access_token IS NOT NULL as has_tokens, created_at,
                       token_expires_at, updated_at
                FROM platform_channels WHERE {ch_where} ORDER BY id
            """), ch_params).fetchall()
            channels = [
                {"id": r[0], "uuid": r[1], "name": r[2], "platform_channel_id": r[3],
                 "enabled": bool(r[4]), "processing_status": bool(r[5]),
                 "has_tokens": bool(r[6]), "created_at": r[7],
                 "token_expires_at": r[8], "updated_at": r[9]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Channels error: %s", e)

    return templates.TemplateResponse("app_channels.html", {
        "request": request, "user": user, "active": "channels", "channels": channels,
    })


@router.get("/channels/add", response_class=HTMLResponse)
async def channel_add_page(request: Request):
    user, redirect = require_user(request)
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
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo, console_repo, credential_repo

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
        credential_repo.add_credentials(
            channel_id=ch_id,
            login_email=login_email,
            login_password=login_password,
            totp_secret=totp_secret or None,
        )

    return RedirectResponse("/app/channels", status_code=302)


# ── OAuth Authorization ──────────────────────────────────────────────

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


@router.get("/channels/{channel_uuid}/authorize")
async def channel_authorize(request: Request, channel_uuid: str):
    """Redirect to Google OAuth consent for channel authorization."""
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo, console_repo

    channel = channel_repo.get_channel_by_uuid(channel_uuid)
    if not channel:
        return RedirectResponse("/app/channels", status_code=302)
    if not is_admin(user) and channel.get("created_by") != user["id"]:
        return RedirectResponse("/app/channels", status_code=302)

    console_id = channel.get("console_id")
    if not console_id:
        return RedirectResponse(
            f"/app/channels/{channel_uuid}?error=no_console",
            status_code=302,
        )

    console = console_repo.get_console_by_id(console_id)
    if not console:
        return RedirectResponse(
            f"/app/channels/{channel_uuid}?error=no_console",
            status_code=302,
        )

    client_id = console.get("client_id")
    client_secret = console.get("client_secret")
    if not client_id or not client_secret:
        return RedirectResponse(
            f"/app/channels/{channel_uuid}?error=no_oauth_creds",
            status_code=302,
        )

    from app.core.config import settings

    base_url = (settings.BASE_URL or str(request.base_url)).rstrip("/")
    redirect_uri = f"{base_url}/app/oauth/callback"

    redirect_to = request.query_params.get("redirect_to", "")
    state_suffix = secrets.token_urlsafe(16)
    state = f"{channel_uuid}_{state_suffix}"
    if redirect_to:
        state = f"{channel_uuid}|{redirect_to}_{state_suffix}"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(OAUTH_SCOPES),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(auth_url, status_code=302)


@router.get("/oauth/callback")
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Handle Google OAuth callback: exchange code for tokens, save to channel, redirect."""
    user, redirect = require_user(request)
    if redirect:
        return redirect

    if error:
        logger.warning("OAuth callback error: %s - %s", error, error_description)
        return RedirectResponse(
            f"/app/channels?error={requests.utils.quote(error_description or error)}",
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse("/app/channels?error=missing_code_or_state", status_code=302)

    # State format: "{channel_uuid}_{random}" or "{channel_uuid}|{redirect_to}_{random}"
    redirect_after = None
    state_main = state.split("_", 1)[0] if state else ""
    if "|" in state_main:
        channel_uuid, redirect_after = state_main.split("|", 1)
    else:
        channel_uuid = state_main

    if not channel_uuid:
        return RedirectResponse("/app/channels?error=invalid_state", status_code=302)

    from shared.db.repositories import channel_repo, console_repo

    channel = channel_repo.get_channel_by_uuid(channel_uuid)
    if not channel:
        return RedirectResponse("/app/channels?error=channel_not_found", status_code=302)
    if not is_admin(user) and channel.get("created_by") != user["id"]:
        return RedirectResponse("/app/channels", status_code=302)

    console_id = channel.get("console_id")
    if not console_id:
        return RedirectResponse(
            f"/app/channels/{channel_uuid}?error=no_console",
            status_code=302,
        )

    console = console_repo.get_console_by_id(console_id)
    if not console:
        return RedirectResponse(
            f"/app/channels/{channel_uuid}?error=no_console",
            status_code=302,
        )

    from app.core.config import settings

    base_url = (settings.BASE_URL or str(request.base_url)).rstrip("/")
    redirect_uri = f"{base_url}/app/oauth/callback"

    token_endpoint = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": console["client_id"],
        "client_secret": console["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    response = requests.post(token_endpoint, data=data, timeout=30)
    if not response.ok:
        logger.error("Token exchange failed: %s", response.text)
        return RedirectResponse(
            f"/app/channels/{channel_uuid}?error=token_exchange_failed",
            status_code=302,
        )

    payload = response.json()
    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")

    if not access_token or not refresh_token:
        logger.warning("OAuth response missing access_token or refresh_token for channel %s", channel_uuid)
        return RedirectResponse(
            f"/app/channels/{channel_uuid}?error=no_refresh_token",
            status_code=302,
        )

    token_expires_at = None
    if expires_in:
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    channel_repo.update_channel_tokens(
        channel_id=channel["id"],
        access_token=access_token,
        refresh_token=refresh_token,
        token_expires_at=token_expires_at,
    )
    logger.info("OAuth tokens saved for channel %s (id=%d)", channel_uuid, channel["id"])

    if redirect_after == "reauth":
        return RedirectResponse(f"/app/reauth?authorized={channel_uuid}", status_code=302)

    return RedirectResponse(
        f"/app/channels/{channel_uuid}?authorized=1",
        status_code=302,
    )


# ── Batch Reauth ─────────────────────────────────────────────────────

@router.get("/reauth", response_class=HTMLResponse)
async def reauth_page(request: Request):
    """Batch re-authorization page: lists channels needing OAuth tokens."""
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    ch_where, ch_params = scoped_where(user, "c")
    channels = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text(f"""
                SELECT c.id, c.uuid, c.name, c.platform_channel_id, c.console_id,
                       c.access_token IS NOT NULL AND c.refresh_token IS NOT NULL as has_tokens,
                       c.token_expires_at, c.enabled
                FROM platform_channels c WHERE {ch_where}
                ORDER BY
                    (c.access_token IS NULL OR c.refresh_token IS NULL) DESC,
                    c.name
            """), ch_params).fetchall()
            channels = [
                {
                    "id": r[0], "uuid": r[1], "name": r[2],
                    "platform_channel_id": r[3], "console_id": r[4],
                    "has_tokens": bool(r[5]), "token_expires_at": r[6],
                    "enabled": bool(r[7]),
                }
                for r in rows
            ]
    except Exception as e:
        logger.error("Reauth page error: %s", e)

    authorized_uuid = request.query_params.get("authorized")

    return templates.TemplateResponse("app_reauth.html", {
        "request": request, "user": user, "active": "reauth",
        "channels": channels, "authorized_uuid": authorized_uuid,
    })


# ── TOTP Credentials Management ─────────────────────────────────────

@router.get("/totp", response_class=HTMLResponse)
async def totp_page(request: Request):
    """Manage TOTP secrets for channel login credentials."""
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    ch_where, ch_params = scoped_where(user, "c")
    channels = []
    try:
        with get_connection() as conn:
            rows = conn.execute(text(f"""
                SELECT c.id, c.uuid, c.name,
                       lc.login_email, lc.totp_secret IS NOT NULL as has_totp,
                       lc.totp_secret, lc.enabled as cred_enabled
                FROM platform_channels c
                LEFT JOIN platform_channel_login_credentials lc ON lc.channel_id = c.id
                WHERE {ch_where}
                ORDER BY c.name
            """), ch_params).fetchall()
            channels = [
                {
                    "id": r[0], "uuid": r[1], "name": r[2],
                    "login_email": r[3], "has_totp": bool(r[4]),
                    "totp_secret_masked": _mask_secret(r[5]) if r[5] else None,
                    "has_credentials": r[3] is not None,
                    "cred_enabled": bool(r[6]) if r[6] is not None else False,
                }
                for r in rows
            ]
    except Exception as e:
        logger.error("TOTP page error: %s", e)

    success = request.query_params.get("success")
    error = request.query_params.get("error")

    return templates.TemplateResponse("app_totp.html", {
        "request": request, "user": user, "active": "totp",
        "channels": channels, "success": success, "error": error,
    })


@router.post("/totp", response_class=HTMLResponse)
@_limiter.limit("30/minute")
async def totp_save(request: Request, channel_id: int = Form(...), totp_secret: str = Form("")):
    """Save or clear TOTP secret for a channel."""
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo, credential_repo

    channel = channel_repo.get_channel_by_id(channel_id)
    if not channel:
        return RedirectResponse("/app/totp?error=Channel+not+found", status_code=302)
    if not is_admin(user) and channel.get("created_by") != user["id"]:
        return RedirectResponse("/app/totp?error=Access+denied", status_code=302)

    totp_secret = totp_secret.strip().replace(" ", "")

    if totp_secret:
        try:
            import pyotp
            pyotp.TOTP(totp_secret).now()
        except Exception:
            return RedirectResponse("/app/totp?error=Invalid+TOTP+secret", status_code=302)

    creds = credential_repo.get_credentials(channel_id, include_disabled=True)
    if not creds:
        return RedirectResponse(
            f"/app/totp?error=No+login+credentials+for+channel+{channel_id}.+Add+email/password+first.",
            status_code=302,
        )

    credential_repo.update_totp_secret(
        channel_id=channel_id,
        totp_secret=totp_secret or None,
    )

    ch_name = channel.get("name", f"#{channel_id}")
    action = "saved" if totp_secret else "cleared"
    logger.info("TOTP secret %s for channel %d (%s) by user %d", action, channel_id, ch_name, user["id"])

    return RedirectResponse(f"/app/totp?success=TOTP+{action}+for+{ch_name}", status_code=302)


def _mask_secret(secret: str) -> str:
    if len(secret) <= 6:
        return "*" * len(secret)
    return secret[:3] + "*" * (len(secret) - 6) + secret[-3:]


@router.get("/channels/{channel_uuid}", response_class=HTMLResponse)
async def channel_detail(request: Request, channel_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import channel_repo
    from sqlalchemy import text

    channel = channel_repo.get_channel_by_uuid(channel_uuid)
    if not channel:
        return RedirectResponse("/app/channels", status_code=302)
    if not is_admin(user) and channel.get("created_by") != user["id"]:
        return RedirectResponse("/app/channels", status_code=302)

    from shared.db.repositories import console_repo, credential_repo

    channel_id = channel["id"]
    stats = {}
    recent_tasks = []
    credentials = None
    console = None
    try:
        # Console info
        if channel.get("console_id"):
            console = console_repo.get_console_by_id(channel["console_id"])

        # Full credentials via credential_repo
        credentials = credential_repo.get_credentials(channel_id, include_disabled=True)

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
                "SELECT id, uuid, title, status, scheduled_at, created_at, error_message "
                "FROM content_upload_queue_tasks WHERE channel_id = :cid "
                "ORDER BY created_at DESC LIMIT 20"
            ), {"cid": channel_id}).fetchall()
            recent_tasks = [
                {"id": r[0], "uuid": r[1], "title": r[2], "status": r[3],
                 "scheduled_at": r[4], "created_at": r[5], "error_message": r[6]}
                for r in task_rows
            ]
    except Exception as e:
        logger.error("Channel detail error: %s", e)

    return templates.TemplateResponse("app_channel_detail.html", {
        "request": request, "user": user, "active": "channels",
        "channel": channel, "stats": stats, "recent_tasks": recent_tasks,
        "credentials": credentials, "console": console,
    })


@router.post("/channels/{channel_uuid}/delete")
async def channel_delete(request: Request, channel_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo
    channel = channel_repo.get_channel_by_uuid(channel_uuid)
    if not channel or (not is_admin(user) and channel.get("created_by") != user["id"]):
        return RedirectResponse("/app/channels", status_code=302)
    channel_repo.delete_channel(channel["id"])
    return RedirectResponse("/app/channels", status_code=302)


@router.get("/channels/{channel_uuid}/edit", response_class=HTMLResponse)
async def channel_edit_page(request: Request, channel_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import channel_repo, console_repo
    from sqlalchemy import text

    channel = channel_repo.get_channel_by_uuid(channel_uuid)
    if not channel:
        return RedirectResponse("/app/channels", status_code=302)
    if not is_admin(user) and channel.get("created_by") != user["id"]:
        return RedirectResponse("/app/channels", status_code=302)

    consoles = console_repo.list_consoles_brief(enabled_only=True)

    credentials = None
    try:
        with get_connection() as conn:
            row = conn.execute(text(
                "SELECT login_email, login_password, totp_secret, proxy_host, enabled "
                "FROM platform_channel_login_credentials WHERE channel_id = :cid"
            ), {"cid": channel["id"]}).fetchone()
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


@router.post("/channels/{channel_uuid}/edit", response_class=HTMLResponse)
async def channel_edit_submit(
    request: Request,
    channel_uuid: str,
    name: str = Form(...),
    enabled: bool = Form(False),
    console_id: str = Form(""),
    login_email: str = Form(""),
    login_password: str = Form(""),
    totp_secret: str = Form(""),
):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import channel_repo, credential_repo

    channel = channel_repo.get_channel_by_uuid(channel_uuid)
    if not channel or (not is_admin(user) and channel.get("created_by") != user["id"]):
        return RedirectResponse("/app/channels", status_code=302)

    channel_id = channel["id"]
    parsed_console_id = int(console_id) if console_id else None
    channel_repo.update_channel(channel_id, name=name.strip(), enabled=enabled, console_id=parsed_console_id)

    if login_email:
        updated = channel_repo.update_login_credentials(
            channel_id, login_email=login_email,
            login_password=login_password or None,
            totp_secret=totp_secret or None,
        )
        if not updated:
            credential_repo.add_credentials(
                channel_id=channel_id,
                login_email=login_email,
                login_password=login_password,
                totp_secret=totp_secret or None,
            )

    return RedirectResponse(f"/app/channels/{channel_uuid}", status_code=302)


# ── Tasks ────────────────────────────────────────────────────────────

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    status_filter = request.query_params.get("status", "")
    channel_filter = request.query_params.get("channel_id", "")

    tasks = []
    stats = {}
    channels = []
    t_where, t_params = scoped_where(user, "t")
    ch_where, ch_params = scoped_where(user)
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
                SELECT t.id, t.uuid, t.channel_id, pc.name, pc.uuid, t.media_type, t.title,
                       t.status, t.scheduled_at, t.created_at, t.error_message,
                       t.completed_at, t.retry_count
                FROM content_upload_queue_tasks t
                LEFT JOIN platform_channels pc ON t.channel_id = pc.id
                WHERE {where}
                ORDER BY t.created_at DESC LIMIT 100
            """), params).fetchall()
            tasks = [
                {"id": r[0], "uuid": r[1], "channel_id": r[2], "channel_name": r[3] or "?",
                 "channel_uuid": r[4] or "", "media_type": r[5], "title": r[6], "status": r[7],
                 "scheduled_at": r[8], "created_at": r[9], "error_message": r[10],
                 "completed_at": r[11], "retry_count": r[12]}
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
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    channels = []
    ch_where, ch_params = scoped_where(user)
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
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import task_repo, channel_repo

    # Validate ownership of channel
    ch = channel_repo.get_channel_by_id(channel_id)
    if not ch or (not is_admin(user) and ch.get("created_by") != user["id"]):
        return RedirectResponse("/app/tasks", status_code=302)

    # Validate file paths (no traversal)
    for path_val in (source_file_path, thumbnail_path):
        if path_val and (".." in path_val or path_val.startswith("/")):
            return RedirectResponse("/app/tasks/new", status_code=302)

    from datetime import datetime, timezone
    scheduled = datetime.now(timezone.utc)
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


@router.post("/tasks/{task_uuid}/cancel")
async def task_cancel(request: Request, task_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import task_repo
    task = task_repo.get_task_by_uuid(task_uuid)
    if not task or (not is_admin(user) and task.get("created_by") != user["id"]):
        return RedirectResponse("/app/tasks", status_code=302)
    task_repo.cancel_task(task["id"])
    return RedirectResponse("/app/tasks", status_code=302)


@router.post("/tasks/{task_uuid}/retry")
async def task_retry(request: Request, task_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import task_repo
    task = task_repo.get_task_by_uuid(task_uuid)
    if not task or (not is_admin(user) and task.get("created_by") != user["id"]):
        return RedirectResponse("/app/tasks", status_code=302)
    task_repo.retry_task(task["id"])
    return RedirectResponse(f"/app/tasks/{task_uuid}", status_code=302)


@router.get("/tasks/{task_uuid}", response_class=HTMLResponse)
async def task_detail(request: Request, task_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import task_repo
    from sqlalchemy import text

    task = task_repo.get_task_by_uuid(task_uuid)
    if not task:
        return RedirectResponse("/app/tasks", status_code=302)
    if not is_admin(user) and task.get("created_by") != user["id"]:
        return RedirectResponse("/app/tasks", status_code=302)

    channel_name = "?"
    channel_uuid = ""
    try:
        with get_connection() as conn:
            row = conn.execute(text(
                "SELECT name, uuid FROM platform_channels WHERE id = :cid"
            ), {"cid": task["channel_id"]}).fetchone()
            if row:
                channel_name = row[0]
                channel_uuid = row[1]
    except Exception:
        pass
    task["channel_name"] = channel_name
    task["channel_uuid"] = channel_uuid

    return templates.TemplateResponse("app_task_detail.html", {
        "request": request, "user": user, "active": "tasks",
        "task": task, "error": None, "message": None,
    })


@router.post("/tasks/{task_uuid}/reschedule", response_class=HTMLResponse)
async def task_reschedule(
    request: Request,
    task_uuid: str,
    scheduled_at: str = Form(...),
):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from datetime import datetime
    from shared.db.repositories import task_repo

    task = task_repo.get_task_by_uuid(task_uuid)
    if not task or (not is_admin(user) and task.get("created_by") != user["id"]):
        return RedirectResponse("/app/tasks", status_code=302)

    try:
        new_time = datetime.fromisoformat(scheduled_at)
    except ValueError:
        return RedirectResponse(f"/app/tasks/{task_uuid}", status_code=302)

    task_repo.update_task_scheduled_at(task["id"], new_time)
    return RedirectResponse(f"/app/tasks/{task_uuid}", status_code=302)


# ── Templates ────────────────────────────────────────────────────────

@router.get("/templates", response_class=HTMLResponse)
async def templates_page(request: Request):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    tpls = []
    st_where, st_params = scoped_where(user, "st")
    try:
        with get_connection() as conn:
            rows = conn.execute(text(f"""
                SELECT st.id, st.uuid, st.name, st.description, st.timezone, st.is_active,
                       COUNT(ss.id) as slot_count
                FROM schedule_templates st
                LEFT JOIN schedule_template_slots ss ON st.id = ss.template_id
                WHERE {st_where}
                GROUP BY st.id
                ORDER BY st.created_at DESC
            """), st_params).fetchall()
            tpls = [
                {"id": r[0], "uuid": r[1], "name": r[2], "description": r[3],
                 "timezone": r[4], "is_active": bool(r[5]), "slot_count": r[6]}
                for r in rows
            ]
    except Exception as e:
        logger.error("Templates error: %s", e)

    return templates.TemplateResponse("app_templates.html", {
        "request": request, "user": user, "active": "templates", "templates_list": tpls,
    })


@router.get("/templates/new", response_class=HTMLResponse)
async def template_new_page(request: Request):
    user, redirect = require_user(request)
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
    user, redirect = require_user(request)
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
    tpl = template_repo.get_template(tid)
    return RedirectResponse(f"/app/templates/{tpl['uuid']}" if tpl else "/app/templates", status_code=302)


@router.get("/templates/{template_uuid}", response_class=HTMLResponse)
async def template_detail(request: Request, template_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from shared.db.repositories import template_repo
    from sqlalchemy import text

    tpl = template_repo.get_template_by_uuid(template_uuid)
    if not tpl:
        return RedirectResponse("/app/templates", status_code=302)
    if not is_admin(user) and tpl.get("created_by") != user["id"]:
        return RedirectResponse("/app/templates", status_code=302)

    slots = template_repo.get_slots(tpl["id"])

    channels = []
    ch_where, ch_params = scoped_where(user)
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


@router.post("/templates/{template_uuid}/slots", response_class=HTMLResponse)
async def template_add_slot(
    request: Request,
    template_uuid: str,
    day_of_week: int = Form(...),
    time_utc: str = Form(...),
    channel_id: int = Form(0),
):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import template_repo
    tpl = template_repo.get_template_by_uuid(template_uuid)
    if not tpl:
        return RedirectResponse("/app/templates", status_code=302)
    if not is_admin(user) and tpl.get("created_by") != user["id"]:
        return RedirectResponse("/app/templates", status_code=302)
    template_repo.add_slot(
        template_id=tpl["id"],
        day_of_week=day_of_week,
        time_utc=time_utc,
        channel_id=channel_id if channel_id else None,
    )
    return RedirectResponse(f"/app/templates/{template_uuid}", status_code=302)


@router.post("/templates/{template_uuid}/slots/{slot_id}/delete")
async def template_delete_slot(request: Request, template_uuid: str, slot_id: int):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import template_repo
    tpl = template_repo.get_template_by_uuid(template_uuid)
    if not tpl:
        return RedirectResponse("/app/templates", status_code=302)
    if not is_admin(user) and tpl.get("created_by") != user["id"]:
        return RedirectResponse("/app/templates", status_code=302)
    template_repo.delete_slot(slot_id)
    return RedirectResponse(f"/app/templates/{template_uuid}", status_code=302)


@router.post("/templates/{template_uuid}/delete")
async def template_delete(request: Request, template_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect

    from shared.db.repositories import template_repo
    tpl = template_repo.get_template_by_uuid(template_uuid)
    if not tpl:
        return RedirectResponse("/app/templates", status_code=302)
    if not is_admin(user) and tpl.get("created_by") != user["id"]:
        return RedirectResponse("/app/templates", status_code=302)
    template_repo.clear_slots(tpl["id"])
    template_repo.delete_template(tpl["id"])
    return RedirectResponse("/app/templates", status_code=302)


# ── Settings ─────────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    user, redirect = require_user(request)
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
    user, redirect = require_user(request)
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
    user, redirect = require_user(request)
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
    user, redirect = require_user(request)
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

    backup_codes = [secrets.token_hex(6) for _ in range(8)]
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
    user, redirect = require_user(request)
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
    user, redirect = require_user(request)
    if redirect:
        return redirect

    ctx = {
        "request": request, "user": user, "active": "settings",
        "message": None, "error": None, "totp_uri": None, "backup_codes": None,
    }

    if not verify_password(current_password, user["password_hash"]):
        ctx["error"] = "Current password is incorrect"
        return templates.TemplateResponse("app_settings.html", ctx)

    if len(new_password) < 8:
        ctx["error"] = "New password must be at least 8 characters"
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

    user = user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    upload_dir = Path(os.environ.get("UPLOAD_DIR", "/opt/content-fabric/uploads")) / "videos"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "video.mp4").suffix.lower()
    allowed = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v"}
    if ext not in allowed:
        return JSONResponse({"error": f"Invalid format: {ext}"}, status_code=400)

    MAX_VIDEO_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB
    unique_name = f"{_uuid.uuid4().hex}{ext}"
    dest = upload_dir / unique_name

    total = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_VIDEO_SIZE:
                dest.unlink(missing_ok=True)
                return JSONResponse({"error": "File too large (max 10 GB)"}, status_code=400)
            f.write(chunk)

    return JSONResponse({"path": str(dest.name), "filename": file.filename, "size": dest.stat().st_size})


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

    user = user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    upload_dir = Path(os.environ.get("UPLOAD_DIR", "/opt/content-fabric/uploads")) / "thumbnails"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "thumb.jpg").suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    if ext not in allowed:
        return JSONResponse({"error": f"Invalid format: {ext}"}, status_code=400)

    MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB
    unique_name = f"{_uuid.uuid4().hex}{ext}"
    dest = upload_dir / unique_name

    total = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_IMAGE_SIZE:
                dest.unlink(missing_ok=True)
                return JSONResponse({"error": "File too large (max 50 MB)"}, status_code=400)
            f.write(chunk)

    return JSONResponse({"path": str(dest.name), "filename": file.filename, "size": dest.stat().st_size})
