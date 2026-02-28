# Content Fabric — Technical Reference (Developer)

> Last updated: 28.02.2026

---

## 1. Architecture Overview

```
                    ┌─────────────┐
                    │   Nginx :80 │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  FastAPI    │
                    │  API GW    │  :8000
                    │  (uvicorn) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼───┐ ┌──────▼──────┐
       │  shared/db   │ │Redis │ │  shared/env │
       │  (SQLAlchemy)│ │ :6379│ │  (.env load)│
       └──────┬──────┘ └──┬───┘ └─────────────┘
              │            │
       ┌──────▼──────┐    │
       │   MySQL     │    ├── publishing queue ──► Publishing Worker
       │   :3306     │    ├── notifications queue ► Notification Worker
       └─────────────┘    └── voice queue ────────► Voice Worker
                                    ▲
                              Scheduler (60s poll)
```

**Stack:** Python 3.10 · FastAPI · SQLAlchemy Core · Redis/rq · MySQL · Google API

---

## 2. Directory Structure

```
prod/
├── main.py                          # FastAPI app entry point + SSR panel mount
├── requirements.txt
├── requirements-test.txt            # Test dependencies (pytest, httpx, etc.)
├── pytest.ini                       # Pytest configuration
├── Dockerfile
├── docker-compose.yml               # All services
├── nginx-content-fabric.conf.example
│
├── app/                             # API Gateway
│   ├── api/
│   │   ├── deps.py                  # get_current_user() dependency
│   │   ├── routes.py                # Router aggregation
│   │   └── endpoints/
│   │       ├── admin.py             # GET /admin/dashboard, /users, /queue
│   │       ├── auth.py              # POST /login, /register, GET /me, 2FA
│   │       ├── channels.py          # CRUD channels + OAuth + stats
│   │       ├── tasks.py             # CRUD tasks + cancel + history + batch + calendar
│   │       ├── templates.py         # CRUD schedule templates
│   │       └── uploads.py           # POST /uploads/video, /uploads/thumbnail
│   ├── core/
│   │   ├── audit.py                 # JSON audit logger → /var/log/cff-audit.log
│   │   ├── config.py                # Settings (pydantic-settings)
│   │   ├── database.py              # Legacy DB bridge
│   │   └── security.py              # JWT create/verify, bcrypt
│   ├── schemas/
│   │   ├── auth.py                  # LoginRequest, RegisterRequest, TokenResponse
│   │   ├── channel.py               # ChannelCreate, ChannelResponse
│   │   └── task.py                  # TaskCreate, TaskUpdate, TaskResponse
│   ├── templates/                   # Jinja2 SSR templates
│   │   ├── base.html                # Admin panel layout (sidebar + content)
│   │   ├── dashboard.html           # Admin: system overview
│   │   ├── channels.html            # Admin: channel list
│   │   ├── tasks.html               # Admin: task list + stats
│   │   ├── users.html               # Admin: user management
│   │   ├── credentials.html         # Admin: login credentials + TOTP
│   │   ├── payment.html             # Admin: payment stub
│   │   ├── app_base.html            # User portal layout (sidebar + content)
│   │   ├── app_login.html           # User: login page (standalone)
│   │   ├── app_register.html        # User: register page (standalone)
│   │   ├── app_dashboard.html       # User: dashboard (stats + recent tasks)
│   │   ├── app_channels.html        # User: channel list
│   │   ├── app_channel_add.html     # User: add channel form
│   │   ├── app_tasks.html           # User: task list + filters
│   │   ├── app_task_new.html        # User: create task form
│   │   ├── app_templates.html       # User: schedule templates
│   │   └── app_settings.html        # User: profile + 2FA
│   └── views/
│       ├── app_portal.py            # User portal routes: /app/*
│       └── panel.py                 # Admin panel routes: /panel/* (admin-only)
│
├── shared/                          # Shared between API + workers + scheduler
│   ├── env.py                       # .env loader (import first!)
│   ├── db/
│   │   ├── connection.py            # SQLAlchemy engine + pool
│   │   ├── models.py                # Table definitions (15 tables)
│   │   └── repositories/
│   │       ├── channel_repo.py
│   │       ├── console_repo.py
│   │       ├── credential_repo.py
│   │       ├── task_repo.py
│   │       ├── user_repo.py
│   │       └── audit_repo.py
│   ├── queue/
│   │   ├── config.py                # Redis connection + queue names
│   │   ├── publisher.py             # enqueue_video_upload(), enqueue_notification()
│   │   └── types.py                 # VideoUploadPayload, NotificationPayload
│   ├── youtube/
│   │   ├── client.py                # create_service(), upload_video(), like_video()
│   │   ├── upload.py                # process_upload() — full pipeline
│   │   └── token_refresh.py         # OAuth token refresh
│   ├── notifications/
│   │   ├── telegram.py              # send() — lazy env reads
│   │   ├── email.py                 # send() — lazy env reads
│   │   └── manager.py               # Notification facade
│   └── voice/
│       └── changer.py               # Voice change wrapper (stub — ML deps required)
│
├── scheduler/
│   ├── run.py                       # Entry point (poll loop + signal handling)
│   └── jobs.py                      # enqueue_pending_tasks()
│
├── workers/
│   ├── publishing_worker.py         # rq worker: 'publishing' queue
│   ├── notification_worker.py       # rq worker: 'notifications' queue
│   └── voice_worker.py              # rq worker: 'voice' queue
│
├── tests/                           # Test suite (91 tests)
│   ├── conftest.py                  # Shared fixtures (mock DB, mock Redis, JWT)
│   ├── test_security.py             # JWT, password hashing, rate limits
│   ├── test_repos.py                # Repository layer (channel, task, user, credential)
│   ├── test_api_channels.py         # Channel endpoints
│   ├── test_api_tasks.py            # Task CRUD + cancel + reschedule
│   ├── test_api_auth.py             # Auth endpoints (register, login, 2FA)
│   ├── test_api_admin.py            # Admin endpoints
│   ├── test_api_templates.py        # Schedule template endpoints
│   ├── test_api_uploads.py          # File upload endpoints
│   └── test_upload_logic.py         # YouTube upload pipeline logic
│
└── deploy/
    └── systemd/                     # Systemd unit files
        ├── cff-api.service
        ├── cff-scheduler.service
        ├── cff-publishing-worker.service
        ├── cff-notification-worker.service
        └── cff-voice-worker.service
```

