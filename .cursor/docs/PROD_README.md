# Content Fabric — Production Microservices

## Architecture

```
                          +----------------+
                          |   Nginx        |
                          |  :80 / :443    |
                          +-------+--------+
                                  |
                          +-------v--------+
                          |   FastAPI       |
                          |   (uvicorn)     |
                          |   :8000         |
                          +---+----+---+---+
                              |    |   |
              +---------------+    |   +---------------+
              |                    |                   |
      +-------v------+   +--------v-------+   +-------v------+
      |   MySQL       |   |   Redis 7      |   |  Telegram    |
      |   :3306       |   |   :6379        |   |  Bot API     |
      |   (external)  |   |   (queues)     |   |              |
      +-------+-------+   +---+----+---+---+   +--------------+
              |                |    |   |
              |        +-------+    |   +-------+
              |        |            |           |
      +-------v--+  +--v--------+  +--v------+ +--v-----------+
      | Scheduler |  | Pub.     |  | Notif.  | | Voice        |
      | (60s poll)|  | Worker   |  | Worker  | | Worker       |
      +----------+  +----------+  +---------+ +--------------+
```

### Services

| Service | Entry Point | Queue | Description |
|---------|------------|-------|-------------|
| **API** | `uvicorn main:app` | — | FastAPI gateway, REST endpoints |
| **Scheduler** | `python -m scheduler.run` | — | Polls DB every 60s, enqueues pending tasks |
| **Publishing Worker** | `python -m workers.publishing_worker` | `publishing` | YouTube video uploads via resumable upload |
| **Notification Worker** | `python -m workers.notification_worker` | `notifications` | Telegram/Email notifications |
| **Voice Worker** | `python -m workers.voice_worker` | `voice` | Voice change processing |

### Tech Stack

- **Python 3.10+**, FastAPI 0.109, Pydantic 2.5
- **MySQL** (content_fabric DB, 15 tables)
- **Redis 7** + **rq** (task queues)
- **SQLAlchemy Core** (connection pooling, not ORM)
- **JWT** auth (python-jose + passlib/bcrypt)
- **YouTube Data API v3** (google-api-python-client)

---

## Directory Structure

```
prod/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml               # Full stack (6 services)
├── .env.example
│
├── app/                             # API layer
│   ├── api/
│   │   ├── deps.py                  # get_current_user (JWT)
│   │   ├── routes.py                # Router includes
│   │   └── endpoints/
│   │       ├── auth.py              # POST /auth/login, /register, GET /me
│   │       ├── channels.py          # Channel CRUD
│   │       └── tasks.py             # Task CRUD (protected)
│   ├── core/
│   │   ├── config.py                # Settings (Pydantic)
│   │   ├── security.py              # JWT creation/verification
│   │   └── database.py
│   ├── schemas/
│   │   ├── auth.py                  # LoginRequest, RegisterRequest, TokenResponse
│   │   ├── channel.py               # Channel, ChannelCreate
│   │   └── task.py                  # TaskCreate, TaskResponse, TaskListResponse
│   └── repositories/
│       └── channel_repository.py    # Thin wrapper over shared layer
│
├── shared/                          # Shared between API and workers
│   ├── env.py                       # Loads .env files (for workers)
│   ├── logging_config.py            # Centralized logging (JSON + plain)
│   ├── db/
│   │   ├── connection.py            # SQLAlchemy engine + pool
│   │   ├── models.py                # 13 table definitions
│   │   ├── utils.py                 # Shared DB helpers (serialize, build_update)
│   │   └── repositories/
│   │       ├── channel_repo.py      # Channel CRUD
│   │       ├── task_repo.py         # Task lifecycle
│   │       ├── console_repo.py      # OAuth consoles
│   │       ├── credential_repo.py   # RPA login credentials
│   │       ├── audit_repo.py        # Reauth audit log
│   │       └── user_repo.py         # User CRUD (auth)
│   ├── queue/
│   │   ├── config.py                # Redis connection + queue names
│   │   ├── types.py                 # Payload dataclasses
│   │   └── publisher.py             # enqueue_* functions
│   ├── youtube/
│   │   ├── client.py                # YouTube API (upload, thumbnail, like, comment)
│   │   ├── upload.py                # Upload orchestration
│   │   └── token_refresh.py         # OAuth token refresh
│   ├── notifications/
│   │   ├── telegram.py              # Telegram Bot API
│   │   ├── email.py                 # SMTP sender
│   │   └── manager.py              # Notification routing
│   └── voice/
│       └── changer.py               # Voice change wrapper
│
├── scheduler/
│   ├── run.py                       # Entry point (polling loop)
│   └── jobs.py                      # enqueue_pending_tasks()
│
└── workers/
    ├── publishing_worker.py         # rq worker for YouTube uploads
    ├── notification_worker.py       # rq worker for notifications
    └── voice_worker.py              # rq worker for voice changes
```

---

## API Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |

### Auth (`/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register (username, email, password) |
| POST | `/auth/login` | Login (email, password) -> JWT |
| GET | `/auth/me` | Current user info (protected) |

### Channels (`/api/v1/channels`) — protected (JWT required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/channels/` | List all channels |
| GET | `/channels/{id}` | Get channel by ID |
| POST | `/channels/` | Create channel |
| GET | `/channels/form` | Web form for adding channels |
| GET | `/channels/google-consoles` | List OAuth consoles |

### Tasks (`/api/v1/tasks`) — protected (JWT required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks/` | List tasks (filter: status, channel_id, limit) |
| POST | `/tasks/` | Create upload task |
| GET | `/tasks/{id}` | Get task details |
| PUT | `/tasks/{id}` | Update task (status, error_message) |
| GET | `/tasks/{id}/status` | Quick status check |

