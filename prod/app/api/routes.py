from fastapi import APIRouter

from app.api.endpoints import channels, items

router = APIRouter()

router.include_router(items.router, prefix="/items", tags=["items"])
router.include_router(channels.router, prefix="/channels", tags=["channels"])
