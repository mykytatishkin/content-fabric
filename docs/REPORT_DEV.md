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
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml               # All services
├── nginx-content-fabric.conf.example
│
├── app/                             # API Gateway
│   ├── api/
│   │   ├── deps.py                  # get_current_user() dependency
│   │   ├── routes.py                # Router aggregation
│   │   └── endpoints/
│   │       ├── auth.py              # POST /login, /register, GET /me
│   │       ├── channels.py          # CRUD channels + OAuth
│   │       └── tasks.py             # CRUD tasks + cancel + history
│   ├── core/
│   │   ├── audit.py                 # JSON audit logger → /var/log/cff-audit.log
│   │   ├── config.py                # Settings (pydantic-settings)
│   │   ├── database.py              # Legacy DB bridge
│   │   └── security.py              # JWT create/verify, bcrypt
│   └── schemas/
│       ├── auth.py                  # LoginRequest, RegisterRequest, TokenResponse
│       ├── channel.py               # ChannelCreate, ChannelResponse
│       └── task.py                  # TaskCreate, TaskUpdate, TaskResponse
│
├── shared/                          # Shared between API + workers + scheduler
│   ├── env.py                       # .env loader (import first!)
│   ├── db/
│   │   ├── connection.py            # SQLAlchemy engine + pool
│   │   ├── models.py                # Table definitions (13 tables)
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
│       └── changer.py               # Voice change wrapper
│
├── scheduler/
│   ├── run.py                       # Entry point (poll loop + signal handling)
│   └── jobs.py                      # enqueue_pending_tasks()
│
└── workers/
    ├── publishing_worker.py         # rq worker: 'publishing' queue
    ├── notification_worker.py       # rq worker: 'notifications' queue
    └── voice_worker.py              # rq worker: 'voice' queue
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

### Tables (13)

| Table | Purpose |
|-------|---------|
| `users` | User accounts |
| `projects` | Projects grouping |
| `project_members` | RBAC: user ↔ project roles |
| `invitations` | Project invitations |
| `google_cloud_consoles` | OAuth client credentials |
| `youtube_channels` | Connected channels + tokens |
| `channel_credentials` | Extra channel creds |
| `content_upload_queue_tasks` | Main task queue |
| `media_library` | Uploaded media files |
| `templates` | Publishing templates |
| `template_items` | Template schedule items |
| `audit_log` | DB-level audit |
| `settings` | Key-value settings |

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
| `POST` | `/auth/login` | `{email, password}` | `{access_token}` |
| `GET` | `/auth/me` | — | `{id, uuid, username, email, ...}` |

JWT in header: `Authorization: Bearer <token>`

### Channels (auth required)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/channels/` | List all channels |
| `POST` | `/channels/` | Add channel |
| `GET` | `/channels/{id}` | Channel details |
| `DELETE` | `/channels/{id}` | Remove channel |
| `POST` | `/channels/{id}/refresh-token` | Refresh OAuth token |

### Tasks (auth required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/tasks/` | Create upload task |
| `GET` | `/tasks/` | List tasks (filters: `status`, `channel_id`, `from`, `to`, `limit`, `offset`) |
| `GET` | `/tasks/history` | Completed/failed/cancelled (same filters) |
| `GET` | `/tasks/{id}` | Task details |
| `PUT` | `/tasks/{id}` | Update (`scheduled_at`, `status`) |
| `POST` | `/tasks/{id}/cancel` | Cancel pending/processing task |
| `GET` | `/tasks/{id}/status` | Quick status check |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | `{"status": "ok"}` |

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

### Deploy changes

```bash
ssh user@46.21.250.43
cd /root/cff
git pull origin main

# Restart services
kill $(pgrep -f "uvicorn main:app")
cd prod && source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /var/log/cff-api.log 2>&1 &

# Restart scheduler
kill $(pgrep -f "scheduler.run")
nohup python -m scheduler.run > /var/log/cff-scheduler.log 2>&1 &

# Restart workers
kill $(pgrep -f "publishing_worker")
nohup python -m workers.publishing_worker > /var/log/cff-publishing-worker.log 2>&1 &

kill $(pgrep -f "notification_worker")
nohup python -m workers.notification_worker > /var/log/cff-notification-worker.log 2>&1 &
```

### Log files

| Log | Path |
|-----|------|
| API | `/var/log/cff-api.log` |
| Scheduler | `/var/log/cff-scheduler.log` |
| Publishing Worker | `/var/log/cff-publishing-worker.log` |
| Notification Worker | `/var/log/cff-notification-worker.log` |
| Audit | `/var/log/cff-audit.log` |

### Verify deployment

```bash
curl http://localhost:8000/api/v1/health           # → {"status":"ok"}
curl http://localhost:8000/api/v1/channels/ -H "Authorization: Bearer <JWT>"
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
| **nohup** (not systemd) on prod | Quick deployment; TODO: create systemd units for auto-restart |

---

## 10. Known Issues & TODOs

| Issue | Priority | Notes |
|-------|----------|-------|
| `config.py` has debug `_log()` calls | Low | Left from Cursor agent debugging; safe to remove |
| No systemd services | Medium | Services restart manually after server reboot |
| JWT secret from env | Medium | Currently loaded from `JWT_SECRET_KEY` env var; ensure it's set on prod |
| Legacy task_worker still running | Low | Will be decommissioned after 1-week parallel run |
| Old tasks with wrong paths | None | 18 tasks failed because files reference old server; expected |

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
