"""SSR admin panel — Jinja2 server-side rendered pages (admin-only)."""

import logging
from pathlib import Path

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from app.core.auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter()

_templates_dir = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


@router.get("/")
async def dashboard(request: Request):
    user, redirect = require_admin(request)
    if redirect:
        return redirect

    from shared.db.connection import get_connection
    from sqlalchemy import text

    ctx = {
        "request": request, "active": "dashboard",
        "channels_total": 0, "channels_active": 0, "users_total": 0,
        "tasks_pending": 0, "tasks_completed": 0, "tasks_failed": 0,
        "tasks_processing": 0, "tasks_cancelled": 0, "tasks_total": 0,
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
            status_map = {0: "tasks_pending", 1: "tasks_completed", 2: "tasks_failed", 3: "tasks_processing", 4: "tasks_cancelled"}
            total = 0
            for r in rows:
                key = status_map.get(r[0])
                if key:
                    ctx[key] = r[1]
                total += r[1]
            ctx["tasks_total"] = total

            # Recent failures
            failures = conn.execute(text(
                "SELECT id, channel_id, title, error_message, COALESCE(completed_at, created_at) as completed_at "
                "FROM content_upload_queue_tasks WHERE status = 2 "
                "ORDER BY id DESC LIMIT 10"
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
    user, redirect = require_admin(request)
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
    user, redirect = require_admin(request)
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
    user, redirect = require_admin(request)
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
    user, redirect = require_admin(request)
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
    user, redirect = require_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse("payment.html", {
        "request": request, "active": "payment",
    })


@router.get("/health")
async def health_page(request: Request):
    user, redirect = require_admin(request)
    if redirect:
        return redirect

    import shutil
    import time

    checks = {}
    queues = {}
    disk = {}
    memory = {}
    process_info = {}

    # MySQL
    try:
        from shared.db.connection import get_connection
        from sqlalchemy import text
        t0 = time.time()
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
        checks["MySQL"] = {"status": "ok", "latency_ms": round((time.time() - t0) * 1000, 1)}
    except Exception as e:
        checks["MySQL"] = {"status": "error", "error": str(e)[:200]}

    # Redis
    try:
        from shared.queue.config import get_redis
        t0 = time.time()
        r = get_redis()
        r.ping()
        checks["Redis"] = {"status": "ok", "latency_ms": round((time.time() - t0) * 1000, 1)}
        queues = {
            "publishing": r.llen("rq:queue:publishing"),
            "notifications": r.llen("rq:queue:notifications"),
            "voice": r.llen("rq:queue:voice"),
            "failed": r.llen("rq:queue:failed"),
        }
    except Exception as e:
        checks["Redis"] = {"status": "error", "error": str(e)[:200]}

    # Disk
    try:
        d = shutil.disk_usage("/")
        disk = {
            "total_gb": round(d.total / (1024**3), 1),
            "used_gb": round(d.used / (1024**3), 1),
            "free_gb": round(d.free / (1024**3), 1),
            "used_pct": round(d.used / d.total * 100, 1),
        }
    except Exception:
        pass

    # Memory + Process
    try:
        import psutil
        mem = psutil.virtual_memory()
        memory = {
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "used_pct": mem.percent,
        }
        proc = psutil.Process()
        process_info = {
            "pid": proc.pid,
            "memory_mb": round(proc.memory_info().rss / (1024**2), 1),
            "cpu_pct": proc.cpu_percent(interval=0),
            "threads": proc.num_threads(),
        }
    except ImportError:
        pass
    except Exception:
        pass

    # Systemd services
    services = []
    try:
        import subprocess
        for svc_name in ["cff-api", "cff-scheduler", "cff-publishing-worker", "cff-notification-worker", "cff-voice-worker"]:
            try:
                result = subprocess.run(
                    ["systemctl", "show", svc_name, "--property=ActiveState,MemoryCurrent,ExecMainStartTimestamp"],
                    capture_output=True, text=True, timeout=5,
                )
                props = dict(line.split("=", 1) for line in result.stdout.strip().split("\n") if "=" in line)
                mem_bytes = int(props.get("MemoryCurrent", 0))
                services.append({
                    "name": svc_name,
                    "active": props.get("ActiveState", "unknown"),
                    "memory": f"{round(mem_bytes / (1024**2), 1)} MB" if mem_bytes > 0 else None,
                    "uptime": props.get("ExecMainStartTimestamp", "")[:19] or None,
                })
            except Exception:
                services.append({"name": svc_name, "active": "unknown", "memory": None, "uptime": None})
    except Exception:
        pass

    # Uptime
    from main import _app_start_time
    uptime_sec = int(time.time() - _app_start_time)
    hours, remainder = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    overall = "healthy" if all(c.get("status") == "ok" for c in checks.values()) else "degraded"

    return templates.TemplateResponse("health.html", {
        "request": request, "active": "health",
        "status": overall, "uptime": uptime_str,
        "checks": checks, "queues": queues,
        "disk": disk, "memory": memory, "process": process_info,
        "services": services,
    })


@router.get("/logs")
async def logs_page(request: Request):
    user, redirect = require_admin(request)
    if redirect:
        return redirect

    available_services = [
        "cff-api", "cff-scheduler", "cff-publishing-worker",
        "cff-notification-worker", "cff-voice-worker",
    ]

    service = request.query_params.get("service", "cff-api")
    if service not in available_services:
        service = "cff-api"
    level = request.query_params.get("level", "all")
    try:
        lines = min(int(request.query_params.get("lines", "200")), 1000)
    except (ValueError, TypeError):
        lines = 200

    log_lines = []
    try:
        import subprocess
        cmd = ["journalctl", "-u", service, "--no-pager", "-n", str(lines), "--output=short-iso"]
        if level == "ERROR":
            cmd.extend(["-p", "err"])
        elif level == "WARNING":
            cmd.extend(["-p", "warning"])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        raw_lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        # Filter by Python log level if needed (journalctl -p only filters syslog levels)
        if level in ("ERROR", "WARNING", "INFO") and not any("-p" in c for c in cmd[4:]):
            log_lines = [l for l in raw_lines if f" {level} " in l or (level == "WARNING" and " ERROR " in l)]
        else:
            log_lines = raw_lines
    except Exception as e:
        log_lines = [f"Error reading logs: {e}"]

    error_count = sum(1 for l in log_lines if " ERROR " in l)
    warning_count = sum(1 for l in log_lines if " WARNING " in l)

    return templates.TemplateResponse("logs.html", {
        "request": request, "active": "logs",
        "log_lines": log_lines,
        "available_services": available_services,
        "current_service": service,
        "current_level": level,
        "lines": lines,
        "error_count": error_count,
        "warning_count": warning_count,
    })


# ── Broadcast ─────────────────────────────────────────────────────

@router.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request):
    user, redirect = require_admin(request)
    if redirect:
        return redirect

    from shared.db.repositories import notification_repo
    from shared.db.connection import get_connection
    from sqlalchemy import text as sql_text

    # Get recent broadcasts
    with get_connection() as conn:
        rows = conn.execute(sql_text(
            "SELECT title, message, created_at FROM notifications "
            "WHERE type = 'broadcast' GROUP BY title, message, created_at "
            "ORDER BY created_at DESC LIMIT 20"
        )).fetchall()
    recent = [{"title": r[0], "message": r[1], "created_at": r[2]} for r in rows]

    return templates.TemplateResponse("broadcast.html", {
        "request": request, "active": "broadcast",
        "message": None, "error": None, "recent": recent,
    })


@router.post("/broadcast", response_class=HTMLResponse)
async def broadcast_send(
    request: Request,
    title: str = Form(...),
    message: str = Form(""),
):
    user, redirect = require_admin(request)
    if redirect:
        return redirect

    from shared.db.repositories import notification_repo

    title = title.strip()
    if not title:
        return templates.TemplateResponse("broadcast.html", {
            "request": request, "active": "broadcast",
            "message": None, "error": "Title is required", "recent": [],
        })

    count = notification_repo.broadcast(title, message.strip() or None)

    return templates.TemplateResponse("broadcast.html", {
        "request": request, "active": "broadcast",
        "message": f"Broadcast sent to {count} users", "error": None, "recent": [],
    })
