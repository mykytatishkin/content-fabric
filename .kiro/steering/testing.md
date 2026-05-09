---
inclusion: fileMatch
fileMatchPattern: ['prod/tests/**/*.py']
---

# Testing Conventions

Last updated: 2026-05-09

## Setup
- pytest with `pythonpath = .` (imports from prod root)
- `conftest.py` sets env vars BEFORE imports (JWT_SECRET_KEY, MySQL test DB, etc.)
- Heavy deps mocked at module level: `rq`, `googleapiclient`, `google.oauth2`

## Fixtures (conftest.py)

```python
TEST_USER = {
    "id": 1, "email": "test@cff.local", "username": "testuser",
    "status": 10, "display_name": "Test", "password_hash": "hashed",
    "totp_enabled": 0, "totp_secret": None, "totp_backup_codes": None,
}

ADMIN_USER = {**TEST_USER, "id": 99, "email": "admin@cff.local", "status": 1}
```

- `app_client` — FastAPI TestClient with mocked DB connections
- `auth_headers` — `{"Authorization": "Bearer <valid_jwt>"}`
- `admin_headers` — `{"Authorization": "Bearer <admin_jwt>"}`

Bearer-auth tests **bypass CSRF middleware** (see `prod/main.py:85-86`) — no extra header juggling needed.

## CRITICAL: Patch at IMPORT SITE

When mocking, patch where the function is IMPORTED, not where it's defined:

```python
# WRONG — patches the definition, but endpoint already imported it:
@patch("shared.db.repositories.channel_repo.get_channel_by_id")

# CORRECT — patches at the import site:
@patch("app.api.endpoints.channels.get_channel_by_id")
```

## Repo test pattern

Use `_patch_repo()` context manager to patch `get_connection`:

```python
CONSOLE_MOD = "shared.db.repositories.console_repo"

@contextmanager
def _patch_repo(module_path: str, conn):
    @contextmanager
    def _fake():
        yield conn
    with patch(f"{module_path}.get_connection", _fake):
        yield
```

Mock data tuples must match the column order in the repo's `select()` / `_row_to_dict()`. When a repo's column list changes, regenerate the mock tuple — see commit `9fcacbc` for an example fix.

## Portal tests — admin gate

`test_web_ui.py` and friends drive the cookie-based portal via `TestClient`. To exercise admin-only pages without a real session, **patch `require_admin` at the view-module import site**:

```python
@patch("app.views.panel.require_admin")
def test_panel_streams(mock_admin, app_client):
    mock_admin.return_value = (ADMIN_USER, None)  # (user, redirect)
    resp = app_client.get("/panel/streams")
    assert resp.status_code == 200
```

Same shape for `require_user` on `/app/*` pages.

## Running tests

```bash
cd prod && python -m pytest tests/ -v --tb=short
```

**221 tests, all should pass.** No real DB needed (everything mocked).

## Coverage gaps (TODO — please add tests when touching these)

- **CSRF middleware** (`prod/main.py:61-136`) — no integration test exercises the cross-origin reject path.
- **JWT decode/encode** (`prod/app/core/security.py`) — covered indirectly via auth flow, but no targeted unit test for expiry, algorithm tampering, missing claims.
- **`slug_to_host`** (`prod/shared/ingestion/dle/pipeline.py`) — silently fixed in commit `e1dcde1`; no regression test yet. Easy unit test, just add slug→host mappings.

If you touch any of these files, add a test in the same PR.
