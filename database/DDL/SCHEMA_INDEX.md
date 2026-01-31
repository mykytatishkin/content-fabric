# Content Factory Database Schema

This document describes the microservices database architecture for the Content Factory SaaS platform.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Content Factory Database                         │
├──────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│ Auth Service │ Channel Svc  │ Publishing   │ Analytics    │ Streaming   │
│              │              │ Service      │ Service      │ Service     │
├──────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ users        │ oauth_consoles│ publish_tasks│ channel_     │ streaming_  │
│              │ channels     │              │ daily_stats  │ accounts    │
│              │ channel_     │              │ reauth_audit │ streams     │
│              │ tokens       │              │              │             │
│              │ channel_     │              │              │             │
│              │ credentials  │              │              │             │
└──────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
```

## Microservice Groupings

### 1. Auth Service (`auth/`)
User authentication and authorization.

| Table | Purpose |
|-------|---------|
| `users` | User accounts, subscriptions, authentication |

### 2. Channel Service (`channels/`)
Multi-platform channel management (YouTube, TikTok, Instagram).

| Table | Purpose |
|-------|---------|
| `oauth_consoles` | OAuth credentials from cloud platforms |
| `channels` | Connected social media channels |
| `channel_tokens` | Token history and backups |
| `channel_credentials` | Login credentials for automated reauth |

### 3. Publishing Service (`publishing/`)
Video publishing and scheduling.

| Table | Purpose |
|-------|---------|
| `publish_tasks` | Scheduled and executed publishing tasks |

### 4. Analytics Service (`analytics/`)
Statistics, reporting, and audit logs.

| Table | Purpose |
|-------|---------|
| `channel_daily_stats` | Daily channel statistics snapshots |
| `reauth_audit` | Reauthorization attempt logs |

### 5. Streaming Service (`streaming/`)
Live streaming management.

| Table | Purpose |
|-------|---------|
| `streaming_accounts` | OAuth accounts for live streaming |
| `streams` | Live stream configurations |

## Entity Relationships

```
users (1)
  │
  ├──< oauth_consoles (*)
  │       │
  │       └──< channels (*) ──< channel_tokens (*)
  │               │
  │               ├──< channel_credentials (1)
  │               ├──< channel_daily_stats (*)
  │               ├──< reauth_audit (*)
  │               └──< publish_tasks (*)
  │
  ├──< streaming_accounts (*)
  │       │
  │       └──< streams (*)
  │
  └──< streams (*) [direct ownership]
```

## Key Design Decisions

### 1. User Ownership
All entities are owned by users via `user_id` foreign key:
- Enables multi-tenancy
- Supports subscription-based access control
- Allows per-user quotas and limits

### 2. Platform Agnostic
Tables are designed to support multiple platforms:
- `channels.platform` = 'youtube' | 'tiktok' | 'instagram'
- `streaming_accounts.platform` = 'youtube' | 'twitch'
- Metadata stored as JSON for platform-specific fields

### 3. Naming Conventions
- Removed `youtube_` prefix from table names
- Renamed `channel_id` to `platform_channel_id` (for platform's ID)
- Our internal `channel_id` now refers to `channels.id`

### 4. Foreign Key Strategy
- Changed from `channel_name` FKs to `channel_id` (more efficient)
- CASCADE DELETE for user-owned data
- SET NULL for optional relationships

## Directory Structure

```
database/DDL/
├── SCHEMA_INDEX.md          # This file
├── auth/
│   └── users.sql
├── channels/
│   ├── oauth_consoles.sql
│   ├── channels.sql
│   ├── channel_tokens.sql
│   └── channel_credentials.sql
├── publishing/
│   └── publish_tasks.sql
├── analytics/
│   ├── channel_daily_stats.sql
│   └── reauth_audit.sql
├── streaming/
│   ├── streaming_accounts.sql
│   └── streams.sql
└── migrations/
    ├── README.md
    ├── 001_create_schema.sql
    ├── 002_migrate_data.sql
    ├── 003_cleanup_legacy.sql
    ├── rollback_001.sql
    └── rollback_002.sql
```

## Legacy Table Mapping

| Legacy Table | New Table | Service |
|-------------|-----------|---------|
| `user` | `users` | Auth |
| `google_consoles` | `oauth_consoles` | Channel |
| `youtube_channels` | `channels` | Channel |
| `youtube_tokens` | `channel_tokens` | Channel |
| `youtube_account_credentials` | `channel_credentials` | Channel |
| `tasks` | `publish_tasks` | Publishing |
| `youtube_channel_daily` | `channel_daily_stats` | Analytics |
| `youtube_reauth_audit` | `reauth_audit` | Analytics |
| `youtube_account` | `streaming_accounts` | Streaming |
| `stream` | `streams` | Streaming |

## Migration

See `migrations/README.md` for detailed migration instructions.

Quick start:
```bash
# 1. Backup database
mysqldump -u root -p content_factory > backup.sql

# 2. Run migrations
mysql -u root -p content_factory < migrations/001_create_schema.sql
mysql -u root -p content_factory < migrations/002_migrate_data.sql

# 3. Verify and cleanup (optional)
mysql -u root -p content_factory < migrations/003_cleanup_legacy.sql
```
