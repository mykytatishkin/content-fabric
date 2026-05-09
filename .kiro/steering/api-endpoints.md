---
inclusion: fileMatch
fileMatchPattern: ['prod/app/api/**/*.py', 'prod/app/schemas/**/*.py']
---

# API Endpoint Conventions

Last updated: 2026-05-09

## Route structure

All API routes mounted under `/api/v1/` via `prod/app/api/routes.py`:

| Prefix | Module | Auth |
|--------|--------|------|
| `/api/v1/auth/` | endpoints/auth.py | public + 2FA |
| `/api/v1/channels/` | endpoints/channels.py | user (Bearer or cookie) |
| `/api/v1/tasks/` | endpoints/tasks.py | user |
| `/api/v1/templates/` | endpoints/templates.py | user |
| `/api/v1/uploads/` | endpoints/uploads.py | user |
| `/api/v1/admin/` | endpoints/admin.py | admin |
| `/api/v1/streams/` | endpoints/streams.py | **admin only** |
| `/api/v1/dle-sources/` | endpoints/dle_sources.py | **admin only** |
| `/api/v1/logs/` | endpoints/logs.py | **admin only** |

`streams`, `dle-sources`, `logs` use `Depends(get_current_admin)` because they expose host-level diagnostics (journald, DSNs, systemd units) — see `prod/app/api/endpoints/logs.py:36`, `streams.py:24`, `dle_sources.py:17`.

---

## Authentication: cookie OR Bearer

`get_current_user` in `prod/app/api/deps.py:26-57` accepts **either**:

- `Authorization: Bearer <jwt>` (machine clients, CLI, tests)
- `Cookie: cff_token=<jwt>` (browser — same cookie set by `/app/login`)

When both present, **Bearer wins** (`deps.py:31-35`). Cookie path is covered by CSRFMiddleware so cross-site POSTs are still rejected (see CSRF section below).

```python
from app.api.deps import get_current_user, get_current_admin

@router.get("/something")
async def something(user: dict = Depends(get_current_user)):
    # user has: id, email, username, status, display_name, ...
    ...

@router.post("/admin-thing")
async def admin_thing(user: dict = Depends(get_current_admin)):
    # 403 if not admin
    ...
```

Inline admin check (when you need user dict + admin gate together):
```python
from shared.db.models import UserStatus
if user["status"] != UserStatus.ADMIN.value:
    raise HTTPException(403, "Admin only")
```

---

## CSRF middleware

`CSRFMiddleware` in `prod/main.py:61-136` protects cookie-authenticated state-changing requests by checking that `Origin` (or `Referer`) matches the request's `Host`.

Skipped for:
- Safe methods (GET/HEAD/OPTIONS).
- `Authorization: Bearer ...` requests — no cookie ⇒ no CSRF surface.
- No `cff_token` cookie — anonymous POSTs (login bootstrap).

Rejects:
- Cross-origin Origin/Referer → 403 with `{"detail": "CSRF: cross-origin POST rejected"}`.
- POST without any Origin/Referer header → 403 (curl should use Bearer instead).

Practical implication: **API endpoints work transparently** for both Bearer (machine) and cookie (browser) clients. Tests that use `auth_headers` (Bearer) bypass CSRF; tests that drive the portal via cookie need correct `Origin`/`Referer` or rely on `TestClient`'s defaults.

---

## Rate limiting

```python
from app.core.config import limiter

@router.post("/create")
@limiter.limit("10/minute")
async def create(request: Request, ...):
    ...
```

Default global limit: 120/minute (see `prod/main.py:27`).

---

## Pydantic v2 schemas

Located in `prod/app/schemas/`. Use:
```python
from pydantic import BaseModel, Field, field_validator

class MySchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    model_config = {"from_attributes": True}
```

---

## User-scoped data (IDOR protection)

Non-admin users see only their own resources. Pass `created_by` to repos:

```python
tasks = task_repo.list_tasks(
    created_by=user["id"] if user["status"] != UserStatus.ADMIN.value else None
)
```

Per-resource ownership check:
```python
from shared.db.models import UserStatus

if user["status"] != UserStatus.ADMIN.value and resource.get("created_by") != user["id"]:
    raise HTTPException(status_code=404, detail="Not found")  # 404, not 403 — intentional
```

For lists:
```python
if user["status"] != UserStatus.ADMIN.value:
    items = [i for i in items if i.get("created_by") == user["id"]]
```

---

## UUID in URLs

Portal uses UUID to prevent ID enumeration. API can use both int ID and UUID. Tables with UUID: `platform_channels`, `content_upload_queue_tasks`, `schedule_templates`. Endpoints that look up by UUID still must validate ownership for non-admin users.

---

## Response format

- Single item: return Pydantic model directly
- List: return `list[Model]` (FastAPI serializes automatically)
- Errors: `raise HTTPException(status_code, detail="message")`

---

## Portal Routes

All SSR portal routes are in `prod/app/views/app_portal.py`. Cookie-based auth (`require_user(request)`), `TemplateResponse` with Jinja2, data user-scoped via `scoped_where()`. See portal-views.md for full handler list.

### User Portal (`/app/*`)

`/app/login`, `/app/register`, `/app/logout`, `/app/`, `/app/channels[…]`, `/app/tasks[…]`, `/app/templates[…]`, `/app/settings[…]`, plus new post-cutover pages: `/app/streams`, `/app/analytics`, `/app/channels/{uuid}/stats`, `/app/notifications`, `/app/voice`, `/app/reauth`. See portal-views.md for full table.

### Admin Panel (`/panel/*`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/panel/` | Admin dashboard |
| GET | `/panel/channels` | All channels |
| GET | `/panel/tasks` | All tasks |
| GET | `/panel/users` | User management |
| GET | `/panel/credentials` | OAuth credentials |
| GET | `/panel/streams` | 9 live streams (start/stop/restart) |
| GET | `/panel/dle-sources` | 7 DLE source statuses |
| GET | `/panel/stats` | Global stats (uses `channel_daily_statistics.snapshot_date`) |
| GET | `/panel/health` | Service/disk/memory/queue health |
| GET | `/panel/logs` | journalctl viewer for all `cff-*` units |
