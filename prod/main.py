import logging
import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# ── Centralized logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") == "1" else logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Quiet noisy libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.routes import router
from app.views.panel import router as panel_router
from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app = FastAPI(
    title=settings.APP_NAME,
    description="Content Fabric API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


app.include_router(router, prefix="/api/v1")
app.include_router(panel_router, prefix="/panel", tags=["panel"])


@app.get("/")
async def root():
    return {
        "message": "Content Fabric Channels API",
        "docs": "/docs",
        "channels_form": "/api/v1/channels/form",
        "channels_api": "/api/v1/channels/",
    }


@app.get("/health")
async def health_check():
    """Basic health + dependency checks."""
    checks: dict = {"api": "ok"}

    # MySQL check
    try:
        from shared.db.connection import get_connection
        from sqlalchemy import text
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
        checks["mysql"] = "ok"
    except Exception:
        checks["mysql"] = "error"

    # Redis check
    try:
        from shared.queue.config import get_redis
        r = get_redis()
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}


if __name__ == "__main__":
    import os
    import uvicorn
    debug = os.environ.get("ENV", "production") == "development"
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=debug)
