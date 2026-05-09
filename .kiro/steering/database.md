---
inclusion: fileMatch
fileMatchPattern: ['prod/shared/db/**/*.py', 'prod/app/repositories/**/*.py']
---

# Database Conventions

Last updated: 2026-05-09

## SQLAlchemy Core (NOT ORM)

We use SQLAlchemy Core with raw `Table` definitions, NOT the ORM. No `Session`, no `Base.metadata`, no mapped classes.

### Connection pattern
```python
from shared.db.connection import get_connection

with get_connection() as conn:
    result = conn.execute(stmt)
    # auto-commits on exit
```

### IntEnum CRITICAL BUG
MySQL does NOT auto-convert Python IntEnum to int. ALWAYS use `.value`:
```python
# WRONG:
.where(t.c.status == TaskStatus.PENDING)
# CORRECT:
.where(t.c.status == TaskStatus.PENDING.value)
```

### Enums (prod/shared/db/models.py)

```python
class TaskStatus(IntEnum):
    PENDING = 0
    COMPLETED = 1
    FAILED = 2
    PROCESSING = 3
    CANCELLED = 4

class UserStatus(IntEnum):
    INACTIVE = 0
    ADMIN = 1
    ACTIVE = 10
```

`UserStatus` non-contiguous: `0/1/10`, NOT `0/1/2`. Bare integer literals in SQL must use exactly these values.

### Repository pattern
Each repo file has:
1. Module-level imports of table + get_connection
2. Functions that build `select()`/`insert()`/`text()` statements
3. Manual `_row_to_dict()` for positional row tuple mapping
4. Returns `dict | None` for single, `list[dict]` for multiple

### JSON columns
```python
from shared.db.utils import serialize_json, deserialize_json

# Writing:
stmt = insert(table).values(metadata=serialize_json(my_dict))

# Reading in _row_to_dict:
"metadata": deserialize_json(row[N])
```

### The metadata_ column
JSON columns named `metadata` use:
```python
Column("metadata_", JSON, key="metadata")  # historical
# or
Column("metadata", JSON, key="meta")       # newer Yii-migrated tables
```
This avoids conflict with SQLAlchemy's `MetaData`. In raw `text()` SQL use the actual column name (`metadata_` or `metadata`) — check the table definition in `models.py`.

### Dynamic UPDATE helper
```python
from shared.db.utils import build_update
sql, params = build_update("platform_channels", {"name": "new"}, where="id = :id", id=5)
conn.execute(text(sql), params)
```

### Duplicate key detection
```python
from shared.db.utils import is_duplicate_key_error
try:
    conn.execute(insert_stmt)
except Exception as e:
    if is_duplicate_key_error(e):
        return None
    raise
```

---

## Tables Reference

All tables defined in `prod/shared/db/models.py`.

### Identity & Access
| Table | Key columns | Notes |
|-------|------------|-------|
| `platform_users` | id, uuid, email, password_hash, status(IntEnum), totp_* | UserStatus: 0=INACTIVE, 1=ADMIN, 10=ACTIVE |
| `platform_projects` | id, uuid, owner_id, slug, subscription_plan | Multi-tenant root |
| `platform_project_members` | project_id, user_id, role | Membership/RBAC |

### Channels & OAuth
| Table | Key columns | Notes |
|-------|------------|-------|
| `platform_channels` | id, uuid, console_id, project_id, access_token, refresh_token, created_by | `created_by` for user-scoped filtering. JSON col `metadata` keyed as `meta` |
| `platform_oauth_credentials` | id, project_id, client_id, client_secret | OAuth consoles |
| `platform_channel_tokens` | channel_id, token_type, token_value, expires_at | Token history |
| `platform_channel_login_credentials` | channel_id, login_email, login_password, totp_secret, proxy_*, profile_path, user_agent, last_attempt_at, last_success_at, last_error, enabled | RPA credentials for Playwright reauth |
| `channel_reauth_audit_logs` | channel_id, status, trigger_reason, error_message | Audit trail |

### Publishing
| Table | Key columns | Notes |
|-------|------------|-------|
| `content_upload_queue_tasks` | id, uuid, channel_id, status(TINYINT 0-4), scheduled_at, created_by | Replaces Yii `tasks`. JSON `metadata` keyed as `meta` |

### Schedule
| Table | Key columns | Notes |
|-------|------------|-------|
| `schedule_templates` | id, uuid, project_id, created_by | `created_by` for user scoping |
| `schedule_template_slots` | template_id, day_of_week, time_utc, channel_id, media_type | |

### Analytics
| Table | Key columns | Notes |
|-------|------------|-------|
| `channel_daily_statistics` | channel_id, platform_channel_id, **snapshot_date**, subscribers, views, videos, likes, comments | Replaces Yii `youtube_channel_daily`. NB: column is `snapshot_date` (used by `/panel/stats`), not `recorded_at` |

### Streaming (Yii migration)
| Table | Key columns | Notes |
|-------|------------|-------|
| `live_streaming_accounts` | project_id, client_id, client_secret, access_token, refresh_token | OAuth for streaming |
| `live_stream_configurations` | project_id, channel_id, name, **service_name**, workdir, rtmp_host, rtmp_base, stream_key, duration_sec, platform_broadcast_id, platform_stream_id | Replaces Yii `stream`. `service_name` is the systemd unit name (`stream-knigaza30sekund`, etc.) |

### Notifications
| Table | Key columns | Notes |
|-------|------------|-------|
| `notifications` | user_id, type, title, message, is_read | type ∈ {info, error, task, broadcast} |

### System
| Table | Notes |
|-------|-------|
| `platform_schema_migrations` | version, checksum, applied_at — flyway-style ledger |

---

## Portal-displayed credential columns

The channel detail page (`/app/channels/{uuid}`) uses `credential_repo.get_credentials(channel_id)` to display the full record. Columns from `platform_channel_login_credentials` shown on the portal:

- `login_email` — login email for the Google account
- `totp_secret` — shown as has/doesn't have, never as the actual secret
- `proxy_host`, `proxy_port`, `proxy_username`, `proxy_password`
- `backup_codes`
- `profile_path` — Playwright profile dir
- `user_agent`
- `last_attempt_at`, `last_success_at`, `last_error`
- `enabled`