---

## 3. Environment Variables

Env files live in `prod/.env/` directory:

| File | Variables |
|------|-----------|
| `.env/.env.db` | `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` |
| `.env/.env.api` | `YOUTUBE_API_KEY` |
| Root `.env` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `REDIS_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` |

**Loading order matters:**

- FastAPI (`main.py`) → `app/core/config.py` loads `.env.db` + `.env.api` via pydantic-settings
- Workers/scheduler → `import shared.env` loads all three files (must be first import!)

```python
# In worker __main__ blocks:
if __name__ == "__main__":
    import shared.env  # noqa: F401 — BEFORE any shared imports
    from rq import Worker
    ...
```

---

## 4. Database

### Connection

`shared/db/connection.py` — singleton SQLAlchemy engine with pooling:

```python
pool_size=5, max_overflow=10, pool_recycle=3600, pool_pre_ping=True
```

All repositories use `get_connection()` context manager with auto-commit.

### Tables (15)

| Table | Purpose |
|-------|---------|
| `platform_users` | User accounts (with 2FA fields) |
| `platform_projects` | Projects grouping |
| `platform_project_members` | RBAC: user ↔ project roles |
| `platform_invitations` | Project invitations |
| `google_cloud_consoles` | OAuth client credentials |
| `platform_channels` | Connected channels + tokens |
| `platform_channel_login_credentials` | Login creds + TOTP + proxy |
| `content_upload_queue_tasks` | Main task queue |
| `media_library` | Uploaded media files |
| `schedule_templates` | Publishing templates |
| `schedule_template_slots` | Template time slots by weekday |
| `audit_log` | DB-level audit |
| `platform_settings` | Key-value settings |
| `user_totp_backup_codes` | 2FA backup codes |
| `channel_daily_stats` | Channel statistics by day |

### Task statuses

```
0 = pending      → scheduler picks up, enqueues to Redis
3 = processing   → worker grabbed it
1 = completed    → upload successful
2 = failed       → upload failed (error_message set)
4 = cancelled    → cancelled via API
```

---

