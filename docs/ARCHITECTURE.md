# Content Fabric (CFF) — Full Architecture Documentation

> Version: 2.0 | Date: 2026-03-21 | 39 channels, 5752 tasks, 10 users

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONTENT FABRIC (CFF)                             │
│                                                                         │
│   Automated video content production & publishing platform              │
│   YouTube • TikTok • Instagram                                          │
│                                                                         │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│   │ 39       │  │ 5752     │  │ 10       │  │ 7        │              │
│   │ Channels │  │ Tasks    │  │ Users    │  │ OAuth    │              │
│   │          │  │ 3513 ✓   │  │          │  │ Consoles │              │
│   │          │  │ 2239 ✗   │  │          │  │          │              │
│   └──────────┘  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure

```
                    ┌─────────────────────────────────────┐
                    │         INTERNET / USERS             │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │     SERVER: 46.21.250.43              │
                    │     ZOMRO Hosting                     │
                    │     Xeon E5-2430v2 • 32GB RAM         │
                    │     Quadro P2000 (GPU)                │
                    │     Ubuntu 22.04 LTS                  │
                    │     220 GB SSD                        │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼────────┐ ┌────────▼────────┐ ┌────────▼────────┐
    │   Nginx :80/:443 │ │   FASTPANEL     │ │   MySQL :3306   │
    │   Reverse Proxy  │ │   Control Panel │ │   content_fabric│
    │   → :8000        │ │   :8888         │ │   28 tables     │
    │                  │ │                  │ │   InnoDB        │
    │  HSTS enabled    │ │  HTTPS intercept│ │                 │
    │  server_tokens   │ │  (blocks custom │ │  User:          │
    │  off             │ │   HTTPS certs)  │ │  content_fabric │
    └──────────────────┘ └─────────────────┘ │  _user          │
                                              └─────────────────┘
```

---

