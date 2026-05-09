# GEMINI.md — Content Fabric (CFF)

Instructional context for Google Gemini AI when working in this codebase. AI-readable, structured, terse. If anything here contradicts source code, the source wins — re-read the cited file:line.

---

## Project Overview

Content Fabric is a Python production platform that automates the full YouTube content lifecycle: DLE-source ingestion → voice conversion (RVC/Silero) → video assembly → scheduled YouTube upload, plus 9 RTMP live-streams, 39 channel OAuth management, and YouTube Shorts generation (yt-dlp → Whisper → GPT-4 → ffmpeg). Backend is FastAPI on Python 3.10+, MySQL via SQLAlchemy Core, Redis+RQ for queues, Jinja2 SSR for the admin/portal UIs. Hosted at `aiyoutube.pbnbots.com` (HTTPS, nginx → uvicorn 127.0.0.1:8000). See `prod/main.py` and `.kiro/steering/project-overview.md`.

---

## Repo Layout

```
cff/
├── prod/                       — application root
│   ├── main.py                 — FastAPI app, middleware stack, /health, /metrics
│   ├── app/
│   │   ├── api/endpoints/      — REST handlers (JWT-protected)
│   │   ├── views/              — SSR portal + admin panel (cookie auth)
│   │   ├── templates/          — Jinja2; uses |tojson for safe JSON islands
│   │   ├── core/               — config, auth, security, database
│   │   └── schemas/            — Pydantic v2 models
│   ├── shared/
│   │   ├── db/                 — connection.py, models.py, repositories/
│   │   ├── queue/              — config.py (queue names), publisher, types
│   │   ├── ingestion/dle/      — DLE pipeline (client, processor, parser)
│   │   ├── shorts/             — downloader, transcriber, highlight, cutter
│   │   ├── streams/            — systemd_manager, provisioner
│   │   ├── voice/              — RVC, Silero, mixer, prosody
│   │   ├── youtube/            — client, upload, token_refresh, reauth/
│   │   ├── notifications/      — telegram, email, manager
│   │   ├── logging_context.py  — trace_id ContextVar (set/get/ensure)
│   │   ├── logging_config.py   — JSON formatter, TraceContextFilter
│   │   ├── metrics.py          — Prometheus + @instrument_job
│   │   └── error_tracking.py   — sentry_sdk (GlitchTip)
│   ├── workers/                — RQ worker entry points (one per queue)
│   ├── scheduler/              — 60s polling loop (run.py, jobs.py)
│   ├── cli/                    — reauth, voice CLI tools
│   ├── tests/                  — pytest suite
│   └── deploy/
│       ├── systemd/            — cff-*.service units
│       ├── nginx/              — aiyoutube.pbnbots.com.conf (HTTPS :443)
│       ├── auditd/             — audit rules + baseline
│       └── observability/      — Prometheus, Loki, Grafana, GlitchTip
├── database/DDL/               — schema, migrations, SCHEMA_INDEX.md
├── docs/                       — operational + design documentation
├── scripts/                    — utility scripts
└── .kiro/steering/             — agent steering files
```

---

## Current Focus (May 2026)

- **Yii→CFF migration: COMPLETE.** Legacy Yii2 app is decommissioned. Do not re-enable. See `database/DDL/migrations/004_yii_decommission.sql`.
- **Security hardening: DONE.** May 2026 commits 049f140, 4a81951, 87d6a1c, a45ea5c, 27fc60e, e49ace1, 84231d7: rotated JWT to 32-byte secret, added CSRF middleware, locked Redis/MySQL ports via DOCKER-USER iptables, tightened CSP/HSTS, patched 4 stored-XSS sites with `|tojson`, blocked public `/metrics`, deployed auditd rules.
- **Now:** feature-parity polish + observability tuning. The full stack (Prometheus/Loki/Grafana/GlitchTip) is live since 2026-05-09 — see `docs/OBSERVABILITY.md`. New work should preserve trace_id propagation and emit metrics via `shared/metrics.py`.

---

## Workers (9 cff-* units)

All defined in `prod/deploy/systemd/cff-*.service`, all run as `python -m workers.<name>` with `WorkingDirectory=/opt/content-fabric/prod`.

| systemd unit                       | module                              | RQ queue             |
|------------------------------------|-------------------------------------|----------------------|
| cff-api.service                    | uvicorn main:app (127.0.0.1:8000)   | — (HTTP gateway)     |
| cff-scheduler.service              | scheduler.run                       | — (polls DB → enqueues) |
| cff-publishing-worker.service      | workers.publishing_worker           | `publishing`         |
| cff-notification-worker.service    | workers.notification_worker         | `notifications`      |
| cff-voice-worker.service           | workers.voice_worker                | `voice`              |
| cff-dle-ingestion-worker.service   | workers.dle_ingestion_worker        | `dle_ingestion`      |
| cff-dle-processor-worker.service   | workers.dle_processor_worker        | `dle_processing`     |
| cff-shorts-worker.service          | workers.shorts_worker               | `shorts`             |
| cff-stats-worker.service           | workers.stats_worker                | `stats`              |
| cff-stream-control-worker.service  | workers.stream_worker               | `stream_control`     |

Queue names live in `prod/shared/queue/config.py:17-26`. The `dle_processing` queue is hard-coded inside `prod/workers/dle_processor_worker.py:102`.

---

## Code Conventions

