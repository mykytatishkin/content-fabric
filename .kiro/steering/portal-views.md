---
inclusion: fileMatch
fileMatchPattern: ['prod/app/views/**/*.py', 'prod/app/templates/**/*.html']
---

# Portal (SSR Views) Conventions

Last updated: 2026-05-09

## Two portals
- **User Portal** (`/app/*`) — `prod/app/views/app_portal.py` (1000+ lines)
- **Admin Panel** (`/panel/*`) — `prod/app/views/panel.py`

## Cookie-based auth (NOT Bearer JWT)
Views use cookies, NOT `Depends(get_current_user)`.

**Production runs HTTPS** (`aiyoutube.pbnbots.com` via nginx). Cookie `Secure` flag is driven by env var `HTTPS_ENABLED` — `True` in prod. `_set_token_cookie()` uses this; if you flip prod back to plain HTTP for any reason, also unset `HTTPS_ENABLED` or browsers won't send the cookie and users get infinite redirect loops.

CSRF is enforced by `CSRFMiddleware` (`prod/main.py:61-136`) — see api-endpoints.md.

```python
from app.core.auth import require_user, require_admin, is_admin

@router.get("/something", response_class=HTMLResponse)
async def something_page(request: Request):
    user, redirect = require_user(request)
    if redirect:
        return redirect
    # user is a dict: {id, email, username, status, ...}
    ...
```

Admin-only pages:
```python
@router.get("/admin-page", response_class=HTMLResponse)
async def admin_page(request: Request):
    user, redirect = require_admin(request)
    if redirect:
        return redirect
```

## Inline repo imports
Views import repos inside functions (lazy):
```python
async def channel_detail(request: Request, channel_uuid: str):
    user, redirect = require_user(request)
    if redirect:
        return redirect
    from shared.db.repositories import channel_repo, credential_repo
    channel = channel_repo.get_channel_by_uuid(channel_uuid)
    ...
```

## Template rendering
```python
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory="app/templates")

return templates.TemplateResponse("app_channels.html", {
    "request": request,
    "user": user,
    "active": "channels",  # for sidebar highlight
    "channels": channels,
    "error": None,
})
```

## Ownership checks
```python
# Returns 404 to non-owners (not 403!) — intentional IDOR protection
if not channel or (not is_admin(user) and channel.get("created_by") != user["id"]):
    return RedirectResponse("/app/channels", status_code=302)
```

## JSON islands in Jinja templates (XSS-safe)

When embedding server-side data into a `<script>` block for client-side JS, use the `|tojson` filter — it produces RFC-8259-valid JSON AND escapes `</script>`/HTML-significant chars:

```jinja
<script id="streams-data" type="application/json">{{ streams | tojson }}</script>
<script>
  const streams = JSON.parse(document.getElementById("streams-data").textContent);
</script>
```

Used in: `app_streams.html`, `app_channel_stats.html`, `app_analytics.html`, `app_channels.html`, `app_task_detail.html`. Patched in commit `87d6a1c` (fix: Stored XSS via Jinja tojson).

**Never** do `const x = {{ obj }};` directly — that is a Stored XSS sink.

## Template files

```
# Base / auth
app_base.html              — base layout for user portal (sidebar, nav)
app_login.html             — login form
app_register.html          — registration form
app_totp.html              — 2FA verification

# Dashboard
app_dashboard.html         — user dashboard

# Channels
app_channels.html          — channel list
app_channel_add.html       — add channel form
app_channel_detail.html    — channel detail
app_channel_edit.html      — edit channel
app_channel_stats.html     — per-channel stats (uses |tojson)
app_reauth.html            — Playwright reauth status

# Tasks
app_tasks.html
app_task_new.html
app_task_detail.html       — uses |tojson

# Templates (schedule)
app_templates.html
app_template_new.html
app_template_detail.html

# Settings
app_settings.html          — profile, password, 2FA

# Post-cutover (Yii migration)
app_streams.html           — 9 live streams (uses |tojson)
app_streams_create.html
app_dle_sources.html       — 7 DLE sources status
app_stats_overview.html    — global stats overview
app_analytics.html         — analytics dashboard (uses |tojson)
app_notifications.html
app_voice.html             — voice change UI

# Admin panel
base.html                  — admin panel base layout
dashboard.html
channels.html / tasks.html / users.html / credentials.html
health.html / logs.html
broadcast.html             — broadcast notification form
payment.html

# Errors
404.html
```
