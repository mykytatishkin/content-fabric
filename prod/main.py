import logging
import os

from shared.logging_config import setup_logging

setup_logging(service_name="cff-api")

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.api.routes import router
from app.views.panel import router as panel_router
from app.views.app_portal import router as app_portal_router
from app.core.config import settings

import time as _time
_app_start_time = _time.time()

limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


_is_dev = os.environ.get("ENV", "production") == "development"
app = FastAPI(
    title=settings.APP_NAME,
    description="Content Fabric API",
    version="1.0.0",
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    openapi_url="/openapi.json" if _is_dev else None,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


_request_logger = logging.getLogger("cff.requests")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    import time
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)
    if not request.url.path.startswith("/health"):
        _request_logger.info(
            "%s %s → %d (%dms)",
            request.method, request.url.path, response.status_code, duration_ms,
        )
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    _request_logger.warning("Rate limit exceeded: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


from starlette.staticfiles import StaticFiles
import pathlib
_static_dir = pathlib.Path(__file__).parent / "app" / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(router, prefix="/api/v1")
app.include_router(panel_router, prefix="/panel", tags=["panel"])
app.include_router(app_portal_router, prefix="/app", tags=["portal"])


@app.get("/")
async def root():
    return {"message": "Content Fabric API", "status": "running"}


@app.get("/health")
async def health_check(request: Request):
    """Health check. Full details only for admin (cookie auth)."""
    import time
    from app.core.auth import user_from_cookie, is_admin
    _user = user_from_cookie(request)
    _show_details = _user is not None and is_admin(_user)

    checks: dict = {"api": "ok"}
    details: dict = {}

    # MySQL check
    try:
        from shared.db.connection import get_connection
        from sqlalchemy import text
        t0 = time.time()
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
        checks["mysql"] = "ok"
        details["mysql_latency_ms"] = round((time.time() - t0) * 1000, 1)
    except Exception as e:
        checks["mysql"] = "error"
        details["mysql_error"] = str(e)[:200]

    # Redis check
    try:
        from shared.queue.config import get_redis
        t0 = time.time()
        r = get_redis()
        r.ping()
        checks["redis"] = "ok"
        details["redis_latency_ms"] = round((time.time() - t0) * 1000, 1)
        # Queue sizes
        details["queues"] = {
            "publishing": r.llen("rq:queue:publishing"),
            "notifications": r.llen("rq:queue:notifications"),
            "voice": r.llen("rq:queue:voice"),
            "failed": r.llen("rq:queue:failed"),
        }
    except Exception as e:
        checks["redis"] = "error"
        details["redis_error"] = str(e)[:200]

    # Disk check
    try:
        import shutil
        disk = shutil.disk_usage("/")
        details["disk"] = {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "used_pct": round(disk.used / disk.total * 100, 1),
        }
        if disk.free / disk.total < 0.1:
            checks["disk"] = "warning"
        else:
            checks["disk"] = "ok"
    except Exception:
        checks["disk"] = "unknown"

    # Memory check
    try:
        import psutil
        mem = psutil.virtual_memory()
        details["memory"] = {
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "available_gb": round(mem.available / (1024**3), 1),
            "used_pct": mem.percent,
        }
        proc = psutil.Process()
        details["process"] = {
            "pid": proc.pid,
            "memory_mb": round(proc.memory_info().rss / (1024**2), 1),
            "cpu_pct": proc.cpu_percent(interval=0),
            "threads": proc.num_threads(),
        }
    except ImportError:
        pass
    except Exception:
        pass

    # Uptime
    details["uptime_seconds"] = round(time.time() - _app_start_time, 0)

    status = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    if _show_details:
        return {"status": status, "checks": checks, "details": details}
    return {"status": status}


if __name__ == "__main__":
    import os
    import uvicorn
    debug = os.environ.get("ENV", "production") == "development"
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=debug)