---

## Configuration

### Environment Files

```
prod/.env/.env.db          # MySQL credentials
prod/.env/.env.api         # YouTube API key
/opt/content-fabric/.env   # Root: Telegram, Redis, JWT, etc.
```

### Required Variables

```bash
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=content_fabric
MYSQL_USER=content_fabric_user
MYSQL_PASSWORD=<secret>

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=<random-secret>

# Telegram notifications
TELEGRAM_BOT_TOKEN=<bot-token>
TELEGRAM_CHAT_ID=<chat-id>

# YouTube API
YOUTUBE_API_KEY=<api-key>
```

---

## Deployment (Production)

### Server: 46.21.250.43

```bash
# Pull latest code
cd /opt/content-fabric && git pull origin main

# Install dependencies (if changed)
cd prod && source venv/bin/activate && pip install -r requirements.txt

# Restart all services
systemctl restart cff-api cff-scheduler cff-publishing-worker cff-notification-worker

# If bytecache stale after code changes:
find /opt/content-fabric/prod -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
systemctl restart cff-api cff-scheduler cff-publishing-worker cff-notification-worker
```

### systemd Services

All services run via systemd. Management commands:

```bash
# Status
systemctl status cff-api cff-scheduler cff-publishing-worker cff-notification-worker

# Restart all
systemctl restart cff-api cff-scheduler cff-publishing-worker cff-notification-worker

# Restart one
systemctl restart cff-scheduler
```

### Log Files & Monitoring

| Service | Log Path | systemd unit |
|---------|----------|-------------|
| API | `/var/log/cff-api.log` | `cff-api.service` |
| Scheduler | `/var/log/cff-scheduler.log` | `cff-scheduler.service` |
| Publishing Worker | `/var/log/cff-publishing-worker.log` | `cff-publishing-worker.service` |
| Notification Worker | `/var/log/cff-notification-worker.log` | `cff-notification-worker.service` |
| Voice Worker | `/var/log/cff-voice-worker.log` | `cff-voice-worker.service` |
| Nginx | `/var/log/nginx/access.log`, `/var/log/nginx/error.log` | `nginx.service` |

**Real-time log viewing:**

```bash
# API errors
journalctl -u cff-api -f --no-pager
tail -f /var/log/cff-api.log | grep -i error

# Scheduler
tail -f /var/log/cff-scheduler.log

# All CFF services
journalctl -u 'cff-*' -f --no-pager

# Last 100 errors across all CFF services
journalctl -u 'cff-*' -p err --since "1 hour ago" --no-pager
```

**Panel monitoring:**

- Health check: `http://46.21.250.43/panel/health` — service status, disk/memory, queues
- Live logs: `http://46.21.250.43/panel/logs` — journalctl viewer with filters
- Health API: `http://46.21.250.43/health` — JSON health endpoint

### Common Errors & Troubleshooting

| Error | Where to look | Fix |
|-------|--------------|-----|
| `Unknown column 'TaskStatus.PENDING'` | `/var/log/cff-scheduler.log` | Use `.value` on IntEnum in SQL queries |
| `Timeout waiting for authorization` | `channel_reauth_audit_logs` table | Manual VNC reauth or fix RPA module |
| `Port 8080 is already in use` | `/var/log/cff-scheduler.log` | Kill stale OAuth callback server |
| `invalid_grant` / token expired | Task error_message in DB | Reauthorize channel |
| 502 Bad Gateway | Nginx error log | Restart cff-api, check port 8000 |
| MySQL connection refused | Any service log | Check MySQL service: `systemctl status mysql` |

### Verification

```bash
# Health check
curl http://localhost:8000/health

# Channels (should return 200)
curl http://localhost:8000/api/v1/channels/

# Get JWT token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@cff.local","password":"TestPass123"}'

# List tasks (with token)
curl http://localhost:8000/api/v1/tasks/ \
  -H "Authorization: Bearer <token>"

# Check all processes
ps aux | grep -E 'uvicorn|scheduler|worker' | grep -v grep
```

### Docker (alternative)

```bash
cd prod
docker compose up -d
```

Services: api, publishing-worker, notification-worker, voice-worker, scheduler, redis.

---

## Task Lifecycle

```
Task Created (status=0)
      |
      v
Scheduler polls (every 60s)
      |
      v
Mark as Processing (status=3)
      |
      v
Enqueue to Redis (publishing queue)
      |
      v
Publishing Worker picks up
      |
      +---> Upload to YouTube (resumable)
      |       |
      |       +---> Success: mark Completed (status=1)
      |       |       - save upload_id
      |       |       - set thumbnail
      |       |       - auto-like
      |       |       - post comment
      |       |
      |       +---> Failure: retry once, then mark Failed (status=2)
      |               - save error_message
      |               - send Telegram notification
```

Status codes: `0`=pending, `1`=completed, `2`=failed, `3`=processing, `4`=cancelled.

---

## Database

Uses MySQL database `content_fabric` with 15 tables. Schema managed via SQL migrations in `/database/DDL/migrations/`.

Key tables: `platform_channels`, `platform_oauth_credentials`, `content_upload_queue_tasks`, `platform_users`, `platform_projects`, `schedule_templates`, `schedule_template_slots`.

**UUID columns:** `platform_channels`, `content_upload_queue_tasks`, and `schedule_templates` have a `uuid VARCHAR(36) NOT NULL UNIQUE` column used as external identifier in portal URLs (instead of integer IDs) to prevent IDOR attacks.

**User-scoped data:** Portal filters data by `created_by` column — regular users see only their own channels/tasks/templates, admins see all.

See [database/DDL/SCHEMA_INDEX.md](../database/DDL/SCHEMA_INDEX.md) for full schema documentation.
