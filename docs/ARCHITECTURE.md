# Content Fabric — Architecture Reference

**Last reviewed:** 2026-05-09
**Audience:** developers + ops
**Repository:** [mykytatishkin/content-fabric](https://github.com/mykytatishkin/content-fabric)

---

## 1. TL;DR

- **Что это.** FastAPI-моноапп (`prod/main.py`) + 8 RQ-воркеров + 1 scheduler. Один MySQL, один Redis (с `requirepass`), один Nginx. PHP/Yii ушёл, всё на Python 3.10+.
- **Как ходят данные.** Браузер/CLI → Nginx (TLS, `:443`) → Uvicorn (`127.0.0.1:8000`) → middleware-стек → роутеры → repositories → MySQL/Redis. Long-running работа уходит в RQ; scheduler крутит cron-эмулятор для DLE-ингестий.
- **Как мы это видим.** Prometheus скрейпит `/metrics`, короткие jobs пушат в pushgateway. Promtail тащит `/var/log/cff-*.log`, journald, nginx и auditd в Loki. Дашборды в Grafana, ошибки в GlitchTip. Trace_id живёт от HTTP-заголовка через ContextVar до конкретной строки лога.

---

## 2. System diagram

```
                         ┌──────────────┐
                         │   Browser    │   (admin / user / CLI / Bearer)
                         │   tg-app*    │   *separate project — see §12
                         └──────┬───────┘
                                │ HTTPS :443
                                ▼
                       ┌────────────────┐
                       │     nginx      │  TLS, /static, /metrics allowlist, proxy
                       │ aiyoutube.*   │  prod/deploy/nginx/*.conf
                       └──────┬─────────┘
                                │ proxy_pass 127.0.0.1:8000
                                ▼
   ┌────────────────────────── uvicorn  (cff-api.service) ──────────────────────────┐
   │  SlowAPI → SecurityHeaders → CSRF → TraceContext → CORS → routers              │
   │           prod/main.py:30..207                                                  │
   │                                                                                 │
   │  /api/v1/*  (Bearer OR cookie)   /panel/*  (admin)   /app/*  (user portal)     │
   │  prod/app/api/{routes,deps}.py   prod/app/views/panel.py  app_portal.py        │
   └──────────────────┬───────────────────┬────────────────────┬────────────────────┘
                      │ repositories      │ enqueue           │ Jinja templates
                      ▼                   ▼                    ▼
              ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
              │   MySQL      │    │   Redis      │    │  templates/  │
              │ content_     │◄──►│ requirepass  │    │  static/     │
              │ factory      │    │ rq:queue:*   │    └──────────────┘
              └──────┬───────┘    └──────┬───────┘
                     │                   │ rq workers (systemd, host)
                     │                   ▼
                     │   ┌──────────────────────────────────────────────┐
                     │   │ cff-scheduler  + 8 cff-*-worker.service       │
                     │   │ prod/scheduler/run.py + prod/workers/*.py     │
                     │   │   • publishing • voice • notifications        │
                     │   │   • dle-ingestion • dle-processor • shorts    │
                     │   │   • stats • stream-control                    │
                     │   └──────┬─────────────────────────┬──────────────┘
                     │          │ instrument_job          │ external APIs
                     │          ▼                          ▼
                     │   ┌──────────────┐         ┌──────────────────────┐
                     │   │ pushgateway  │         │ YouTube • TikTok     │
                     │   │ 127.0.0.1:91 │         │ DLE MySQL × 7        │
                     │   └──────┬───────┘         │ Telegram • Email     │
                     │          │                  │ OpenAI / Whisper     │
                     ▼          ▼                  └──────────────────────┘
              ┌────────────────────────── observability ──────────────────────────┐
              │ Prometheus :9090  ←  /metrics (cff-api) + pushgateway              │
              │ Loki :3100        ←  Promtail (cff-files, systemd-journal,        │
              │                       nginx, auditd)                                │
              │ Grafana :3001 (SSH-tunnel only)                                    │
              │ GlitchTip :8001   ←  sentry_sdk from cff-* services                │
              │ docker-compose в prod/deploy/observability/                        │
              └────────────────────────────────────────────────────────────────────┘
```

---

## 3. Request lifecycle (HTTP)

Middleware order is the order Starlette executes — **последний `add_middleware` срабатывает первым** на входящем запросе. См. `prod/main.py:197..207`.

| Order on request | Middleware | Source | What it does |
|---:|---|---|---|
| 1 | **TraceContextMiddleware** | `prod/main.py:139` | Reads or generates `X-Trace-Id`, binds to `ContextVar`, logs the request once and echoes the id back. |
| 2 | **CSRFMiddleware** | `prod/main.py:61` | For unsafe methods on cookie-auth requests, requires `Origin` (or `Referer`) to match `Host`. Bearer tokens and `/api/v1/auth/login` bypass. |
| 3 | **SecurityHeadersMiddleware** | `prod/main.py:30` | Sets HSTS (2 года), CSP, X-Frame-Options DENY, Permissions-Policy, Referrer-Policy on every response. |
| 4 | **SlowAPIMiddleware** | `prod/main.py:197` | Per-IP rate limiter (default `120/minute`); login endpoint locally caps at `10/minute`. |
| 5 | **CORSMiddleware** | `prod/main.py:202` | Whitelisted origins, no credentials, allowed methods `GET/POST/PUT/DELETE/OPTIONS`. |
| 6 | **Router dispatch** | `prod/app/api/routes.py` + views | Matches `/api/v1/*`, `/panel/*`, `/app/*`, `/health`, `/metrics`, `/static`. |

`TraceContextMiddleware` deliberately does both ContextVar-binding and access-logging in one dispatch — ContextVars set in an inner middleware are not visible to outer ones because Starlette wraps each middleware in its own asyncio Task scope.

Errors:
- `RateLimitExceeded` → 429 JSON (`prod/main.py:216`).
- 404 in `/api/*` → JSON; 404 elsewhere → `templates/404.html` (`prod/main.py:231`).
- All other HTTP → JSON `{detail}`.

---

## 4. Authentication & authorization

**Token format.** HS256 JWT, claims `{sub: str(user_id), exp}`, signed with `JWT_SECRET_KEY` (32-byte hex, rotated May 2026). TTL 24h via `JWT_EXPIRE_MINUTES`. См. `prod/app/core/security.py`.

**Two transports, one validator.** `get_current_user` (`prod/app/api/deps.py:26`) accepts:
1. `Authorization: Bearer <jwt>` (CLI, machine clients, tests).
2. Cookie `cff_token=<jwt>` (browser, set by `/app/login` with `HttpOnly; SameSite=lax; Secure` when `HTTPS_ENABLED=1`).

When both are present, **Bearer wins**. Missing/invalid/expired → 401. The cookie path is the only one CSRFMiddleware guards — Bearer requests are immune by construction (an attacker on `evil.com` cannot read another origin's `Authorization` header).

**Admin gate.** `is_admin(user)` checks `user.status == UserStatus.ADMIN` (= 1). Two helpers consume it:
- `get_current_admin` (`prod/app/api/deps.py:60`) — for JSON APIs; raises 403.
- `require_admin(request)` (`prod/app/core/auth.py:53`) — for SSR pages; redirects unauth → `/app/login`, non-admin → `/app/`.

**Admin-only surfaces (post-May-2026 hardening):**
- All of `/panel/*` (every handler in `prod/app/views/panel.py` calls `require_admin`).
- `/api/v1/streams/*` — full CRUD + control (`prod/app/api/endpoints/streams.py`).
- `/api/v1/streams/dle-sources/logs` and the rest of `/api/v1/dle-sources/*` (`prod/app/api/endpoints/dle_sources.py`).
- `/api/v1/admin/*` (`prod/app/api/endpoints/admin.py`).
- `/api/v1/logs/*` — Loki proxy / journald tail (`prod/app/api/endpoints/logs.py`).

**User-scoped surfaces.** `tasks`, `templates`, `uploads`, `channels` use `get_current_user` + `scoped_where(user, alias)` (`prod/app/core/auth.py:81`) so non-admins only see rows where `created_by = user.id`. Admins see everything.

**2FA.** Optional TOTP per user (`platform_users.totp_secret`, `totp_enabled`, `totp_backup_codes`). Verified in `app_portal.login_submit` (`prod/app/views/app_portal.py:80..107`).

---

## 5. Domain layer (`prod/shared/`)

| Subdir | Purpose | Entry point |
|---|---|---|
| `db/` | SQLAlchemy Core engine + connection pool. `models.py` defines 13 tables; `connection.py` exposes `get_connection()`; `utils.py` has cursor helpers. | `shared.db.connection.get_connection` |
| `db/repositories/` | Thin per-aggregate query layer — every endpoint reaches MySQL through these, never raw. `task_repo`, `channel_repo`, `user_repo`, `template_repo`, `console_repo` (=oauth credentials), `stats_repo`, `audit_repo`, `notification_repo`, `credential_repo`. | `from shared.db.repositories import …` |
| `queue/` | Redis + RQ wiring. `config.py` defines all 9 queue names; `publisher.py` provides `enqueue_*` helpers; `types.py` holds dataclass payloads (`VideoUploadPayload`, `DleIngestionPayload`, etc.). | `shared.queue.publisher.enqueue_video_upload` |
| `youtube/` | OAuth credentials build/refresh, resumable upload (`upload.py`), and the **reauth** module (`reauth/service.py`) — Playwright-driven re-authorization with TOTP and proxy support. | `shared.youtube.upload.process_upload` |
| `voice/` | RVC-based voice conversion (`changer.py`, `rvc/inference.py`, `silero.py`, `prosody.py`, `mixer.py`, `parallel.py`). Worker calls `process_voice_change`. | `shared.voice.changer.process_voice_change` |
| `ingestion/dle/` | DLE-сайты (7 источников) — `client.py` (per-source MySQL), `xfields_parser.py`, `pipeline.py` (создаёт CFF tasks из DLE-постов), `processor.py` (download + processing). | `shared.ingestion.dle.pipeline.DleIngestionPipeline` |
| `streams/` | YouTube live streaming control plane: `provisioner.py` создаёт `live_stream_configurations`, `systemd_manager.py` управляет unit-файлами `stream-*.service`, `runner_template.py` рендерит ffmpeg-команду. | `shared.streams.systemd_manager` |
| `shorts/` | YouTube Shorts pipeline: `downloader.py` (yt-dlp), `transcriber.py` (Whisper), `highlight.py` (GPT-4 picks moments), `cutter.py` (ffmpeg vertical cut), `thumbnail.py` (frame pick). | `shared.shorts.*` |
| `sora/` | Sora AI scraping через ZenRows — `scraper.py`. | `shared.sora.scraper` |
| `notifications/` | Multi-channel notifier — `telegram.py`, `email.py`, `manager.py` (router by `NotificationPayload.channel`). | `shared.notifications.manager.notify` |
| `metrics.py` | Prometheus metrics: counters/gauges/histograms registered to default `REGISTRY`, `instrument_job` decorator for RQ jobs, `push_worker_global_metrics`, `sample_all` for periodic gauges. | `shared.metrics` |
| `logging_config.py` + `logging_context.py` | JSON line logging to `/var/log/cff-<service>.log`, `MetricsLogHandler` (every WARNING+ → `cff_log_events_total`), and `ContextVar`-based `trace_id`/`task_id`/`worker` propagation. | `shared.logging_config.setup_logging` |
| `error_tracking.py` | GlitchTip / Sentry init wrapper. Lazy and idempotent. | `shared.error_tracking.init` |
| `env.py` | Single import side-effect: load `.env` files before anything reads `os.environ`. | `import shared.env` |

---

## 6. Background processing

### 6.1 Queues

Defined once in `prod/shared/queue/config.py:17..26`:

| Queue | Worker (systemd unit) | Source file |
|---|---|---|
| `publishing` | `cff-publishing-worker.service` | `workers/publishing_worker.py` |
| `notifications` | `cff-notification-worker.service` | `workers/notification_worker.py` |
| `voice` | `cff-voice-worker.service` | `workers/voice_worker.py` |
| `dle_ingestion` | `cff-dle-ingestion-worker.service` | `workers/dle_ingestion_worker.py` |
| `dle_processing` | `cff-dle-processor-worker.service` | `workers/dle_processor_worker.py` |
| `shorts` | `cff-shorts-worker.service` | `workers/shorts_worker.py` |
| `sora` | (cf. dle_processor — sora job is dispatched there) | `workers/dle_processor_worker.py` |
| `stats` | `cff-stats-worker.service` | `workers/stats_worker.py` |
| `stream_control` | `cff-stream-control-worker.service` | `workers/stream_worker.py` |

`sample_queue_depths` (`shared/metrics.py:297`) iterates exactly these 9 names to populate `cff_queue_depth{queue="…"}`.

### 6.2 Job bootstrap and instrumentation

Every worker handler calls `bootstrap_job(payload, "cff-<name>")` (`workers/_job_bootstrap.py`) at the top of the function. That:

1. Lazy-inits GlitchTip once per process.
2. Pulls `payload.trace_id` (or generates one) and binds to `ContextVar` so all log lines emitted in the job carry it.
3. Binds `payload.task_id` if present.

Then the function is wrapped with `@instrument_job("<name>")` (`shared/metrics.py:237`). The decorator:

- Times execution into `cff_worker_job_duration_seconds{worker, outcome}`.
- Increments `cff_worker_jobs_total{worker, outcome}` (ok / fail / exception).
- Pushes the per-job `CollectorRegistry` to pushgateway with `grouping_key={task_id}` so each task overwrites its own slot.
- Pushes the worker process's global `REGISTRY` via `push_worker_global_metrics(name)` so `cff_log_events_total` (incremented by `MetricsLogHandler` during the job) actually reaches Prometheus — workers don't expose `/metrics`.

If the handler returns `{"ok": False}` or raises, outcome is `fail` / `exception` and `errors_total{worker, error_kind}` is bumped.

### 6.3 Scheduler (`prod/scheduler/`)

`scheduler/run.py` is a single loop, polled every `POLL_INTERVAL = 60s`:

1. **`enqueue_pending_tasks()`** — pulls up to 50 rows from `content_upload_queue_tasks` with `status=0` and `scheduled_at ≤ NOW()`, marks them `processing`, routes:
   - DLE task with empty `source_file_path` → `voice` queue (worker downloads + processes from `legacy_add_info.dle_source`).
   - Otherwise → `publishing` queue.
2. **`run_periodic_yii_jobs()`** — in-memory cron emulator (`scheduler/jobs.py:407`). Fires once per HH:MM combination across runs:
   - `dle_nightly` @ 02:00 — nightly video ingestion (knigi_audio_biz, audiokniga_one_com, club_books_ru, books_online_info, bazaknig_net × N channels).
   - `dle_shorts_{1,2,3}` @ 14:15 / 16:15 / 21:15 — short-form ingestion.
   - `slushat_shorts_{1,2}` @ 17:15 / 20:15 — `slushat_knigi_com` shorts.
   - `shorts_from_video` @ 13:20 — shorts from donor YouTube videos.
3. **Daily token validation** (once per calendar day) — `validate_channel_tokens()` calls `ensure_fresh_credentials` for every channel with stored OAuth, updates `token_check_ok`.
4. **Daily stats collection** (once per calendar day) — `collect_channel_stats()` + `collect_video_stats()` via YouTube Data API v3 → `channel_daily_statistics`.

`SIGINT` / `SIGTERM` set `_running = False` and the loop exits cleanly.

---

## 7. Data model

All tables live in `database/DDL/` and are mirrored as SQLAlchemy Core in `prod/shared/db/models.py`. See `database/DDL/SCHEMA_INDEX.md` for the full ER diagram.

### Identity & access (`auth/`)

| Table | Purpose |
|---|---|
| `platform_users` | User accounts. `status` int: `0`=inactive, `1`=admin, `10`=active. TOTP fields embedded. |
| `platform_projects` | Workspaces — every business resource belongs to a project, not a user. |
| `platform_project_members` | RBAC role per (project, user): `owner` / `admin` / `editor` / `viewer`. |

### Channels & OAuth (`channels/`)

| Table | Purpose |
|---|---|
| `platform_oauth_credentials` | Cloud-console-level OAuth app credentials (client_id, client_secret). One per Google Cloud project. Internal name in code: `console_repo`. |
| `platform_channels` | Multi-platform channels (youtube/tiktok/instagram/...). Holds `access_token`, `refresh_token`, `token_expires_at`, `processing_status`. `uuid` column for IDOR-safe portal URLs. |
| `platform_channel_tokens` | Historical token backups (rotated on refresh). |
| `platform_channel_login_credentials` | RPA login creds for automated reauth: `login_email`, `login_password`, `totp_secret`, optional proxy and `profile_path`. |

### Publishing

| Table | Purpose |
|---|---|
| `content_upload_queue_tasks` | The video publishing queue. Status int: `0`=pending, `1`=completed, `2`=failed, `3`=processing, `4`=cancelled. `legacy_add_info` JSON carries DLE provenance. `uuid` IDOR column. |

### Scheduling

| Table | Purpose |
|---|---|
| `schedule_templates` | Named publishing schedule (per project, with timezone). `uuid` IDOR column. |
| `schedule_template_slots` | (template, day_of_week, time_utc, optional channel_id) — generates pending tasks for the scheduler to pick up. |

### Analytics & audit (`analytics/`)

| Table | Purpose |
|---|---|
| `channel_daily_statistics` | Daily snapshot per channel: subscribers, views, videos, likes, comments. |
| `channel_reauth_audit_logs` | One row per reauth attempt (status, trigger_reason, error_code/message). |

### Streaming (`streaming/`)

| Table | Purpose |
|---|---|
| `live_streaming_accounts` | OAuth accounts dedicated to live streaming. |
| `live_stream_configurations` | One row per `stream-*.service` systemd unit: rtmp endpoint, stream key, ffmpeg workdir, broadcast/video/stream IDs, duration. |

### Notifications & system

| Table | Purpose |
|---|---|
| `notifications` | In-app inbox per user. `is_read` flag, `type` ∈ `{info, error, task, broadcast}`. |
| `platform_schema_migrations` | Migration version tracking. |

### Convention notes

- **IntEnum `.value` rule.** `TaskStatus` and `UserStatus` (`shared/db/models.py:6,14`) are `IntEnum`. Always pass `.value` in raw SQL — comparing `WHERE status = TaskStatus.ADMIN` would bind the enum object, not the int.
- **`Column("metadata", JSON, key="meta")`.** SQLAlchemy reserves `metadata` on Tables; the `key="meta"` aliases it so Python attribute access works without colliding with `Table.metadata`.
- **UUID-IDOR.** Three tables (`platform_channels`, `content_upload_queue_tasks`, `schedule_templates`) carry an extra `uuid VARCHAR(36)` exposed in portal URLs. JOINs and FKs still use integer `id`.

---

## 8. Observability

### 8.1 Prometheus

- **`/metrics` on `cff-api`** — exposed via `prometheus_fastapi_instrumentator` (`prod/main.py:279`). Excludes `/metrics` and `/health` from histograms. The endpoint is **firewalled at nginx** to `127.0.0.1` only — Prometheus scrapes the loopback (see §9 security posture).
- **Sampled gauges.** A startup task (`prod/main.py:289..302`) calls `sample_all()` every 30s, which refreshes:
  - `cff_queue_depth{queue}` — RQ queue lengths for all 9 queues.
  - `cff_dle_source_up{source}` + `cff_dle_source_check_duration_seconds{source}` — `SELECT 1` against each DLE source DSN.
  - `cff_youtube_token_expires_in_seconds{channel}` — read from `platform_channels.token_expires_at` (UTC-aware, see comment in `metrics.py:336`).
  - `cff_stream_active{stream,service}` + `cff_stream_uptime_seconds{stream}` + `cff_streams_in_state{state}` — via `systemctl list-units stream-*.service`.
  - `cff_tasks_in_status{status}`, `cff_tasks_created_recent{window}`, `cff_tasks_completed_recent{window}`, `cff_tasks_failed_recent{window}`.
- **Push-based job metrics.** Short-lived RQ jobs use the `instrument_job` decorator (see §6.2) — the per-job registry plus the worker's process-wide `REGISTRY` are pushed to `pushgateway` at `127.0.0.1:9091` after every invocation.
- **Log-driven counters.** `MetricsLogHandler` (registered by `setup_logging`) increments `cff_log_events_total{level, logger, worker}` on every record ≥ INFO so dashboards can compute real error rates without depending on `raise`.

### 8.2 Loki / Promtail

`prod/deploy/observability/promtail/promtail-config.yml` defines four sources:

| Job label | Path / source | Purpose |
|---|---|---|
| `cff-files` | `/var/log/cff-*.log` | JSON-line logs from `cff-api`, `cff-scheduler`, every worker. Extracts `service`, `level`, `worker`, `trace_id`, `task_id` labels. |
| `systemd-journal` | journald (matches `_SYSTEMD_UNIT=cff-*` and friends) | Catches stdout/stderr from systemd units that bypass file logging. |
| `nginx` | `/var/log/nginx/*access*.log` + `/var/log/nginx/*error*.log` | HTTP access & error log. |
| `auditd` | `/var/log/audit/audit.log` | Security audit events. Promtail extracts the `-k <key>` tag and synthesises a `level=warn` for `res=failed` lines. |

### 8.3 Trace_id flow

```
External call: X-Trace-Id: abcdef1234... ─────┐
                                              ▼
TraceContextMiddleware           ── set_trace_id() on ContextVar
   prod/main.py:139                            │
                                              ▼
   logger.info("...")            ── TraceFilter (logging_config) injects
                                              │  trace_id into the JSON log line
                                              ▼
   Promtail regex pulls           ── label trace_id="abcdef..."
   trace=… out of /var/log/cff-*  ── viewable in Loki / Grafana
                                              │
   payload.trace_id =                         │
   shared.logging_context.get_trace_id()      ▼
                                       enqueue → RQ
                                              │
                                              ▼
   bootstrap_job(payload, …)      ── set_trace_id() on worker ContextVar
                                       same trace_id propagates through
                                       child jobs and metric labels
```

Response `X-Trace-Id` header is set unconditionally so external callers can correlate.

### 8.4 Grafana dashboards

Provisioned from `prod/deploy/observability/grafana/dashboards/`:

| UID | File | What it shows |
|---|---|---|
| `cff-now` | `now.json` | Default home dashboard — single-pane current state. |
| `cff-system` | `system_overview.json` | 11-tile platform summary (queues, tasks, errors, exporters). |
| `cff-pipeline` | `task_pipeline.json` | Per-stage durations and conversion rates of tasks through the pipeline. |
| `cff-trace` | `trace_explorer.json` | Loki-backed trace explorer — paste a `trace_id`, get the full timeline. |
| `cff-incidents` | `incidents_now.json` | Live incidents board fed by alerting rules. |
| `cff-security` | `security.json` | Auditd-driven security events. |

Alerting rules: `prod/deploy/observability/grafana/provisioning/alerting/rules.yaml` (cff-api-down, worker-missing, queue-growing, failure-rate, token-expiring, worker-mem, …).

---

## 9. Security posture (post-May-2026 hardening)

| Layer | Control | Source |
|---|---|---|
| TLS / headers | HSTS `max-age=63072000; includeSubDomains; preload` | `prod/main.py:57` |
| Headers | CSP (`'unsafe-eval'` removed, `frame-ancestors 'none'`, `form-action 'self'`, `base-uri 'self'`, `object-src 'none'`), X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy strict-origin-when-cross-origin, Permissions-Policy locked. | `prod/main.py:30..58` |
| CSRF | `Origin`/`Referer` must match `Host` for unsafe methods on cookie-auth requests; Bearer + login bootstrap exempt. | `prod/main.py:61..136` |
| Auth | JWT HS256, 32-byte hex secret (rotated May 2026), 24h TTL, `JWT_SECRET_KEY` mandatory at boot. | `prod/app/core/security.py:13` |
| AuthZ | Admin gate on every `/panel/*` and `/api/v1/{streams,dle-sources,admin,logs}/*` endpoint. | `prod/app/api/deps.py:60`, `prod/app/views/panel.py` |
| 2FA | Optional per-user TOTP + backup codes. | `prod/app/views/app_portal.py:80..107` |
| Rate limit | Global `120/minute` per IP, login `10/minute`. | `prod/main.py:27`, `prod/app/views/app_portal.py:79` |
| `/metrics` exposure | Nginx `location = /metrics { allow 127.0.0.1; deny all; }` on both vhosts. Prometheus scrapes loopback only. | `prod/deploy/nginx/{content-fabric,aiyoutube.pbnbots.com}.conf` |
| Network | Firewall: only `22`, `80`, `443` external; everything else (Redis 6379, Prometheus 9090, Loki 3100, Grafana 3001, Pushgateway 9091, GlitchTip 8001) listens on `127.0.0.1` and is reached via SSH tunnel. |
| Redis | `requirepass` enabled on the main Redis used by app + workers (`REDIS_URL` carries the password). The `cff-glitchtip-redis` container has no auth — accepted because it's an internal-only docker network and bound to loopback inside the container. | `prod/shared/queue/config.py` |
| Audit | `auditd` enabled with 52 rules in `prod/deploy/auditd/cff-security.rules` (login events, sudo, ssh, cron, systemd, unauthorized file access). | `prod/deploy/auditd/` |
| Rootkit scan | Weekly `rkhunter --check` cron, output piped into Loki via `cff-files`. |
| Static assets | Served by FastAPI `StaticFiles` mount at `/static`, no directory listing. | `prod/main.py:251` |

OpenAPI docs (`/docs`, `/redoc`, `/openapi.json`) are disabled outside `ENV=development` (`prod/main.py:191..193`).

---

## 10. Deployment

### 10.1 The FastAPI process is **not** containerised

The application (cff-api + scheduler + 8 workers) runs as plain systemd units on the host:

```
/etc/systemd/system/cff-api.service
/etc/systemd/system/cff-scheduler.service
/etc/systemd/system/cff-publishing-worker.service
/etc/systemd/system/cff-voice-worker.service
/etc/systemd/system/cff-notification-worker.service
/etc/systemd/system/cff-dle-ingestion-worker.service
/etc/systemd/system/cff-dle-processor-worker.service
/etc/systemd/system/cff-shorts-worker.service
/etc/systemd/system/cff-stats-worker.service
/etc/systemd/system/cff-stream-control-worker.service
```

Source for each unit lives in `prod/deploy/systemd/`.

Standard deploy on `46.21.250.43`:

```bash
cd /opt/content-fabric
git pull
# If requirements changed:
.venv/bin/pip install -r prod/requirements.txt
# Restart the affected units (or all of them — they share the venv):
sudo systemctl restart cff-api.service
sudo systemctl restart 'cff-*-worker.service' cff-scheduler.service
```

Logs go to `/var/log/cff-<service>.log` (systemd `StandardOutput=append:`); promtail tails them as the `cff-files` job.

### 10.2 The observability stack **is** Docker

`prod/deploy/observability/docker-compose.yml` brings up Prometheus, Pushgateway, Node/Process Exporter, Loki, Promtail, Grafana, GlitchTip (web + worker + Postgres + Redis) on the `cff-observability_default` network. Bring up / down:

```bash
cd /opt/content-fabric/prod/deploy/observability
docker compose up -d
docker compose pull && docker compose up -d   # upgrade
```

Grafana is bound to `127.0.0.1:3001`; admins SSH-tunnel to it.

### 10.3 Database migrations

`database/migrations/*.sql` numbered sequentially. Backup → apply in order (see `database/DDL/SCHEMA_INDEX.md`). The `platform_schema_migrations` table tracks applied versions.

### 10.4 Tests

`prod/tests/` — currently **221 tests**, all passing under `pytest -q` against the venv. Test database isolation via `conftest.py` fixtures.

---

## 11. Decommissioned

| Component | Status | Notes |
|---|---|---|
| Yii / PHP backend | **Removed.** Code archived into `.legacy/yii/` in dev-only checkouts. Production server has no PHP runtime. The `feat/yii-integration` branch finalised the cutover; `scheduler/jobs.py:_YII_CRON` is the cron-emulator that replaced `shel_youtube*.sh`. |
| `unported/` | **Deleted.** All Python that was scaffolded there was either ported into `prod/` or dropped. |
| `proftpd` | **Disabled (May 2026).** FTP was the legacy upload path for media; replaced by `/api/v1/uploads` and direct worker-side downloads (yt-dlp, DLE clients). |
| Phase-N planning docs | Stale. Single source of truth is **this document** plus `database/DDL/SCHEMA_INDEX.md` and `docs/OBSERVABILITY.md`. |

---

## 12. Out of scope: tg-app

`tg-app` is a **separate project** that happens to live on the same host (46.21.250.43). It runs in its own Docker network, exposes its dev UI through an ngrok tunnel on **port 5173**, and has its own dependencies and lifecycle.

CFF and tg-app currently share nothing at runtime except the host. Per `feedback_tg_app.md` (strict rule):

- We **do not** modify any tg-app source files.
- We **do not** touch tg-app containers, environments, or compose files.
- We **do not** alter or rotate the tg-app ngrok tunnel.
- We **do not** add tg-app dependencies to CFF, or vice-versa.

Any cross-system integration request must be reviewed before any file in tg-app is touched.

---

## File map (quick index)

```
prod/
  main.py                       FastAPI app, middleware stack, /metrics, /health
  app/
    api/
      routes.py                 /api/v1 router aggregator
      deps.py                   get_current_user, get_current_admin
      endpoints/                auth, channels, tasks, templates, uploads,
                                streams, dle_sources, logs, admin
    core/
      auth.py                   cookie auth helpers, is_admin, scoped_where
      security.py               JWT encode/decode, password hashing
      config.py                 pydantic settings (CORS, DSNs, API keys)
    views/
      panel.py                  /panel/* — admin SSR
      app_portal.py             /app/* — user SSR (login, register, tasks…)
    templates/                  Jinja2 templates
    static/                     CSS/JS/icons
  scheduler/
    run.py                      60s polling loop
    jobs.py                     enqueue_pending_tasks, validate_channel_tokens,
                                collect_*_stats, _YII_CRON cron-emulator
  workers/
    _job_bootstrap.py           bootstrap_job(payload, name)
    publishing_worker.py        queue=publishing
    voice_worker.py             queue=voice
    notification_worker.py      queue=notifications
    dle_ingestion_worker.py     queue=dle_ingestion
    dle_processor_worker.py     queue=dle_processing (+sora dispatch)
    shorts_worker.py            queue=shorts
    stats_worker.py             queue=stats
    stream_worker.py            queue=stream_control
  shared/
    db/                         engine, models, repositories
    queue/                      Redis, RQ wiring, payloads, queue names
    youtube/                    OAuth refresh + reauth + resumable upload
    voice/                      RVC voice change
    ingestion/dle/              DLE pipeline + processor
    streams/                    live stream provisioner + systemd
    shorts/                     yt-dlp + Whisper + GPT pipeline
    sora/                       Sora scraper
    notifications/              telegram + email + manager
    metrics.py                  Prometheus metrics + sample_all + instrument_job
    logging_config.py           JSON logging + MetricsLogHandler
    logging_context.py          ContextVar-based trace_id propagation
    error_tracking.py           GlitchTip init
    env.py                      .env loader (import-side-effect)
  deploy/
    systemd/                    *.service files
    nginx/                      vhost configs (incl. /metrics allowlist)
    auditd/                     cff-security.rules + baseline scan
    observability/              docker-compose + Prom/Loki/Grafana/GlitchTip
database/
  DDL/                          *.sql per table + SCHEMA_INDEX.md
  migrations/                   numbered .sql migrations
docs/
  ARCHITECTURE.md               this file
  OBSERVABILITY.md              observability stack details
  PORTAL_GUIDE.md, REAUTH_GUIDE.md, NGINX_SETUP.md, ...
```
