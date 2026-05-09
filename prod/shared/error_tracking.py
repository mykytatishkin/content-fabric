"""Sentry-compatible error tracking via GlitchTip (self-hosted).

Initialize once at startup of every long-running process (FastAPI app and
each rq worker). Trace_id from logging_context is automatically attached
as a Sentry tag — clicking through an error in GlitchTip will jump to the
matching log line in Loki.

Configuration via env (in /opt/content-fabric/prod/.env/.env.api):
    SENTRY_DSN=http://<key>@127.0.0.1:8001/<project_id>
    SENTRY_ENVIRONMENT=production
    SENTRY_TRACES_SAMPLE_RATE=0.05    # 5% of transactions get tracing
    SENTRY_RELEASE=cff@<git_sha>      # filled by CI/deploy

When SENTRY_DSN is empty the SDK is a no-op — safe to enable per-service.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_initialized = False


def _before_send(event, hint):
    """Hook every event right before it's shipped to GlitchTip.

    - Attach trace_id / task_id / worker from logging_context as tags.
    - Drop noisy events we never want stored (ping checks, expected 4xx).
    """
    try:
        from shared.logging_context import context_dict
        ctx = context_dict()
        if ctx:
            event.setdefault("tags", {})
            for k, v in ctx.items():
                event["tags"][k] = str(v)
            event.setdefault("contexts", {}).setdefault("cff", {}).update(ctx)
    except Exception:
        pass

    # Drop /metrics and /health spam if any leaked through
    try:
        request = event.get("request") or {}
        url = (request.get("url") or "").lower()
        if url.endswith("/metrics") or url.endswith("/health"):
            return None
    except Exception:
        pass

    return event


def init(service_name: str) -> bool:
    """Initialize Sentry SDK if SENTRY_DSN is set. Returns True if active."""
    global _initialized
    if _initialized:
        return True

    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        logger.debug("Sentry DSN not set — error tracking disabled for %s", service_name)
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logger.warning("sentry-sdk not installed — error tracking unavailable")
        return False

    integrations = [
        LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
    ]

    # Optional integrations (only register if importable, so workers without
    # FastAPI / SQLAlchemy don't crash)
    try:
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        integrations.append(FastApiIntegration())
    except Exception:
        pass
    try:
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        integrations.append(SqlalchemyIntegration())
    except Exception:
        pass
    try:
        from sentry_sdk.integrations.redis import RedisIntegration
        integrations.append(RedisIntegration())
    except Exception:
        pass
    try:
        from sentry_sdk.integrations.rq import RqIntegration
        integrations.append(RqIntegration())
    except Exception:
        pass

    try:
        traces_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05"))
    except ValueError:
        traces_rate = 0.05

    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
            release=os.environ.get("SENTRY_RELEASE", ""),
            integrations=integrations,
            traces_sample_rate=traces_rate,
            send_default_pii=False,
            attach_stacktrace=True,
            before_send=_before_send,
        )
        sentry_sdk.set_tag("service", service_name)
        _initialized = True
        logger.info("Sentry/GlitchTip initialized for %s (env=%s)",
                    service_name, os.environ.get("SENTRY_ENVIRONMENT", "production"))
        return True
    except Exception:
        logger.exception("Failed to initialize Sentry/GlitchTip — continuing without")
        return False


def capture_exception(exc: BaseException) -> None:
    """Force-send an exception (otherwise it's caught automatically)."""
    if not _initialized:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def capture_message(message: str, level: str = "info") -> None:
    if not _initialized:
        return
    try:
        import sentry_sdk
        sentry_sdk.capture_message(message, level=level)
    except Exception:
        pass
