"""Admin endpoints — system overview, user management, queue status."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from shared.db.connection import get_connection
from sqlalchemy import text

router = APIRouter()


def _require_admin(user: dict) -> dict:
    """Check that the current user has admin status (status=1)."""
    # status=1 is admin in platform_users
    if user.get("status") != 1:
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

    status_names = {0: "pending", 1: "completed", 2: "failed", 3: "processing", 4: "cancelled"}
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

    if new_status not in (0, 1, 10):
        raise HTTPException(status_code=400, detail="Invalid status (0=inactive, 1=admin, 10=active)")

    sql = text("UPDATE platform_users SET status = :status WHERE id = :uid")
    with get_connection() as conn:
        result = conn.execute(sql, {"status": new_status, "uid": user_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "user_id": user_id, "new_status": new_status}
