"""Schedule template repository."""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from sqlalchemy import text

from shared.db.connection import get_connection


def create_template(
    project_id: int,
    created_by: int,
    name: str,
    description: str | None = None,
    timezone: str = "UTC",
) -> int:
    new_uuid = str(_uuid.uuid4())
    sql = text(
        "INSERT INTO schedule_templates (uuid, project_id, created_by, name, description, timezone, created_at, updated_at) "
        "VALUES (:uuid, :pid, :uid, :name, :desc, :tz, NOW(), NOW())"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "uuid": new_uuid, "pid": project_id, "uid": created_by,
            "name": name, "desc": description, "tz": timezone,
        })
        return new_uuid


def get_template(template_id: int) -> dict[str, Any] | None:
    sql = text("SELECT * FROM schedule_templates WHERE id = :tid")
    with get_connection() as conn:
        row = conn.execute(sql, {"tid": template_id}).mappings().fetchone()
    return dict(row) if row else None


def get_template_by_uuid(uuid: str) -> dict[str, Any] | None:
    sql = text("SELECT * FROM schedule_templates WHERE uuid = :uuid")
    with get_connection() as conn:
        row = conn.execute(sql, {"uuid": uuid}).mappings().fetchone()
    return dict(row) if row else None


def list_templates(project_id: int) -> list[dict[str, Any]]:
    sql = text("SELECT * FROM schedule_templates WHERE project_id = :pid ORDER BY created_at DESC")
    with get_connection() as conn:
        rows = conn.execute(sql, {"pid": project_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def update_template(template_id: int, name: str | None = None, description: str | None = None,
                    timezone: str | None = None, is_active: bool | None = None) -> bool:
    parts: list[str] = []
    params: dict[str, Any] = {"tid": template_id}
    if name is not None:
        parts.append("name = :name")
        params["name"] = name
    if description is not None:
        parts.append("description = :desc")
        params["desc"] = description
    if timezone is not None:
        parts.append("timezone = :tz")
        params["tz"] = timezone
    if is_active is not None:
        parts.append("is_active = :active")
        params["active"] = int(is_active)
    if not parts:
        return False
    parts.append("updated_at = NOW()")
    sql = text(f"UPDATE schedule_templates SET {', '.join(parts)} WHERE id = :tid")
    with get_connection() as conn:
        result = conn.execute(sql, params)
        return result.rowcount > 0


def delete_template(template_id: int) -> bool:
    sql = text("DELETE FROM schedule_templates WHERE id = :tid")
    with get_connection() as conn:
        result = conn.execute(sql, {"tid": template_id})
        return result.rowcount > 0


# ── Slots ───────────────────────────────────────────────────────────


def add_slot(template_id: int, day_of_week: int, time_utc: str,
             channel_id: int | None = None, media_type: str = "video") -> int:
    sql = text(
        "INSERT INTO schedule_template_slots (template_id, day_of_week, time_utc, channel_id, media_type, created_at) "
        "VALUES (:tid, :dow, :time, :cid, :mt, NOW())"
    )
    with get_connection() as conn:
        result = conn.execute(sql, {
            "tid": template_id, "dow": day_of_week, "time": time_utc,
            "cid": channel_id, "mt": media_type,
        })
        return result.lastrowid


def get_slots(template_id: int) -> list[dict[str, Any]]:
    sql = text(
        "SELECT s.*, pc.uuid AS channel_uuid, pc.name AS channel_name "
        "FROM schedule_template_slots s "
        "LEFT JOIN platform_channels pc ON pc.id = s.channel_id "
        "WHERE s.template_id = :tid ORDER BY s.day_of_week, s.time_utc"
    )
    with get_connection() as conn:
        rows = conn.execute(sql, {"tid": template_id}).mappings().fetchall()
    return [dict(r) for r in rows]


def delete_slot(slot_id: int) -> bool:
    sql = text("DELETE FROM schedule_template_slots WHERE id = :sid")
    with get_connection() as conn:
        result = conn.execute(sql, {"sid": slot_id})
        return result.rowcount > 0


def clear_slots(template_id: int) -> int:
    sql = text("DELETE FROM schedule_template_slots WHERE template_id = :tid")
    with get_connection() as conn:
        result = conn.execute(sql, {"tid": template_id})
        return result.rowcount
