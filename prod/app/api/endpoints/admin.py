"""Admin endpoints — system overview, user management, queue status."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from shared.db.connection import get_connection
from shared.db.models import TaskStatus, UserStatus
from sqlalchemy import text

router = APIRouter()


def _require_admin(user: dict) -> dict:
    """Check that the current user has admin status (status=1)."""
    # status=1 is admin in platform_users
    if user.get("status") != UserStatus.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/dashboard")
async def admin_dashboard(user: dict = Depends(get_current_user)):
    """Overview of system state — users, channels, tasks, queues."""
    _require_admin(user)

    with get_connection() as conn:
        users_count = conn.execute(text("SELECT COUNT(*) FROM platform_users")).scalar()
        channels_count = conn.execute(text("SELECT COUNT(*) FROM platform_channels")).scalar()
        active_channels = conn.execute(text("SELECT COUNT(*) FROM platform_channels WHERE enabled = 1")).scalar()

        task_stats = conn.execute(text(
            "SELECT status, COUNT(*) FROM content_upload_queue_tasks GROUP BY status"
        )).fetchall()

        recent_errors = conn.execute(text(
            "SELECT id, channel_id, title, error_message, completed_at "
            "FROM content_upload_queue_tasks WHERE status = 2 "
            "ORDER BY completed_at DESC LIMIT 10"
        )).mappings().fetchall()

    status_names = {s.value: s.name.lower() for s in TaskStatus}
    tasks = {status_names.get(r[0], f"unknown_{r[0]}"): r[1] for r in task_stats}

    return {
        "users": {"total": users_count},
        "channels": {"total": channels_count, "active": active_channels},
        "tasks": tasks,
        "recent_errors": [dict(r) for r in recent_errors],
    }


@router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    """List all platform users."""
    _require_admin(user)

    sql = text(
        "SELECT id, uuid, username, email, display_name, status, totp_enabled, "
        "last_login_at, created_at FROM platform_users ORDER BY id"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return {"users": [dict(r) for r in rows]}


@router.get("/queue")
async def queue_status(user: dict = Depends(get_current_user)):
    """Redis queue status — job counts per queue."""
    _require_admin(user)

    try:
        from shared.queue.config import get_redis, QUEUE_PUBLISHING, QUEUE_NOTIFICATIONS, QUEUE_VOICE
        r = get_redis()
        return {
            "publishing": r.llen(f"rq:queue:{QUEUE_PUBLISHING}"),
            "notifications": r.llen(f"rq:queue:{QUEUE_NOTIFICATIONS}"),
            "voice": r.llen(f"rq:queue:{QUEUE_VOICE}"),
            "failed": r.llen("rq:queue:failed"),
        }
    except Exception as e:
        return {"error": "Redis not available", "detail": str(e)}


@router.get("/consoles")
async def list_consoles(user: dict = Depends(get_current_user)):
    """List all OAuth consoles with channel counts."""
    _require_admin(user)

    sql = text(
        "SELECT c.id, c.name, c.platform, c.cloud_project_id, c.enabled, c.created_at, "
        "COUNT(ch.id) as channel_count "
        "FROM platform_oauth_credentials c "
        "LEFT JOIN platform_channels ch ON ch.console_id = c.id "
        "GROUP BY c.id ORDER BY c.id"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).mappings().fetchall()
    return {"consoles": [dict(r) for r in rows]}


@router.post("/users/{user_id}/status")
async def update_user_status(user_id: int, new_status: int, user: dict = Depends(get_current_user)):
    """Change user status (activate/deactivate)."""
    _require_admin(user)

    valid_statuses = {s.value for s in UserStatus}
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {', '.join(f'{s.value}={s.name.lower()}' for s in UserStatus)}")

    sql = text("UPDATE platform_users SET status = :status WHERE id = :uid")
    with get_connection() as conn:
        result = conn.execute(sql, {"status": new_status, "uid": user_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user_id": user_id, "new_status": new_status}


# ── Credential / TOTP management ──────────────────────────────────


@router.get("/credentials")
async def list_credentials(user: dict = Depends(get_current_user)):
    """List all channel login credentials (passwords masked)."""
    _require_admin(user)

    from shared.db.repositories import credential_repo
    creds = credential_repo.list_credentials()
    for c in creds:
        c["login_password"] = "***"  # never expose
        if c.get("proxy_password"):
            c["proxy_password"] = "***"
    return {"credentials": creds}


@router.post("/credentials/{channel_id}/totp")
async def set_totp_secret(
    channel_id: int,
    totp_secret: str,
    user: dict = Depends(get_current_user),
):
    """Set TOTP secret for a channel's RPA credentials."""
    _require_admin(user)

    from shared.db.repositories import credential_repo
    existing = credential_repo.get_credentials(channel_id, include_disabled=True)
    if not existing:
        raise HTTPException(status_code=404, detail="No credentials for this channel")

    credential_repo.update_totp_secret(channel_id, totp_secret)
    return {"ok": True, "channel_id": channel_id, "totp_set": True}


@router.get("/reauth-status")
async def reauth_status(user: dict = Depends(get_current_user)):
    """Show channels needing re-auth (expired/revoked tokens) and MFA status."""
    _require_admin(user)

    sql = text(
        "SELECT c.id, c.name, c.enabled, c.token_expires_at, "
        "cl.login_email, "
        "IF(cl.totp_secret IS NOT NULL AND cl.totp_secret != '', 1, 0) as has_totp, "
        "cl.last_success_at, cl.last_error "
        "FROM platform_channels c "
        "LEFT JOIN platform_channel_login_credentials cl ON cl.channel_id = c.id "
        "WHERE cl.id IS NOT NULL "
        "ORDER BY c.id"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).mappings().fetchall()

    channels = []
    for r in rows:
        d = dict(r)
        d["has_totp"] = bool(d.get("has_totp"))
        channels.append(d)
    return {"channels": channels}
