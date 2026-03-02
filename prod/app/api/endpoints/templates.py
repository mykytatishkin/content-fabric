"""Schedule template endpoints — CRUD for publishing schedules."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.audit import log as audit_log
from shared.db.models import UserStatus

logger = logging.getLogger(__name__)
from app.schemas.template import (
    SlotCreate,
    SlotResponse,
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from shared.db.repositories import template_repo

router = APIRouter()

# Default project_id (single-tenant for now)
_DEFAULT_PROJECT = 1


def _check_template_owner(template_id: int, user: dict) -> dict:
    """Return template dict or raise 404 if not found/not owned."""
    t = template_repo.get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    if user["status"] != UserStatus.ADMIN.value and t.get("created_by") != user["id"]:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


def _slot_to_response(s: dict) -> SlotResponse:
    s = dict(s)
    s["enabled"] = bool(s.get("enabled", True))
    s["time_utc"] = str(s.get("time_utc", ""))
    return SlotResponse(**s)


def _template_to_response(t: dict, slots: list[dict]) -> TemplateResponse:
    t = dict(t)
    t["is_active"] = bool(t.get("is_active", True))
    t["slots"] = [_slot_to_response(s) for s in slots]
    return TemplateResponse(**t)


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(body: TemplateCreate, user: dict = Depends(get_current_user)):
    template_id = template_repo.create_template(
        project_id=_DEFAULT_PROJECT,
        created_by=user["id"],
        name=body.name,
        description=body.description,
        timezone=body.timezone,
    )

    for slot in body.slots:
        template_repo.add_slot(
            template_id=template_id,
            day_of_week=slot.day_of_week,
            time_utc=slot.time_utc,
            channel_id=slot.channel_id,
            media_type=slot.media_type,
        )

    audit_log("template.create", actor_id=user["id"], entity_type="template", entity_id=template_id)
    logger.info("Template created: id=%s name=%s by user=%s (%d slots)", template_id, body.name, user["id"], len(body.slots))
    return _build_response(template_id)


@router.get("/", response_model=TemplateListResponse)
async def list_templates(user: dict = Depends(get_current_user)):
    all_templates = template_repo.list_templates(_DEFAULT_PROJECT)
    if user["status"] != UserStatus.ADMIN.value:
        all_templates = [t for t in all_templates if t.get("created_by") == user["id"]]
    items = []
    for t in all_templates:
        slots = template_repo.get_slots(t["id"])
        items.append(_template_to_response(t, slots))
    return TemplateListResponse(items=items, total=len(items))


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: int, user: dict = Depends(get_current_user)):
    _check_template_owner(template_id, user)
    return _build_response(template_id)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(template_id: int, body: TemplateUpdate, user: dict = Depends(get_current_user)):
    _check_template_owner(template_id, user)

    template_repo.update_template(
        template_id,
        name=body.name,
        description=body.description,
        timezone=body.timezone,
        is_active=body.is_active,
    )
    return _build_response(template_id)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: int, user: dict = Depends(get_current_user)):
    _check_template_owner(template_id, user)
    template_repo.delete_template(template_id)
    audit_log("template.delete", actor_id=user["id"], entity_type="template", entity_id=template_id)
    logger.info("Template deleted: id=%s by user=%s", template_id, user["id"])


@router.post("/{template_id}/slots", response_model=SlotResponse, status_code=status.HTTP_201_CREATED)
async def add_slot(template_id: int, body: SlotCreate, user: dict = Depends(get_current_user)):
    _check_template_owner(template_id, user)

    slot_id = template_repo.add_slot(
        template_id=template_id,
        day_of_week=body.day_of_week,
        time_utc=body.time_utc,
        channel_id=body.channel_id,
        media_type=body.media_type,
    )
    slots = template_repo.get_slots(template_id)
    slot = next((s for s in slots if s["id"] == slot_id), None)
    if not slot:
        raise HTTPException(status_code=500, detail="Slot creation failed")
    return _slot_to_response(slot)


@router.delete("/{template_id}/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_slot(template_id: int, slot_id: int, user: dict = Depends(get_current_user)):
    _check_template_owner(template_id, user)
    if not template_repo.delete_slot(slot_id):
        raise HTTPException(status_code=404, detail="Slot not found")


def _build_response(template_id: int) -> TemplateResponse:
    t = template_repo.get_template(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    slots = template_repo.get_slots(template_id)
    return _template_to_response(t, slots)