## 5. API Endpoints

Base URL: `http://<host>:8000/api/v1`

### Auth (public)

| Method | Path | Body | Returns |
|--------|------|------|---------|
| `POST` | `/auth/register` | `{username, email, password, display_name?}` | `{access_token}` |
| `POST` | `/auth/login` | `{email, password, totp_code?}` | `{access_token}` |
| `GET` | `/auth/me` | — | `{id, uuid, username, email, ...}` |
| `POST` | `/auth/2fa/setup` | — | `{secret, qr_uri, backup_codes}` |
| `POST` | `/auth/2fa/verify` | `{code}` | `{status: "enabled"}` |
| `POST` | `/auth/2fa/disable` | `{code}` | `{status: "disabled"}` |

JWT in header: `Authorization: Bearer <token>`
Rate limits: login 10/min, register 5/min

### Channels (auth required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/channels/` | List all channels |
| `POST` | `/channels/` | Add channel |
| `GET` | `/channels/{id}` | Channel details |
| `DELETE` | `/channels/{id}` | Remove channel |
| `POST` | `/channels/{id}/refresh-token` | Refresh OAuth token |
| `GET` | `/channels/{id}/stats` | Daily stats for channel |

### Tasks (auth required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tasks/` | Create upload task |
| `POST` | `/tasks/batch` | Batch create (up to 100 tasks) |
| `GET` | `/tasks/` | List tasks (filters: `status`, `channel_id`, `from`, `to`, `limit`, `offset`) |
| `GET` | `/tasks/history` | Completed/failed/cancelled (same filters) |
| `GET` | `/tasks/calendar` | Tasks grouped by day |
| `GET` | `/tasks/stats/summary` | Aggregation by status |
| `GET` | `/tasks/{id}` | Task details |
| `PUT` | `/tasks/{id}` | Update (`scheduled_at`, `status`) |
| `POST` | `/tasks/{id}/cancel` | Cancel pending/processing task |
| `GET` | `/tasks/{id}/status` | Quick status check |
| `GET` | `/tasks/{id}/progress` | Redis-backed upload progress (stage + %) |
| `GET` | `/tasks/{id}/preview` | File info + YouTube URL |

### Uploads (auth required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/uploads/video` | Upload video file (mp4, mkv, avi, mov, etc., max 10GB) |
| `POST` | `/uploads/thumbnail` | Upload thumbnail (jpg, png, webp, max 50MB) |

### Schedule Templates (auth required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/templates/` | Create template with time slots |
| `GET` | `/templates/` | List templates |
| `GET` | `/templates/{id}` | Template details |
| `PUT` | `/templates/{id}` | Update template |
| `DELETE` | `/templates/{id}` | Delete template |

### Admin (auth required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/dashboard` | System overview (counts, queue sizes) |
| `GET` | `/admin/users` | All users with stats |
| `GET` | `/admin/queue` | Redis queue status |

### User Portal (cookie auth required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/app/login` | Login page |
| `POST` | `/app/login` | Login submit (email + password + optional TOTP) |
| `GET` | `/app/register` | Register page |
| `POST` | `/app/register` | Register submit |
| `GET` | `/app/logout` | Clear cookie, redirect to login |
| `GET` | `/app/` | User dashboard (stats + recent tasks) |
| `GET` | `/app/channels` | User's channel list |
| `GET` | `/app/channels/add` | Add channel form |
| `POST` | `/app/channels/add` | Add channel submit |
| `GET` | `/app/tasks` | Task list (filter by status/channel) |
| `GET` | `/app/tasks/new` | Create task form |
| `POST` | `/app/tasks/new` | Create task submit |
| `GET` | `/app/templates` | Schedule templates list |
| `GET` | `/app/settings` | Account settings (profile + 2FA) |

### SSR Admin Panel (cookie auth + admin role required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/panel/` | Dashboard (channels, tasks, queue overview) |
| `GET` | `/panel/channels` | Channel list with token status |
| `GET` | `/panel/tasks` | Task list + stats cards |
| `GET` | `/panel/users` | User management |
| `GET` | `/panel/credentials` | Login credentials + TOTP |
| `GET` | `/panel/payment` | Payment stub |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{"status": "healthy", "checks": {"api", "mysql", "redis"}}` |

---

## 6. Task Lifecycle

```
API: POST /tasks/
    │
    ▼
