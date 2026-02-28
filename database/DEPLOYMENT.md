# Database Schema Refactoring — Deployment Guide

## Overview

This document describes how to deploy the new database schema locally and on production.

The refactoring includes:
- 13 new tables with consistent naming conventions
- Projects/workspaces with RBAC (owner/admin/editor/viewer)
- Numbered migration scripts (001-008) with rollbacks
- All production data preserved

---

## Pull Requests (merge order)

| # | PR | Branch | What |
|---|---|---|---|
| 1 | [#69](https://github.com/mykytatishkin/content-fabric/pull/69) | `feature/db-refactoring` | Migration scripts 001-008, rollbacks, DDL |
| 2 | [#70](https://github.com/mykytatishkin/content-fabric/pull/70) | `feature/update-prod-schema` | Prod API code (FastAPI repositories/schemas) |
| 3 | [#71](https://github.com/mykytatishkin/content-fabric/pull/71) | `feature/update-legacy-schema` | Legacy Python code (50+ SQL queries, dataclasses) |
| 4 | [#72](https://github.com/mykytatishkin/content-fabric/pull/72) | `feature/local-dev-compatible` | Docker local dev auto-setup |

**PRs #70 and #71 are based on #69** — merge #69 first.

---

## Local Setup (Docker)

### Prerequisites
- Docker Desktop installed and running
- Git access to the repository

### Step 1: Start local environment

```bash
git checkout feature/local-dev-compatible
cd docker
docker-compose up -d
```

This starts:
- **MySQL 8.0** on port `3306` (user: `dev_user`, pass: `dev_pass`, db: `content_fabric`)
- **phpMyAdmin** on port `8080` (http://localhost:8080)

Docker auto-runs init scripts in order:
1. `docker/init/01-legacy-schema.sql` — creates legacy tables with test data
2. `docker/init/02-new-schema-migration.sql` — runs all migrations 001-007

After startup you'll have **24 tables**: 11 legacy + 13 new.

### Step 2: Verify locally

Open phpMyAdmin (http://localhost:8080) and run:

```sql
-- Check all 13 new tables exist
SELECT TABLE_NAME, TABLE_ROWS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'content_fabric'
AND TABLE_NAME LIKE 'platform_%'
   OR TABLE_NAME LIKE 'content_%'
   OR TABLE_NAME LIKE 'channel_%'
   OR TABLE_NAME LIKE 'live_%'
ORDER BY TABLE_NAME;
```

Expected: 13 tables with data migrated from legacy.

### Step 3: Test migrations manually (optional)

To test step-by-step instead of auto-setup:

```bash
# Start with only legacy schema
docker-compose down -v
# Remove 02-new-schema-migration.sql temporarily
mv docker/init/02-new-schema-migration.sql /tmp/
docker-compose up -d

# Wait for MySQL to be healthy, then run migrations one by one
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/001_create_new_schema.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/002_migrate_identity.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/003_migrate_channels.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/004_migrate_publishing.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/005_migrate_analytics.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/006_migrate_streaming.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/007_verify_migration.sql

# Restore auto-setup
mv /tmp/02-new-schema-migration.sql docker/init/
```

### Step 4: Test rollback (optional)

```bash
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/rollback_006.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/rollback_005.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/rollback_004.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/rollback_003.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/rollback_002.sql
docker exec -i dev-test-env-mysql mysql -u dev_user -pdev_pass content_fabric < ../database/migrations/rollback_001.sql
```

Legacy tables remain intact after rollback.

---

## Production Deployment

### Prerequisites
- SSH access to production server
- MySQL root or admin access on production
- **Production database backup taken BEFORE starting**

### Step 1: Take a backup

```bash
# SSH into prod server
ssh $PROD_SSH_USER@$PROD_SSH_HOST

# Full backup
mysqldump -u root -p content_fabric > /backups/content_fabric_pre_migration_$(date +%Y%m%d_%H%M%S).sql
```

### Step 2: Run migrations 001-006 (data migration)

```bash
# On prod server, from the repo directory:
mysql -u root -p content_fabric < database/migrations/001_create_new_schema.sql
mysql -u root -p content_fabric < database/migrations/002_migrate_identity.sql
mysql -u root -p content_fabric < database/migrations/003_migrate_channels.sql
mysql -u root -p content_fabric < database/migrations/004_migrate_publishing.sql
mysql -u root -p content_fabric < database/migrations/005_migrate_analytics.sql
mysql -u root -p content_fabric < database/migrations/006_migrate_streaming.sql
```

All migrations are **idempotent** — safe to re-run if something fails.

### Step 3: Verify migration (007)

```bash
mysql -u root -p content_fabric < database/migrations/007_verify_migration.sql
```

**Check that ALL rows show `OK` status:**

```
+-------------------+--------------+-----------+--------+
| check_name        | legacy_count | new_count | status |
+-------------------+--------------+-----------+--------+
| users             |            1 |         1 | OK     |
| oauth_consoles    |           11 |        11 | OK     |
| channels          |           34 |        34 | OK     |
| channel_tokens    |           34 |        34 | OK     |
| login_credentials |           34 |        34 | OK     |
| tasks             |         5079 |      5078 | OK     |
| daily_stats       |         2050 |      2050 | OK     |
| reauth_audit      |         3550 |      3550 | OK     |
| streaming_accounts|            X |         X | OK     |
| stream_configs    |            X |         X | OK     |
+-------------------+--------------+-----------+--------+
```

The 1 missing task is an orphan record (references non-existent channel) — this is expected.

**FK integrity checks should all show `0`:**

```
+------------------------------+-------+
| check_name                   | count |
+------------------------------+-------+
| channels_invalid_console     |     0 |
| tasks_invalid_channel        |     0 |
| credentials_invalid_channel  |     0 |
+------------------------------+-------+
```

### Step 4: Deploy application code

After migration is verified:
1. Deploy prod code changes (PR #70)
2. Deploy legacy code changes (PR #71)
3. Restart application services

### Step 5: Monitor

- Watch application logs for any SQL errors
- Verify task processing works (new tasks get created in `content_upload_queue_tasks`)
- Verify reauth service works
- Check daily report generates correctly

### Step 6: Cleanup legacy tables (008)

**ONLY after everything works for at least a few days:**

```bash
mysql -u root -p content_fabric < database/migrations/008_cleanup_legacy.sql
```

This script is **commented out by default**. To actually drop legacy tables:

1. Open `008_cleanup_legacy.sql`
2. Uncomment the `DROP TABLE` block (lines 36-54)
3. Run the script

**This is IRREVERSIBLE.** Make sure:
- [ ] 007 verification shows all OK
- [ ] Application code (PRs #70, #71) is deployed and working
- [ ] No errors in logs for 48+ hours
- [ ] Fresh backup taken before running 008

Legacy tables that will be dropped:
```
youtube_tokens, youtube_account_credentials, youtube_reauth_audit,
youtube_channel_daily, tasks, youtube_channels, google_consoles,
stream, youtube_account, user, migration
```

---

## Rollback Plan

If something goes wrong after migration:

### Before code deployment (migrations only)
Run rollback scripts in reverse order:
```bash
mysql -u root -p content_fabric < database/migrations/rollback_006.sql
mysql -u root -p content_fabric < database/migrations/rollback_005.sql
mysql -u root -p content_fabric < database/migrations/rollback_004.sql
mysql -u root -p content_fabric < database/migrations/rollback_003.sql
mysql -u root -p content_fabric < database/migrations/rollback_002.sql
mysql -u root -p content_fabric < database/migrations/rollback_001.sql
```
Legacy tables remain untouched — old code continues working.

### After code deployment
Revert application code to previous version, then run rollback scripts above.

### After 008 cleanup
Restore from backup. This is why backup is mandatory before starting.

---

## Table Mapping Reference

| New Table | Old Table | Records (approx) |
|---|---|---|
| `platform_users` | `user` | 1 |
| `platform_projects` | *(new)* | 1 |
| `platform_project_members` | *(new)* | 1 |
| `platform_oauth_credentials` | `google_consoles` | 11 |
| `platform_channels` | `youtube_channels` | 34 |
| `platform_channel_tokens` | `youtube_tokens` | 34 |
| `platform_channel_login_credentials` | `youtube_account_credentials` | 34 |
| `content_upload_queue_tasks` | `tasks` | ~5078 |
| `channel_daily_statistics` | `youtube_channel_daily` | ~2050 |
| `channel_reauth_audit_logs` | `youtube_reauth_audit` | ~3550 |
| `live_streaming_accounts` | `youtube_account` | varies |
| `live_stream_configurations` | `stream` | varies |
| `platform_schema_migrations` | `migration` | auto |

---

## UUID Migration (applied 28.02.2026)

After the main schema migration, an additional migration was applied to add UUID columns for IDOR protection in the web portal:

```sql
-- Step 1: Add nullable uuid columns
ALTER TABLE platform_channels ADD COLUMN uuid VARCHAR(36) NULL AFTER id;
ALTER TABLE content_upload_queue_tasks ADD COLUMN uuid VARCHAR(36) NULL AFTER id;
ALTER TABLE schedule_templates ADD COLUMN uuid VARCHAR(36) NULL AFTER id;

-- Step 2: Backfill existing rows with MySQL's UUID() function
UPDATE platform_channels SET uuid = UUID() WHERE uuid IS NULL;
UPDATE content_upload_queue_tasks SET uuid = UUID() WHERE uuid IS NULL;
UPDATE schedule_templates SET uuid = UUID() WHERE uuid IS NULL;

-- Step 3: Make NOT NULL and add UNIQUE index
ALTER TABLE platform_channels MODIFY uuid VARCHAR(36) NOT NULL, ADD UNIQUE INDEX idx_channels_uuid (uuid);
ALTER TABLE content_upload_queue_tasks MODIFY uuid VARCHAR(36) NOT NULL, ADD UNIQUE INDEX idx_tasks_uuid (uuid);
ALTER TABLE schedule_templates MODIFY uuid VARCHAR(36) NOT NULL, ADD UNIQUE INDEX idx_templates_uuid (uuid);
```

**Verification:**
```sql
-- All counts should match (0 nulls, 0 duplicates, 0 bad format)
SELECT COUNT(*) - COUNT(uuid) AS missing FROM platform_channels;
SELECT COUNT(*) - COUNT(DISTINCT uuid) AS dupes FROM platform_channels;
SELECT COUNT(*) FROM platform_channels WHERE LENGTH(uuid) != 36;
-- Repeat for content_upload_queue_tasks and schedule_templates
```

**Purpose:** Portal URLs now use `/app/channels/{uuid}` instead of `/app/channels/{int_id}` to prevent sequential ID enumeration (IDOR attacks). Internal DB operations still use integer `id` columns for FK joins.

---

## Production Testing Checklist

- [ ] Backup taken before migration
- [ ] Migrations 001-006 applied without errors
- [ ] 007 verification — all rows show OK
- [ ] FK integrity — all checks show 0
- [ ] Application code deployed (PRs #70, #71)
- [ ] Task processing works on new tables
- [ ] Reauth service works
- [ ] Daily report generates correctly
- [ ] Channel management works in admin panel
- [ ] No SQL errors in application logs for 48h
- [ ] 008 cleanup executed (after verification period)
