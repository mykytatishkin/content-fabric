from fastapi import APIRouter

from app.api.endpoints import (
    admin, auth, channels, dle_sources, dle_quotes_shorts, logs, news, sora,
    streams, tasks, templates, uploads,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(channels.router, prefix="/channels", tags=["channels"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(templates.router, prefix="/templates", tags=["templates"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
router.include_router(streams.router, prefix="/streams", tags=["streams"])
router.include_router(dle_sources.router, prefix="/dle-sources", tags=["dle-sources"])
router.include_router(dle_quotes_shorts.router, prefix="/dle-quotes-shorts",
                      tags=["dle-quotes-shorts"])
router.include_router(news.router, prefix="/news", tags=["news"])
router.include_router(sora.router, prefix="/sora", tags=["sora"])
router.include_router(logs.router, prefix="/logs", tags=["logs"])