DB: status=0 (pending), scheduled_at=<future time>
    │
    ▼ (scheduler polls every 60s, finds scheduled_at <= NOW())
Redis: publishing queue ◄── enqueue_video_upload(payload)
    │                        DB: status=3 (processing)
    ▼
Worker: process_upload(payload)
    ├── Load channel + console from DB
    ├── Create YouTube service (auto-refresh token)
    ├── Upload video (resumable)
    ├── Set thumbnail
    ├── Auto-like
    ├── Post comment (if configured)
    └── Result:
        ├── OK → DB: status=1, upload_id=<youtube_id>
        └── Fail → DB: status=2, error_message=<err>
                   Telegram notification sent
```

Retry: `MAX_UPLOAD_ATTEMPTS = 2` — one retry after token refresh.

---

## 7. Running Locally

### Prerequisites

- Python 3.10+
- MySQL 8.0+
- Redis 7+

### Setup

```bash
cd prod
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Copy env files
cp .env.example .env
# Edit .env/.env.db and .env/.env.api with your credentials
```

### Docker (recommended)

```bash
cd prod
docker compose up -d
```

This starts: API (`:8000`), Redis (`:6379`), scheduler, publishing/notification/voice workers.

### Manual (without Docker)

Terminal 1 — API:
```bash
cd prod && source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Terminal 2 — Scheduler:
```bash
cd prod && source venv/bin/activate
python -m scheduler.run
```

Terminal 3 — Publishing Worker:
```bash
cd prod && source venv/bin/activate
python -m workers.publishing_worker
```

Terminal 4 — Notification Worker:
```bash
cd prod && source venv/bin/activate
python -m workers.notification_worker
```

---

## 8. Production Deployment

**Server:** 46.21.250.43 · Python 3.10 · venv (not Docker)
**Code path:** `/opt/content-fabric`
**Upload dirs:** `/opt/content-fabric/uploads/{videos,thumbnails}`

### Deploy changes

```bash
ssh user@46.21.250.43
cd /opt/content-fabric
git pull origin main

# Restart services via systemd
sudo systemctl restart cff-api
sudo systemctl restart cff-scheduler
sudo systemctl restart cff-publishing-worker
sudo systemctl restart cff-notification-worker

# Or quick restart (API only):
sudo systemctl restart cff-api
```

### Systemd services

| Service | Unit File | Description |
|---------|-----------|-------------|
| `cff-api` | `prod/deploy/systemd/cff-api.service` | FastAPI + SSR Panel (:8000) |
| `cff-scheduler` | `prod/deploy/systemd/cff-scheduler.service` | DB poller (60s interval) |
| `cff-publishing-worker` | `prod/deploy/systemd/cff-publishing-worker.service` | YouTube upload worker |
| `cff-notification-worker` | `prod/deploy/systemd/cff-notification-worker.service` | Telegram/email worker |
| `cff-voice-worker` | `prod/deploy/systemd/cff-voice-worker.service` | Voice change worker (stub) |

```bash
# Check status
sudo systemctl status cff-api cff-scheduler cff-publishing-worker cff-notification-worker

# View logs
sudo journalctl -u cff-api -f
sudo journalctl -u cff-scheduler --since "1 hour ago"
```

### Log files

| Log | Path |
|-----|------|
| API | `journalctl -u cff-api` |
| Scheduler | `journalctl -u cff-scheduler` |
| Publishing Worker | `journalctl -u cff-publishing-worker` |
| Notification Worker | `journalctl -u cff-notification-worker` |
| Audit | `/var/log/cff-audit.log` |

### Verify deployment

```bash
curl http://localhost:8000/health                   # → {"status":"healthy","checks":{...}}
curl http://localhost:8000/panel/                    # → SSR dashboard HTML
curl http://localhost:8000/api/v1/channels/ -H "Authorization: Bearer <JWT>"
```

### Running tests on prod

```bash
cd /opt/content-fabric/prod
source venv/bin/activate
pytest tests/ -v  # 91 tests expected
```

---

