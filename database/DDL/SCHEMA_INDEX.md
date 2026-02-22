# Content Fabric Database Schema

Database architecture for the Content Fabric SaaS platform with projects, RBAC, and multi-platform support.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       Content Fabric Database                                │
├───────────────────┬──────────────────┬──────────────┬────────────┬───────────┤
│ Identity & Access │ Channels & OAuth │ Publishing   │ Analytics  │ Streaming │
├───────────────────┼──────────────────┼──────────────┼────────────┼───────────┤
│ platform_users    │ platform_oauth_  │ content_     │ channel_   │ live_     │
│ platform_projects │  credentials     │  upload_     │  daily_    │  streaming│
│ platform_project_ │ platform_        │  queue_tasks │  statistics│  _accounts│
│  members          │  channels        │              │ channel_   │ live_     │
│                   │ platform_channel_│              │  reauth_   │  stream_  │
│                   │  tokens          │              │  audit_logs│  configu- │
│                   │ platform_channel_│              │            │  rations  │
│                   │  login_creds     │              │            │           │
└───────────────────┴──────────────────┴──────────────┴────────────┴───────────┘
```

## Table Index

### 1. Identity & Access (`auth/`)

| Table | Purpose |
|-------|---------|
| `platform_users` | User accounts, authentication |
| `platform_projects` | Workspaces grouping resources, subscription billing |
| `platform_project_members` | RBAC: user-to-project roles (owner/admin/editor/viewer) |

### 2. Channels & OAuth (`channels/`)

| Table | Purpose |
|-------|---------|
| `platform_oauth_credentials` | OAuth app creds from cloud providers (Google, Meta, TikTok) |
| `platform_channels` | Multi-platform channels (YouTube, TikTok, Instagram) |
| `platform_channel_tokens` | Token history and backup |
| `platform_channel_login_credentials` | RPA login creds for automated reauth (Playwright) |

### 3. Publishing (`publishing/`)

| Table | Purpose |
|-------|---------|
| `content_upload_queue_tasks` | Video publishing task queue with retry logic |

### 4. Analytics & Audit (`analytics/`)

| Table | Purpose |
|-------|---------|
| `channel_daily_statistics` | Daily channel stats snapshots |
| `channel_reauth_audit_logs` | OAuth reauthorization attempt audit trail |

### 5. Streaming (`streaming/`)

| Table | Purpose |
|-------|---------|
| `live_streaming_accounts` | OAuth accounts for live streaming |
| `live_stream_configurations` | RTMP/systemd stream configurations |

### 6. System

| Table | Purpose |
|-------|---------|
| `platform_schema_migrations` | Migration version tracking |

## Entity Relationships

```
platform_users (1)
  │
  ├──< platform_projects (*) [owner_id]
  │       │
  │       ├──< platform_project_members (*) [project_id]
  │       │       └──> platform_users [user_id]
  │       │
  │       ├──< platform_oauth_credentials (*)
  │       │       │
  │       │       └──< platform_channels (*) [console_id, SET NULL]
  │       │               │
  │       │               ├──< platform_channel_tokens (*)
  │       │               ├──< platform_channel_login_credentials (1)
  │       │               ├──< channel_daily_statistics (*)
  │       │               ├──< channel_reauth_audit_logs (*)
  │       │               └──< content_upload_queue_tasks (*)
  │       │
  │       ├──< live_streaming_accounts (*)
  │       │       │
  │       │       └──< live_stream_configurations (*) [SET NULL]
  │       │
  │       └──< live_stream_configurations (*) [project_id]
  │
  └──< content_upload_queue_tasks (*) [created_by, SET NULL]
```

## Key Design Decisions

### 1. Project-Based Ownership (not user-based)
All resources belong to a **project**, not directly to a user:
- 1 user can have multiple projects
- 1 project can have multiple users with different roles
- Subscription/billing is per-project

### 2. RBAC Roles
Enforced in application layer via `platform_project_members.role`:

| Role | Channels | Tasks | Settings | Members | Billing |
|------|----------|-------|----------|---------|---------|
| owner | CRUD | CRUD | CRUD | CRUD | CRUD |
| admin | CRUD | CRUD | CRUD | CRU | Read |
| editor | Read | CRUD | Read | Read | - |
| viewer | Read | Read | Read | Read | - |

### 3. Descriptive Table Naming
Tables use descriptive names grouped by domain prefix:
- `platform_*` — identity, access, core infrastructure
- `content_*` — content publishing
- `channel_*` — channel analytics and audit
- `live_*` — live streaming

### 4. Platform Agnostic
Multi-platform support via `platform` column:
- youtube, tiktok, instagram, twitch, meta, kick

### 5. FK Strategy
- Integer FKs everywhere (no string-based FKs)
- CASCADE DELETE for project-owned resources
- SET NULL for optional references (console, streaming_account)

## Legacy Table Mapping

| Legacy Table | New Table |
|---|---|
| `user` | `platform_users` |
| `google_consoles` | `platform_oauth_credentials` |
| `youtube_channels` | `platform_channels` |
| `youtube_tokens` | `platform_channel_tokens` |
| `youtube_account_credentials` | `platform_channel_login_credentials` |
| `tasks` | `content_upload_queue_tasks` |
| `youtube_channel_daily` | `channel_daily_statistics` |
| `youtube_reauth_audit` | `channel_reauth_audit_logs` |
| `youtube_account` | `live_streaming_accounts` |
| `stream` | `live_stream_configurations` |
| `migration` | `platform_schema_migrations` |

## Migrations

All migration scripts are in `database/migrations/`:

```bash
# 1. Backup
mysqldump -u root -p content_factory > backup_$(date +%Y%m%d).sql

# 2. Run migrations sequentially
mysql -u root -p content_factory < database/migrations/001_create_new_schema.sql
mysql -u root -p content_factory < database/migrations/002_migrate_identity.sql
mysql -u root -p content_factory < database/migrations/003_migrate_channels.sql
mysql -u root -p content_factory < database/migrations/004_migrate_publishing.sql
mysql -u root -p content_factory < database/migrations/005_migrate_analytics.sql
mysql -u root -p content_factory < database/migrations/006_migrate_streaming.sql
mysql -u root -p content_factory < database/migrations/007_verify_migration.sql

# 3. Cleanup (ONLY after all code updated and verified)
# mysql -u root -p content_factory < database/migrations/008_cleanup_legacy.sql
```

## Directory Structure

```
database/
├── DDL/
│   ├── SCHEMA_INDEX.md              # This file
│   ├── auth/
│   │   ├── platform_users.sql
│   │   ├── platform_projects.sql
│   │   └── platform_project_members.sql
│   ├── channels/
│   │   ├── platform_oauth_credentials.sql
│   │   ├── platform_channels.sql
│   │   ├── platform_channel_tokens.sql
│   │   └── platform_channel_login_credentials.sql
│   ├── publishing/
│   │   └── content_upload_queue_tasks.sql
│   ├── analytics/
│   │   ├── channel_daily_statistics.sql
│   │   └── channel_reauth_audit_logs.sql
│   └── streaming/
│       ├── live_streaming_accounts.sql
│       └── live_stream_configurations.sql
└── migrations/
    ├── 001_create_new_schema.sql
    ├── 002_migrate_identity.sql
    ├── 003_migrate_channels.sql
    ├── 004_migrate_publishing.sql
    ├── 005_migrate_analytics.sql
    ├── 006_migrate_streaming.sql
    ├── 007_verify_migration.sql
    ├── 008_cleanup_legacy.sql
    └── rollback_001..006.sql
```