1. **IntEnum + SQL.** `TaskStatus`, `UserStatus` etc. are `IntEnum`. When building raw SQL params, always pass `.value` — e.g. `status=TaskStatus.PENDING.value`, never the enum itself. SQLAlchemy Core does not auto-unwrap.
2. **Repositories.** All DB operations route through `prod/shared/db/repositories/*.py` (audit, channel, console, credential, notification, stats, task, template, user). New tables get a new repo file. Endpoints/views never call `text()` directly.
3. **Queue names.** Centralised in `prod/shared/queue/config.py`. Workers import `QUEUE_*` constants; never hard-code strings (the lone exception is `dle_processor_worker.py` — fix that if you touch it).
4. **trace_id.** `prod/shared/logging_context.py` exposes `new_trace_id() / set_trace_id() / get_trace_id()` backed by a `ContextVar`. `TraceContextMiddleware` in `main.py:139-183` binds it from `X-Trace-Id` header (or fresh) and echoes it in the response. `shared/queue/publisher.py` auto-fills `trace_id` on every enqueue from the current ContextVar so it propagates across worker boundaries. `workers/_job_bootstrap.py::bootstrap_job()` re-binds it inside the worker. Never strip trace_id from a payload.
5. **Jinja `|tojson` for JSON islands.** Any time template code injects server-side data into a `<script>` block as JSON, wrap with `|tojson` (XSS-safe: it produces JSON-escaped, HTML-safe output). See commit 87d6a1c for the four sites that were patched. Do NOT use `|safe` on user-controlled strings.
6. **CSRF.** `CSRFMiddleware` in `main.py:61-136` enforces Origin/Referer == Host for cookie-authenticated state-changing requests. Bearer-token clients bypass (no cookie ⇒ no CSRF surface). Login is the only POST endpoint exempted by path. Don't disable for new endpoints — fix the form instead.
7. **Pydantic v2.** All schemas use Pydantic 2 syntax (`model_config`, `Field(...)`, `field_validator`). Don't mix v1 patterns.
8. **Observability conventions.** New workers must call `bootstrap_job()` first thing and decorate jobs with `@instrument_job` from `shared/metrics.py`. Read `docs/OBSERVABILITY.md` before adding a new worker.

---

## Forbidden

- **Never modify `tg-app`** or anything under `/var/www/.../tg-app` on the server. It is a separate Telegram-bot application owned by another team. Not in this repo.
- **Never re-enable Yii2 / `yii-audit/` code paths.** The migration is complete and one-way. Any "let me just look at what Yii did" should be done in git history, not by booting PHP.
- **Never touch `/opt/content-fabric/prod/tg-app`** on the production server.
- **Never bind a worker or uvicorn to `0.0.0.0`.** Production binds 127.0.0.1; nginx is the only public-facing process. See `cff-api.service:14`.
- **Never bypass CSRF middleware** for state-changing cookie-auth endpoints. If you need to, you're using the wrong auth scheme.
- **Never log secrets.** OAuth tokens, passwords, API keys must not appear in logs even at DEBUG. The audit pipeline forwards stdout/journal to Loki.

---

## Test Conventions

- **Framework:** `pytest`, runner in `prod/tests/`. Currently 221 tests passing on Linux (CI). On Windows some integration tests skip due to FFmpeg/RVC native dependency mocks — that's expected.
- **Run:** `cd prod && python -m pytest tests/ -v --tb=short`.
- **Mocking style.** Module-level imports are patched at the import site, not at the source. Example: when testing `app.api.endpoints.channels`, patch `app.api.endpoints.channels.get_connection`, not `shared.db.connection.get_connection`. The DLE integration tests (`tests/test_dle_pipeline_integration.py`) are the canonical example.
- **Fixtures.** Use `tests/conftest.py` for shared fixtures. Never hit a real MySQL/Redis from a unit test — the test suite must be runnable offline.
- **TestClient.** Web/API tests use `fastapi.testclient.TestClient`; cookie-auth tests need to call `/api/v1/auth/login` first to establish the cookie.

---

## Key Documentation

| File                                       | Purpose                                                |
|--------------------------------------------|--------------------------------------------------------|
| `docs/PROD_README.md`                      | Operations, services, env files, task lifecycle        |
| `docs/ARCHITECTURE.md`                     | System design, component boundaries                    |
| `docs/SECURITY.md`                         | Hardening — JWT rotation, CSRF, CSP, port lockdown (if missing, see commits 049f140 / 4a81951 / e49ace1) |
| `docs/OBSERVABILITY.md`                    | Telemetry stack, trace_id, metrics, alerts             |
| `prod/deploy/auditd/README.md`             | Audit logging rules + baseline scan                    |
| `database/DDL/SCHEMA_INDEX.md`             | Full DB schema                                         |
| `SERVER_START_GUIDE.md`                    | Ops quick-start (start/stop, health, rollback)         |
| `.kiro/steering/project-overview.md`       | High-level orientation                                 |

---

## Dependency Policy

Security floors — never downgrade these without explicit approval:

| Package           | Minimum            | Reason                                    |
|-------------------|--------------------|-------------------------------------------|
| `requests`        | `>=2.32.4`         | CVE patch (urllib3 cert verification)     |
| `python-multipart`| `>=0.0.18`         | DoS fix in form-parser                    |
| `psutil`          | `>=5.9.8`          | Race-condition fix in proc inspection     |

`prod/requirements.txt` is the source of truth. Adding a new dep: pin upper bound to the minor version, document the reason in the commit body. Run `pip-audit` before merging.