## 3. Service Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     systemd services                                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    cff-api.service                           │    │
│  │                                                             │    │
│  │  uvicorn main:app --host 127.0.0.1 --port 8000             │    │
│  │  WorkingDirectory: /opt/content-fabric/prod                 │    │
│  │  Log: /var/log/cff-api.log                                  │    │
│  │                                                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │    │
│  │  │ REST API │  │ Web      │  │ Admin    │                  │    │
│  │  │ /api/v1/ │  │ Portal   │  │ Panel    │                  │    │
│  │  │          │  │ /app/*   │  │ /panel/* │                  │    │
│  │  │ Bearer   │  │ Cookie   │  │ Cookie   │                  │    │
│  │  │ JWT      │  │ JWT      │  │ JWT      │                  │    │
│  │  └──────────┘  └──────────┘  └──────────┘                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                    ┌─────────▼─────────┐                            │
│                    │   Redis :6379     │                             │
│                    │   3 queues:       │                             │
│                    │   • publishing    │                             │
│                    │   • notifications │                             │
│                    │   • voice         │                             │
│                    └──┬──────┬─────┬──┘                             │
│                       │      │     │                                 │
│  ┌────────────────────▼──┐ ┌─▼─────▼────────────────────┐          │
│  │ cff-scheduler.service │ │ Workers (3 services)        │          │
│  │                       │ │                             │          │
│  │ Polls DB every 60s    │ │ cff-publishing-worker       │          │
│  │ Finds PENDING tasks   │ │   → YouTube upload          │          │
│  │ Marks PROCESSING      │ │   → 30min timeout           │          │
│  │ Pushes to Redis       │ │                             │          │
│  │                       │ │ cff-notification-worker     │          │
│  │ Log: /var/log/        │ │   → Telegram/Email          │          │
│  │   cff-scheduler.log   │ │   → 2min timeout            │          │
│  │                       │ │                             │          │
│  │                       │ │ cff-voice-worker            │          │
│  │                       │ │   → Voice change (RVC/ML)   │          │
│  └───────────────────────┘ └─────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Request Flow

### 4.1 API Request (Bearer JWT)

```
  Client                    Nginx                   FastAPI
    │                         │                        │
    │  GET /api/v1/tasks/     │                        │
    │  Authorization: Bearer  │                        │
    │  eyJhbGci...            │                        │
    ├────────────────────────►│                        │
    │                         │  proxy_pass :8000      │
    │                         ├───────────────────────►│
    │                         │                        │
    │                         │     deps.py            │
    │                         │     get_current_user() │
    │                         │     decode JWT         │
    │                         │     load user from DB  │
    │                         │     check status       │
    │                         │          │             │
    │                         │     endpoints/tasks.py │
    │                         │     scoped query       │
    │                         │     (admin=all,        │
    │                         │      user=own only)    │
    │                         │          │             │
    │                         │◄─────────┘             │
    │  200 JSON               │                        │
    │◄────────────────────────┤                        │
```

### 4.2 Portal Request (Cookie JWT)

```
  Browser                   Nginx                   FastAPI
    │                         │                        │
    │  GET /app/channels      │                        │
    │  Cookie: cff_token=...  │                        │
    ├────────────────────────►│                        │
    │                         ├───────────────────────►│
    │                         │                        │
    │                         │     auth.py            │
    │                         │     require_user()     │
    │                         │     read cookie        │
    │                         │     decode JWT         │
    │                         │          │             │
    │                         │     app_portal.py      │
    │                         │     scoped_where()     │
    │                         │     SQL query          │
    │                         │          │             │
    │                         │     Jinja2 template    │
    │                         │     render HTML        │
    │                         │          │             │
    │  200 HTML               │◄─────────┘             │
    │◄────────────────────────┤                        │
```

---

## 5. Task Lifecycle (Publishing Pipeline)

```
  ┌──────────────┐
  │  USER creates │     POST /api/v1/tasks/ or /app/tasks/new
  │  upload task  │     status = 0 (PENDING)
  │  scheduled_at │     scheduled_at = future datetime
  └──────┬───────┘
         │
         ▼
  ┌──────────────┐
  │  SCHEDULER    │     Polls DB every 60 seconds
  │  (cff-        │     SELECT ... WHERE status=0
  │   scheduler)  │       AND scheduled_at <= NOW()
  │               │
  │  Finds task   │     UPDATE status = 3 (PROCESSING)
  │  Enqueues     │     enqueue_video_upload(payload)
  └──────┬───────┘
         │
         ▼ Redis queue: "publishing"
  ┌──────────────┐
  │  PUBLISHING   │     Picks up from Redis
  │  WORKER       │
  │               │     1. Load channel tokens
  │               │     2. Load OAuth console (client_id/secret)
  │               │     3. Refresh access_token if expired
  │               │     4. Upload video (resumable upload)
  │               │     5. Set thumbnail
  │               │     6. Auto-like video
  │               │     7. Post comment
  │               │
  └──────┬───────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 ┌──────┐  ┌──────┐
 │  ✓   │  │  ✗   │
 │  OK  │  │ FAIL │
 └──┬───┘  └──┬───┘
    │         │
    ▼         ▼
 status=1   status=2
 COMPLETED  FAILED
 save       save error_message
 upload_id  retry_count++
            │
            ▼
         ┌──────────────┐
         │ NOTIFICATION  │     Telegram message:
         │ WORKER        │     "Помилка завантаження"
         │               │     channel, error, timestamp
         └──────────────┘
```

### Task Status Codes

```
  ┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐
  │  0  │────►│  3  │────►│  1  │     │  2  │     │  4  │
  │PEND │     │PROC │     │DONE │     │FAIL │     │CANC │
  │ING  │     │ESS  │     │     │     │     │     │ELLED│
  └─────┘     └──┬──┘     └─────┘     └─────┘     └─────┘
                 │                       ▲
                 └───────────────────────┘
                      on error
```

---

## 6. OAuth / Reauthorization Flow

### 6.1 Web Portal OAuth (Browser-based)

```
  User Browser              CFF Server              Google
      │                         │                      │
      │  Click "Authorize"      │                      │
      │  /app/channels/{uuid}/  │                      │
      │  authorize              │                      │
      ├────────────────────────►│                      │
      │                         │                      │
      │  302 Redirect           │                      │
      │  → accounts.google.com  │                      │
      │  /o/oauth2/v2/auth      │                      │
      │  ?client_id=...         │                      │
      │  &redirect_uri=         │                      │
      │   /app/oauth/callback   │                      │
      │◄────────────────────────┤                      │
      │                         │                      │
      │  User logs in to Google │                      │
      ├───────────────────────────────────────────────►│
      │                         │                      │
      │  User grants consent    │                      │
      │◄──────────────────────────────────────────────┤
      │                         │                      │
      │  302 → /app/oauth/      │                      │
      │  callback?code=...      │                      │
      ├────────────────────────►│                      │
      │                         │  POST /token         │
      │                         │  code → tokens       │
      │                         ├─────────────────────►│
      │                         │                      │
      │                         │  access_token        │
      │                         │  refresh_token       │
      │                         │◄─────────────────────┤
      │                         │                      │
      │                         │  Save to DB:         │
      │                         │  platform_channels   │
      │                         │  .access_token       │
      │                         │  .refresh_token      │
      │                         │  .token_expires_at   │
      │                         │                      │
      │  302 → channel detail   │                      │
      │  ?authorized=1          │                      │
      │◄────────────────────────┤                      │
```

### 6.2 CLI Reauth (Selenium + SSH Tunnel)

```
  Developer PC              Server (SSH)            Google
      │                         │                      │
      │  ssh -L 8080:           │                      │
      │  localhost:8080         │                      │
      │  root@46.21.250.43     │                      │
      ├────────────────────────►│                      │
      │                         │                      │
      │  python -m cli.reauth   │                      │
      │  --channel-id 9         │                      │
      │  --no-browser           │                      │
      │                         │                      │
      │                         │  InstalledAppFlow     │
      │                         │  starts HTTP server   │
      │                         │  on :8080             │
      │                         │                      │
      │  Prints OAuth URL       │                      │
      │◄────────────────────────┤                      │
      │                         │                      │
      │  Open URL in browser    │                      │
      ├───────────────────────────────────────────────►│
      │                         │                      │
      │  Authorize in Google    │                      │
      │◄──────────────────────────────────────────────┤
      │                         │                      │
      │  Redirect to            │                      │
      │  localhost:8080         │                      │
      │  (SSH tunnel → server)  │                      │
      ├────────────────────────►│                      │
      │                         │  Capture code         │
      │                         │  Exchange for tokens  │
      │                         │  Save to DB           │
      │                         │                      │
      │  "Tokens updated for    │                      │
      │   channel BazaAudioKnig"│                      │
      │◄────────────────────────┤                      │
```

---

## 7. Directory Structure

```
content-fabric/
│
├── prod/                              ← MAIN CODEBASE (13,957 lines Python)
│   │
│   ├── main.py                        ← FastAPI app entry point
│   ├── requirements.txt               ← 24 dependencies
│   ├── Dockerfile                     ← Docker build
│   ├── docker-compose.yml             ← Full stack (6 services)
│   ├── .env.example                   ← Env template
│   │
│   ├── app/                           ← API + Views layer
│   │   ├── api/
│   │   │   ├── deps.py                ← get_current_user() — Bearer JWT
│   │   │   ├── routes.py              ← Router includes
│   │   │   └── endpoints/
│   │   │       ├── auth.py            ← POST /login, /register, GET /me
│   │   │       ├── channels.py        ← Channel CRUD
│   │   │       ├── tasks.py           ← Task CRUD
│   │   │       ├── templates.py       ← Schedule template CRUD
│   │   │       ├── uploads.py         ← File upload (10GB limit)
│   │   │       └── admin.py           ← Admin-only endpoints
│   │   │
│   │   ├── core/
│   │   │   ├── config.py              ← Settings (Pydantic), BASE_URL
│   │   │   ├── security.py            ← JWT create/decode, password hash
│   │   │   ├── auth.py                ← require_user(), scoped_where()
│   │   │   └── database.py            ← DB session helpers
│   │   │
│   │   ├── schemas/                   ← Pydantic v2 request/response
│   │   │   ├── auth.py                ← LoginRequest, TokenResponse
│   │   │   ├── channel.py             ← Channel, ChannelCreate
│   │   │   ├── task.py                ← TaskCreate, TaskResponse
│   │   │   └── template.py            ← TemplateCreate, SlotCreate
│   │   │
│   │   ├── views/
│   │   │   ├── app_portal.py          ← SSR User Portal (1400+ lines)
│   │   │   └── panel.py               ← SSR Admin Panel
│   │   │
│   │   └── templates/                 ← Jinja2 HTML (27 files, 2286 lines)
│   │       ├── app_base.html          ← Base layout (sidebar, nav)
│   │       ├── app_dashboard.html     ← Dashboard stats
│   │       ├── app_channels.html      ← Channel list
│   │       ├── app_channel_detail.html← Channel detail + credentials
│   │       ├── app_tasks.html         ← Task list with filters
│   │       ├── app_task_detail.html   ← Task detail + reschedule
│   │       ├── app_reauth.html        ← Batch reauthorization
│   │       ├── app_totp.html          ← TOTP management
│   │       ├── app_settings.html      ← User settings + 2FA
│   │       ├── base.html              ← Admin panel base
│   │       ├── health.html            ← System health
│   │       └── logs.html              ← Log viewer
│   │
│   ├── shared/                        ← Shared between API + Workers
│   │   ├── env.py                     ← .env loader
│   │   ├── logging_config.py          ← JSON/plain logging
│   │   │
│   │   ├── db/
│   │   │   ├── connection.py          ← SQLAlchemy engine + pool
│   │   │   ├── models.py             ← 15 table definitions + IntEnums
│   │   │   ├── utils.py               ← serialize_json, build_update
│   │   │   └── repositories/         ← Data access layer (8 repos)
│   │   │       ├── user_repo.py       ← User CRUD, 2FA, backup codes
│   │   │       ├── channel_repo.py    ← Channel CRUD, token update
│   │   │       ├── task_repo.py       ← Task lifecycle
│   │   │       ├── template_repo.py   ← Schedule templates + slots
│   │   │       ├── credential_repo.py ← RPA login credentials
│   │   │       ├── console_repo.py    ← OAuth consoles
│   │   │       ├── stats_repo.py      ← Channel statistics
│   │   │       └── audit_repo.py      ← Reauth audit log
│   │   │
│   │   ├── queue/
│   │   │   ├── config.py              ← Redis connection + queue names
│   │   │   ├── publisher.py           ← enqueue_video_upload(), etc.
│   │   │   └── types.py              ← Payload dataclasses
│   │   │
│   │   ├── youtube/
│   │   │   ├── client.py              ← upload_video(), set_thumbnail()
│   │   │   ├── upload.py              ← process_upload() pipeline
│   │   │   ├── token_refresh.py       ← OAuth token auto-refresh
│   │   │   └── reauth/               ← Automated reauthorization
│   │   │       ├── selenium_auth.py   ← Selenium + undetected-chromedriver
│   │   │       ├── service.py         ← Orchestration (DB → OAuth → tokens)
│   │   │       └── models.py          ← ReauthResult, ReauthStatus
│   │   │
│   │   ├── notifications/
│   │   │   ├── telegram.py            ← send() → Telegram Bot API
│   │   │   ├── email.py               ← SMTP sender
│   │   │   └── manager.py            ← Notification routing
│   │   │
│   │   └── voice/                     ← Voice conversion (ML)
│   │       ├── changer.py             ← Worker interface
│   │       ├── voice_changer.py       ← VoiceChanger (RVC-based)
│   │       ├── mixer.py               ← Audio background mixing
│   │       ├── silero.py              ← Silero TTS
│   │       ├── prosody.py             ← Prosody transfer
│   │       └── rvc/                   ← RVC voice conversion
│   │
│   ├── cli/
│   │   └── reauth.py                  ← YouTube re-auth CLI tool
│   │
│   ├── scheduler/
│   │   ├── run.py                     ← Entry point (60s polling loop)
│   │   └── jobs.py                    ← enqueue_pending_tasks()
│   │
│   ├── workers/
│   │   ├── publishing_worker.py       ← rq worker for YouTube uploads
│   │   ├── notification_worker.py     ← rq worker for notifications
│   │   └── voice_worker.py            ← rq worker for voice changes
│   │
│   └── tests/                         ← 204 tests (18 files)
│       ├── conftest.py                ← Fixtures, mocked DB
│       ├── test_api_auth.py
│       ├── test_api_channels.py
│       ├── test_api_tasks.py
│       └── ...
│
├── database/
│   └── DDL/
│       ├── migrations/                ← SQL migrations
│       └── SCHEMA_INDEX.md           ← Schema documentation
│
├── deploy/
│   ├── systemd/                       ← Service files (5)
│   ├── nginx/                         ← Nginx config
│   ├── logrotate-cff                  ← Log rotation
│   └── install-services.sh           ← Deployment script
│
├── cpp/video/                         ← C++ module (@graf_crayt)
│   ├── src/                           ← Watermark/subtitle removal
│   └── CMakeLists.txt
│
├── docs/
│   ├── REPORT_PMA.md                 ← Project management report
│   └── ARCHITECTURE.md               ← THIS FILE
│
└── .cursor/                           ← IDE config
    ├── docs/PROD_README.md
    └── rules/*.mdc
```

---

## 8. Database Schema

### 8.1 Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────────┐
│  platform_users  │       │  platform_projects    │
│──────────────────│       │──────────────────────│
│ id (PK)          │◄──┐   │ id (PK)              │
│ uuid             │   │   │ uuid                 │
│ username         │   │   │ owner_id (FK→users)  │
│ email            │   └───│ name, slug           │
│ password_hash    │       │ subscription_plan    │
│ totp_secret      │       └──────────┬───────────┘
│ totp_enabled     │                  │
│ status (IntEnum) │       ┌──────────▼───────────┐
│  0=inactive      │       │ platform_oauth_      │
│  1=admin         │       │ credentials          │
│  10=active       │       │──────────────────────│
│ last_login_at    │       │ id (PK)              │
└──────────────────┘       │ project_id (FK)      │
                           │ client_id            │
                           │ client_secret        │
                           │ redirect_uris (JSON) │
                           │ enabled              │
                           └──────────┬───────────┘
                                      │
┌─────────────────────────────────────▼───────────────────────────┐
│                      platform_channels                          │
│─────────────────────────────────────────────────────────────────│
│ id (PK)  │ uuid  │ project_id (FK)  │ console_id (FK→oauth)    │
│ created_by (FK→users)  │ name  │ platform_channel_id            │
│ access_token  │ refresh_token  │ token_expires_at               │
│ enabled  │ processing_status  │ metadata (JSON)                 │
└────────┬────────────────────────────────┬───────────────────────┘
         │                                │
         │                                │
┌────────▼──────────────────┐   ┌────────▼──────────────────────┐
│ platform_channel_login_   │   │ content_upload_queue_tasks    │
│ credentials               │   │──────────────────────────────│
│───────────────────────────│   │ id (PK)  │ uuid              │
│ channel_id (FK)           │   │ channel_id (FK)              │
│ login_email               │   │ created_by (FK→users)        │
│ login_password            │   │ status (IntEnum 0-4)         │
│ totp_secret               │   │ source_file_path             │
│ backup_codes (JSON)       │   │ title, description           │
│ proxy_host:port           │   │ scheduled_at                 │
│ proxy_username:password   │   │ completed_at                 │
│ profile_path              │   │ upload_id                    │
│ user_agent                │   │ retry_count / max_retries    │
│ last_attempt_at           │   │ error_message                │
│ last_success_at           │   └──────────────────────────────┘
│ last_error                │
│ enabled                   │
└───────────────────────────┘

┌──────────────────────┐    ┌──────────────────────┐
│ schedule_templates   │    │ channel_reauth_      │
│──────────────────────│    │ audit_logs           │
│ id (PK)  │ uuid      │    │──────────────────────│
│ project_id (FK)      │    │ channel_id (FK)      │
│ created_by (FK)      │    │ status (str)         │
│ name, timezone       │    │ trigger_reason       │
│                      │    │ error_message        │
│  ┌───────────────┐   │    │ initiated_at         │
│  │ template_slots│   │    │ completed_at         │
│  │───────────────│   │    └──────────────────────┘
│  │ day_of_week   │   │
│  │ time_utc      │   │    ┌──────────────────────┐
│  │ channel_id    │   │    │ channel_daily_       │
│  │ media_type    │   │    │ statistics           │
│  └───────────────┘   │    │──────────────────────│
└──────────────────────┘    │ channel_id (FK)      │
                            │ snapshot_date        │
                            │ subscribers, views   │
                            │ videos, likes        │
                            └──────────────────────┘
```

### 8.2 Table Statistics (Production)

```
┌──────────────────────────────────┬────────┬─────────────────────────┐
│ Table                            │ Rows   │ Purpose                 │
├──────────────────────────────────┼────────┼─────────────────────────┤
│ platform_users                   │ 10     │ User accounts           │
│ platform_channels                │ 39     │ YouTube channels        │
│ content_upload_queue_tasks       │ 5752   │ Upload tasks            │
│   └─ status=1 (completed)        │ 3513   │   ✓ Uploaded            │
│   └─ status=2 (failed)           │ 2239   │   ✗ Failed              │
│ platform_channel_login_creds     │ 36     │ RPA credentials         │
│ platform_oauth_credentials       │ 7      │ Google OAuth consoles   │
│ schedule_templates               │ 3      │ Publishing schedules    │
│ channel_reauth_audit_logs        │ 3836   │ Reauth history          │
└──────────────────────────────────┴────────┴─────────────────────────┘
```

---

## 9. Web Portal Pages

```
┌─────────────────────────────────────────────────────────────┐
│  SIDEBAR                │  MAIN CONTENT                     │
│                          │                                   │
│  ┌────────────────────┐  │                                   │
│  │ Content Fabric     │  │                                   │
│  ├────────────────────┤  │                                   │
│  │ 🏠 Dashboard       │  │  Stats cards + recent tasks       │
│  │ 📺 Channels        │  │  Channel list + token status      │
│  │ 📋 Tasks           │  │  Task list + filters + actions    │
│  │ 📅 Templates       │  │  Schedule templates + slots       │
│  │ ⚙ Settings         │  │  Profile, password, 2FA           │
│  │ 🔒 Auth            │  │  Batch OAuth reauthorization      │
│  │ 🔐 TOTP            │  │  TOTP secret management           │
│  ├────────────────────┤  │                                   │
│  │ 🔐 Admin Panel     │  │  (admin only, status==1)          │
│  │ 💚 Health          │  │  (admin only)                     │
│  ├────────────────────┤  │                                   │
│  │ User: admin        │  │                                   │
│  │ admin@cff.local    │  │                                   │
│  │ [Logout]           │  │                                   │
│  └────────────────────┘  │                                   │
└─────────────────────────────────────────────────────────────┘
```

### Portal Routes Map

```
/app/login          POST → authenticate → set cookie → /app/
/app/register       POST → create user → /app/login
/app/logout         GET  → clear cookie → /app/login
/app/               GET  → dashboard (stats, recent tasks)
│
├── /app/channels                GET  → list (ID, name, YT ID, tokens, expires)
│   ├── /app/channels/add        GET/POST → add channel form
│   ├── /app/channels/{uuid}     GET  → detail (tokens, console, credentials)
│   │   ├── /edit                GET/POST → edit channel
│   │   ├── /delete              POST → delete channel
│   │   └── /authorize           GET  → redirect to Google OAuth
│   └── /app/oauth/callback      GET  → handle Google OAuth return
│
├── /app/tasks                   GET  → list (filter by status/channel)
│   ├── /app/tasks/new           GET/POST → create task + file upload
│   └── /app/tasks/{uuid}       GET  → detail
│       ├── /cancel              POST → cancel task
│       ├── /retry               POST → retry failed task
│       └── /reschedule          POST → reschedule task
│
├── /app/templates               GET  → list templates
│   ├── /app/templates/create    GET/POST → create template
│   └── /app/templates/{uuid}   GET  → detail + slot management
│
├── /app/reauth                  GET  → batch reauth page
├── /app/totp                    GET/POST → TOTP management
└── /app/settings                GET/POST → profile, password, 2FA
```

---

## 10. Security Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                           │
│                                                                  │
│  ┌─── Layer 1: Network ─────────────────────────────────────┐   │
│  │  • Nginx: HSTS, server_tokens off                         │   │
│  │  • Rate limiting: 120 req/min global                      │   │
│  │  • Auth endpoints: 10 req/min                             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Layer 2: Authentication ──────────────────────────────┐   │
│  │                                                           │   │
│  │  API (/api/v1/*)          Portal (/app/*, /panel/*)      │   │
│  │  ┌──────────────┐        ┌──────────────────┐            │   │
│  │  │ Bearer JWT   │        │ Cookie cff_token │            │   │
│  │  │ Header:      │        │ HttpOnly         │            │   │
│  │  │ Authorization│        │ SameSite=lax     │            │   │
│  │  │              │        │ Secure=false *   │            │   │
│  │  └──────────────┘        └──────────────────┘            │   │
│  │                                                           │   │
│  │  * Secure flag controlled by HTTPS_ENABLED env var       │   │
│  │    (false on HTTP, true when HTTPS configured)           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Layer 3: Authorization ───────────────────────────────┐   │
│  │                                                           │   │
│  │  User-scoped data:                                        │   │
│  │  ┌──────────────────────────────────────────┐            │   │
│  │  │ Regular user: WHERE created_by = :uid    │            │   │
│  │  │ Admin (status=1): WHERE 1=1 (see all)    │            │   │
│  │  └──────────────────────────────────────────┘            │   │
│  │                                                           │   │
│  │  UUID in URLs (not int IDs) → prevents IDOR              │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Layer 4: Input Validation ────────────────────────────┐   │
│  │  • Pydantic v2 schemas                                    │   │
│  │  • File upload: 10GB video, 50MB thumbnail                │   │
│  │  • Path traversal: reject .. and absolute paths           │   │
│  │  • Jinja2 autoescaping (XSS prevention)                   │   │
│  │  • 2FA: TOTP + backup codes                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─── Layer 5: Production Hardening ────────────────────────┐   │
│  │  • Swagger UI disabled in prod (docs_url=None)            │   │
│  │  • Health details admin-only                              │   │
│  │  • Dependencies: pip-audit (0 vulnerabilities)            │   │
│  │  • PyJWT (not python-jose — CVE-free)                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        TECH STACK                            │
│                                                              │
│  Backend          │  Database       │  Queue                │
│  ─────────────    │  ──────────     │  ──────               │
│  Python 3.10      │  MySQL          │  Redis 7              │
│  FastAPI 0.135.1  │  InnoDB         │  rq (task queues)     │
│  Pydantic 2.11.3  │  28 tables      │  3 queues             │
│  uvicorn 0.34.2   │  SQLAlchemy     │                       │
│  Jinja2 3.1.6     │  Core (not ORM) │                       │
│                   │                 │                       │
│  Auth             │  External APIs  │  ML / Processing      │
│  ─────────────    │  ──────────     │  ──────               │
│  PyJWT            │  YouTube Data   │  RVC voice            │
│  passlib+bcrypt   │  API v3         │  Silero TTS           │
│  pyotp (2FA)      │  Google OAuth   │  C++ watermark        │
│  slowapi (limits) │  Telegram Bot   │  removal (scaffold)   │
│                   │  SMTP email     │                       │
│  Automation       │                 │  DevOps               │
│  ─────────────    │                 │  ──────               │
│  Selenium         │                 │  systemd (5 units)    │
│  undetected-      │                 │  nginx reverse proxy  │
│  chromedriver     │                 │  logrotate            │
│                   │                 │  Docker (alternative) │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Team & Responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│                         TEAM                                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Джамал (Owner)                                       │   │
│  │  → Content strategy, monetization                     │   │
│  │  → Channel management, publishing decisions           │   │
│  │  → Languages: Ukrainian / Russian                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  @mykytatishkin (Nikita) — Lead Developer             │   │
│  │  → Reauth module (Selenium), TOTP management          │   │
│  │  → OAuth flows, server administration                 │   │
│  │  → .env files, SSH access management                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Сергей — Tech Features & Testing                     │   │
│  │  → Technical features, QA                             │   │
│  │  → Language: Ukrainian only                           │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  @graf_crayt — C++ Module                             │   │
│  │  → Watermark/subtitle removal (prod/cpp/video/)       │   │
│  │  → FFmpeg integration, video processing pipeline      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  @SsmTuInvalid1 — Data Migration & SSH                │   │
│  │  → Database migrations                                │   │
│  │  → Server access management                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Анастасія — Manual Operations                        │   │
│  │  → Manual content tasks                               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 13. Deployment

### 13.1 Quick Deploy

```
┌─────────────────────────────────────────────────────────────┐
│                     DEPLOYMENT FLOW                          │
│                                                              │
│  Developer                                                   │
│      │                                                       │
│      │  git push origin main                                │
│      │                                                       │
│      ▼                                                       │
│  GitHub (mykytatishkin/content-fabric)                       │
│      │                                                       │
│      │  ssh root@46.21.250.43                               │
│      │  "cd /opt/content-fabric && git pull &&              │
│      │   systemctl restart cff-api cff-scheduler            │
│      │   cff-publishing-worker cff-notification-worker"     │
│      │                                                       │
│      ▼                                                       │
│  Server pulls latest code                                    │
│  systemd restarts all services                              │
│  New code is live                                            │
│                                                              │
│  If new dependencies:                                        │
│      source prod/venv/bin/activate                          │
│      pip install -r prod/requirements.txt                   │
│                                                              │
│  If bytecache stale:                                        │
│      find prod -name '__pycache__' -type d -exec            │
│        rm -rf {} + 2>/dev/null                              │
└─────────────────────────────────────────────────────────────┘
```

### 13.2 Environment Files

```
/opt/content-fabric/.env              ← ROOT (MySQL, Redis, JWT, Telegram, TikTok)
/opt/content-fabric/prod/.env/.env.db ← MySQL credentials
/opt/content-fabric/prod/.env/.env.api← YouTube API keys

Key variables:
  MYSQL_HOST=localhost          JWT_SECRET_KEY=<secret>
  MYSQL_PASSWORD=<secret>       TELEGRAM_BOT_TOKEN=<token>
  REDIS_URL=redis://localhost   HTTPS_ENABLED=false
```

### 13.3 Log Locations

```
┌────────────────────────────┬──────────────────────────────┐
│ Service                    │ Log File                      │
├────────────────────────────┼──────────────────────────────┤
│ API (FastAPI/uvicorn)      │ /var/log/cff-api.log          │
│ Scheduler                  │ /var/log/cff-scheduler.log    │
│ Publishing Worker          │ /var/log/cff-publishing-      │
│                            │   worker.log                  │
│ Notification Worker        │ /var/log/cff-notification-    │
│                            │   worker.log                  │
│ Voice Worker               │ /var/log/cff-voice-worker.log │
│ Nginx                      │ /var/log/nginx/access.log     │
│                            │ /var/log/nginx/error.log      │
│ Selenium screenshots       │ prod/data/logs/               │
│                            │   reauth_failures/            │
└────────────────────────────┴──────────────────────────────┘
```

---

## 14. Monitoring Commands

```bash
# All services status
systemctl status cff-api cff-scheduler cff-publishing-worker cff-notification-worker

# Health check
curl http://localhost:8000/health

# Recent errors
tail -f /var/log/cff-api.log | grep -i error

# Redis queue sizes
redis-cli llen rq:queue:publishing
redis-cli llen rq:queue:notifications

# Active processes
ps aux | grep -E 'uvicorn|scheduler|worker' | grep -v grep

# DB task stats
mysql -u content_fabric_user -p content_fabric \
  -e "SELECT status, COUNT(*) FROM content_upload_queue_tasks GROUP BY status"
```

---

## 15. Known Issues & Notes

```
┌─────────────────────────────────────────────────────────────┐
│  KNOWN ISSUES                                                │
│                                                              │
│  1. HTTPS not working — FASTPANEL intercepts :443           │
│     → Cookie Secure flag disabled via HTTPS_ENABLED=false   │
│     → When HTTPS configured: set HTTPS_ENABLED=true         │
│                                                              │
│  2. Selenium headless blocked by Google                      │
│     → "This browser or app may not be secure"               │
│     → Use SSH tunnel + manual browser instead                │
│     → Or add redirect_uri to Google Console for web OAuth   │
│                                                              │
│  3. passlib + bcrypt 4.x compatibility warning               │
│     → "trapped error reading bcrypt version"                │
│     → Functional, not breaking. Will fix with passlib update│
│                                                              │
│  4. Google OAuth SMS verification                            │
│     → New server IP triggers "suspicious activity"           │
│     → Need phone number for each Google account             │
│                                                              │
│  5. Web OAuth redirect_uri not registered                    │
│     → http://46.21.250.43/app/oauth/callback                │
│     → Must be added to each Google Cloud Console project    │
└─────────────────────────────────────────────────────────────┘
```
