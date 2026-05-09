import logging
import os

from shared.logging_config import setup_logging
from shared.error_tracking import init as init_error_tracking

setup_logging(service_name="cff-api")
init_error_tracking(service_name="cff-api")

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
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
        # CSP: 'unsafe-eval' removed — no runtime eval in app code. 'unsafe-inline'
        # remains for styles+scripts because templates rely on inline <style>/<script>.
        # frame-ancestors 'none' supersedes X-Frame-Options for modern browsers.
        # form-action 'self' blocks form-submission to external origins (CSRF defence-in-depth).
        # base-uri 'self' blocks <base> tag injection.
        # object-src 'none' blocks Flash/legacy plugins.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # HSTS: 2y + includeSubDomains + preload (only takes effect when served over HTTPS;
        # browsers ignore on plain HTTP responses).
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """Origin/Referer-based CSRF protection for cookie-authenticated forms.

    For state-changing methods on cookie-auth endpoints, require that
    Origin (or Referer) matches the request's Host. Browsers always send
    Origin on cross-origin POST, so an attacker on evil.com cannot forge
    a request that looks same-origin.

    Skipped for:
      - Safe methods (GET/HEAD/OPTIONS).
      - Bearer-token auth (CLI/API clients) — no cookie ⇒ no CSRF
        vector, and forcing Origin on machine clients is impractical.
      - /api/v1/auth/login — login is the bootstrap; no cookie yet.
    """

    SAFE = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next):
        if request.method in self.SAFE:
            return await call_next(request)

        # Bearer-token clients (machine-to-machine) bypass — they can't
        # be CSRF'd because attacker can't read Authorization header from
        # another origin.
        if request.headers.get("authorization", "").lower().startswith("bearer "):
            return await call_next(request)

        # No cookie ⇒ no CSRF surface (login bootstrap, anonymous POSTs).
        if not request.cookies.get("cff_token"):
            return await call_next(request)

        host = request.headers.get("host", "")
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        def _same_host(url: str) -> bool:
            if not url or not host:
                return False
            for prefix in (f"http://{host}", f"https://{host}"):
                if url == prefix or url.startswith(prefix + "/"):
                    return True
            return False

        if origin:
            if not _same_host(origin):
                logging.getLogger("cff.csrf").warning(
                    "CSRF reject: method=%s path=%s origin=%s host=%s",
                    request.method, request.url.path, origin, host,
                )
                return JSONResponse(
                    {"detail": "CSRF: cross-origin POST rejected"},
                    status_code=403,
                )
        elif referer:
            if not _same_host(referer):
                logging.getLogger("cff.csrf").warning(
                    "CSRF reject: method=%s path=%s referer=%s host=%s",
                    request.method, request.url.path, referer, host,
                )
                return JSONResponse(
                    {"detail": "CSRF: cross-origin referer"},
                    status_code=403,
                )
        # No Origin and no Referer → most browsers send at least one for
        # POST. Refuse to be safe (curl etc. should use Bearer auth).
        else:
            logging.getLogger("cff.csrf").warning(
                "CSRF reject: method=%s path=%s — no Origin/Referer header",
                request.method, request.url.path,
            )
            return JSONResponse(
                {"detail": "CSRF: missing Origin/Referer header"},
                status_code=403,
            )

        return await call_next(request)


class TraceContextMiddleware(BaseHTTPMiddleware):
    """Bind a trace_id to every incoming HTTP request + log access.

    Doing both in one middleware (instead of two) is critical: ContextVars
    set in an inner middleware are NOT visible from an outer one, because
    starlette wraps each middleware in its own asyncio Task scope. So we
    set trace_id AND log the request from the same dispatch.

    trace_id is taken from X-Trace-Id header (so external callers can
    correlate their request with our logs) or generated fresh. The same id
    is echoed back in X-Trace-Id response header and attached to every log
    line emitted while handling the request.
    """

    _request_logger = logging.getLogger("cff.requests")

    async def dispatch(self, request: Request, call_next):
        from shared.logging_context import new_trace_id, set_trace_id, set_worker
        import time as _time

        incoming = request.headers.get("X-Trace-Id", "").strip()
        trace_id = incoming if incoming else new_trace_id()
        set_trace_id(trace_id)
        set_worker("cff-api")
        request.state.trace_id = trace_id

        start = _time.time()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_ms = int((_time.time() - start) * 1000)
            self._request_logger.exception(
                "%s %s → EXC (%dms)",
                request.method, request.url.path, duration_ms,
            )
            raise

        duration_ms = int((_time.time() - start) * 1000)
        if not request.url.path.startswith("/health") and not request.url.path == "/metrics":
            self._request_logger.info(
                "%s %s → %d (%dms)",
                request.method, request.url.path, response.status_code, duration_ms,
            )
        response.headers["X-Trace-Id"] = trace_id
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
app.add_middleware(CSRFMiddleware)
app.add_middleware(TraceContextMiddleware)