## 9. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **SQLAlchemy Core** (not ORM) | Raw SQL flexibility, no migration overhead for existing schema |
| **Redis + rq** (not Celery) | Simpler for single-server, 1-dev team; no broker overhead |
| **Shared package** | DB + queue + YouTube code shared between API and workers, no duplication |
| **Lazy env reads** in notifications | Module-level `os.environ.get()` runs at import time, before `.env` loads in workers |
| **`SELECT FOR UPDATE SKIP LOCKED`** | Prevents double-processing when legacy and new workers coexist |
| **Resumable uploads** | YouTube API requires chunked upload for large files; auto-retry on HTTP 5xx |
| **Systemd** on prod | Auto-restart, journalctl logging, proper process management |
| **Jinja2 SSR** for admin panel | No JS build step, fast development, server-side data access |

---

## 10. Known Issues & TODOs

| Issue | Priority | Assignee | Notes |
|-------|----------|----------|-------|
| SSL/HTTPS (certbot) | High | @mykytatishkin | No HTTPS, need Let's Encrypt certificates |
| Domain setup | High | @mykytatishkin | Currently accessed by IP only |
| 9 channels need VNC reauth | High | @mykytatishkin | Google "Verify it's you" security challenge (issue #96) |
| Voice worker ML porting | Medium | @mykytatishkin | Stub ready, needs torch/librosa/so-vits-svc + models (issue #100) |
| C++ watermark/subtitle module | Medium | @graf_crayt | Separate binary, called from API (issue #104) |
| Payment integration | Low | @mykytatishkin | UI stub ready, needs Stripe/LiqPay (issue #101) |
| YouTube LIVE streaming | Low | @mykytatishkin | Backlog (issue #102) |
| MySQL backups | Medium | @mykytatishkin | Need cron + mysqldump |
| `config.py` debug `_log()` calls | Low | — | Left from Cursor agent; safe to remove |
| Legacy task_worker | None | — | **Killed** on 28.02.2026 |

---

## 11. Migration History

| # | Migration | Description |
|---|-----------|-------------|
| 001 | `create_new_schema.sql` | Initial 13-table schema |
| 002 | `add_uuid_and_auth_to_users.sql` | User auth fields |
| 003 | `create_projects_and_rbac.sql` | Projects + RBAC |
| 004 | `create_invitations.sql` | Invitation system |
| 005 | `create_google_cloud_consoles.sql` | Multi-console OAuth |
| 006 | `migrate_data_to_new_schema.sql` | Data migration from legacy |
| 007 | `update_legacy_code_references.sql` | Legacy compat views |
| 008 | `add_media_library.sql` | Media library table |

All migrations are idempotent (`IF NOT EXISTS`) with matching rollback scripts.

---

## 12. Security

| Feature | Status |
|---------|--------|
| JWT authentication | Implemented (HS256, configurable expiry) |
| 2FA (TOTP) | Implemented (setup/verify/disable + backup codes) |
| Rate limiting | 10/min login, 5/min register, 120/min default |
| Security headers | X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, Referrer-Policy |
| CORS | Restricted methods/headers |
| Path traversal protection | `..` blocked in file paths |
| Swagger docs | Hidden in production (DEBUG=False) |
| Error sanitization | No stack traces in responses |
| Audit logging | All auth events + task operations → `/var/log/cff-audit.log` |

---

## 13. Test Suite

**91 tests** — all passing on production.

```bash
cd prod && pytest tests/ -v
```

| Test file | Count | What it covers |
|-----------|-------|----------------|
| `test_security.py` | 12 | JWT, bcrypt, rate limits, security headers |
| `test_repos.py` | 15 | All repository layer (channel, task, user, credential, console) |
| `test_api_channels.py` | 10 | Channel CRUD, OAuth refresh, stats |
| `test_api_tasks.py` | 14 | Task CRUD, cancel, reschedule, batch, calendar, progress |
| `test_api_auth.py` | 12 | Register, login, 2FA setup/verify/disable |
| `test_api_admin.py` | 6 | Admin dashboard, users, queue |
| `test_api_templates.py` | 8 | Schedule template CRUD |
| `test_api_uploads.py` | 5 | Video + thumbnail upload, validation |
| `test_upload_logic.py` | 9 | YouTube upload pipeline, retry logic, token refresh |

Dependencies: `pip install -r requirements-test.txt` (pytest, httpx<0.28, pytest-asyncio, pytest-mock)
