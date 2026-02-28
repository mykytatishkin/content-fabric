from fastapi import APIRouter

from app.api.endpoints import admin, auth, channels, tasks, templates, uploads

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(channels.router, prefix="/channels", tags=["channels"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(templates.router, prefix="/templates", tags=["templates"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