# ─── SessionMiddleware (cookie-signed sessions, used for flash messages) ───
# Starlette adds middleware in reverse order, so registering this AFTER
# CSRFMiddleware means it sits *inside* CSRF (closer to the handler) — the
# session is decoded only after Origin/Referer checks pass. Keep it after
# TraceContext too so trace_id is bound for any session-related logging.
_session_secret = (
    os.environ.get("CFF_SESSION_SECRET")
    or os.environ.get("JWT_SECRET_KEY")
    or "cff-dev-session-secret-change-me"
)
_session_https_only = os.environ.get("ENV", "production") == "production" and (
    os.environ.get("HTTPS_ENABLED", "").lower() in ("1", "true", "yes")
)
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    https_only=_session_https_only,
    same_site="lax",
    session_cookie="cff_session",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
)


# NB: request logging now happens inside TraceContextMiddleware so the
# log line carries the trace_id ContextVar (which would be invisible from
# an outer @app.middleware decorator).
_request_logger = logging.getLogger("cff.requests")


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    _request_logger.warning("Rate limit exceeded: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.templating import Jinja2Templates as _Jinja2Templates
import pathlib

_error_templates = _Jinja2Templates(
    directory=str(pathlib.Path(__file__).parent / "app" / "templates")
)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        # JSON for API requests
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return _error_templates.TemplateResponse(
            "404.html",
            {"request": request, "path": request.url.path},
            status_code=404,
        )
    if exc.status_code == 500:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


from starlette.staticfiles import StaticFiles
from starlette.responses import FileResponse, PlainTextResponse
_static_dir = pathlib.Path(__file__).parent / "app" / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def _favicon():
    fav = _static_dir / "favicon.svg"
    if fav.is_file():
        return FileResponse(fav, media_type="image/svg+xml")
    return PlainTextResponse("", status_code=204)


@app.get("/robots.txt", include_in_schema=False)
async def _robots():
    rb = _static_dir / "robots.txt"
    if rb.is_file():
        return FileResponse(rb, media_type="text/plain")
    return PlainTextResponse("User-agent: *\nDisallow: /\n", media_type="text/plain")

app.include_router(router, prefix="/api/v1")
app.include_router(panel_router, prefix="/panel", tags=["panel"])
app.include_router(app_portal_router, prefix="/app", tags=["portal"])


# ─── Register `get_flashes` as a Jinja global on every Jinja2Templates ───
# Two router modules (app_portal, panel) each instantiate their own
# Jinja2Templates pointing at the same template dir. Inject the helper
# into both so {% for cat, msg in get_flashes(request) %} works in any
# template, regardless of which router rendered it.
try:
    from app.core.flash import get_flashes as _get_flashes
    from app.views.app_portal import templates as _portal_templates
    from app.views.panel import templates as _panel_templates

    for _t in (_portal_templates, _panel_templates, _error_templates):
        _t.env.globals["get_flashes"] = _get_flashes
except Exception:
    logging.getLogger("cff.flash").exception("failed to register get_flashes global")


# ─── Prometheus /metrics — opt-in HTTP instrumentation + custom gauges ───
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    from shared.metrics import sample_all  # noqa: F401  side-effect: register metrics

    _instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics", "/health"],
    )
    _instrumentator.instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False, should_gzip=True,
    )

    @app.on_event("startup")
    async def _kick_metrics_sampler():
        """Refresh sampled gauges every 30s in the background."""
        import asyncio

        async def _loop():
            while True:
                try:
                    sample_all()
                except Exception:
                    logging.getLogger("cff.metrics").exception("sample_all failed")
                await asyncio.sleep(30)

        asyncio.create_task(_loop())

except ImportError:
    logging.getLogger("cff.metrics").warning(
        "prometheus_fastapi_instrumentator not installed — /metrics disabled"
    )


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
