# Database Migration Guide

This guide explains how to migrate from the legacy monolith schema to the new microservices architecture.

## Migration Overview

| Migration | Description | Reversible |
|-----------|-------------|------------|
| 001_create_schema.sql | Creates new table structure | Yes (rollback_001.sql) |
| 002_migrate_data.sql | Migrates data from legacy tables | Yes (rollback_002.sql) |
| 003_cleanup_legacy.sql | Removes old tables (optional) | No |

## Before You Start

1. **Backup your database**:
   ```bash
   mysqldump -u root -p your_database > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Test in staging first**: Run migrations on a copy of production data

3. **Review the schema changes**: See table mappings below

## Table Mapping

### Auth Service
| Old Table | New Table | Changes |
|-----------|-----------|---------|
| `user` | `users` | Added: uuid, subscription_plan, timezone |

### Channel Service
| Old Table | New Table | Changes |
|-----------|-----------|---------|
| `google_consoles` | `oauth_consoles` | Added: user_id, platform |
| `youtube_channels` | `channels` | Added: user_id, platform; Renamed: channel_id → platform_channel_id |
| `youtube_tokens` | `channel_tokens` | Changed: FK by channel_id instead of name |
| `youtube_account_credentials` | `channel_credentials` | Changed: FK by channel_id instead of name |

### Publishing Service
| Old Table | New Table | Changes |
|-----------|-----------|---------|
| `tasks` | `publish_tasks` | Added: user_id, platform, retry tracking; Renamed fields |

### Analytics Service
| Old Table | New Table | Changes |
|-----------|-----------|---------|
| `youtube_channel_daily` | `channel_daily_stats` | Added: likes, comments, metadata |
| `youtube_reauth_audit` | `reauth_audit` | Changed: FK by channel_id, added trigger_reason |

### Streaming Service
| Old Table | New Table | Changes |
|-----------|-----------|---------|
| `youtube_account` | `streaming_accounts` | Added: user_id, platform, enabled |
| `stream` | `streams` | Added: user_id; Renamed: youtube_* → platform_* |

## Running the Migrations

### Step 1: Create New Schema
```bash
mysql -u root -p your_database < 001_create_schema.sql
```

### Step 2: Migrate Data
```bash
mysql -u root -p your_database < 002_migrate_data.sql
```

### Step 3: Verify Migration
```sql
-- Check row counts in new tables
SELECT 'channels' as tbl, COUNT(*) as cnt FROM channels
UNION ALL SELECT 'publish_tasks', COUNT(*) FROM publish_tasks
UNION ALL SELECT 'channel_daily_stats', COUNT(*) FROM channel_daily_stats;
```

### Step 4: Cleanup (Optional)
Only after verification:
```bash
mysql -u root -p your_database < 003_cleanup_legacy.sql
```
Edit the file to uncomment the DROP statements.

## Rollback Procedures

### Rollback Data Migration
```bash
mysql -u root -p your_database < rollback_002.sql
```

### Rollback Schema Creation
```bash
mysql -u root -p your_database < rollback_001.sql
```

## User Assignment

The migration assigns all existing data to a default admin user. After migration, you can:

1. **Reassign channels to specific users**:
   ```sql
   UPDATE channels SET user_id = ? WHERE id = ?;
   ```

2. **Reassign tasks**:
   ```sql
   UPDATE publish_tasks SET user_id = ? WHERE channel_id IN (SELECT id FROM channels WHERE user_id = ?);
   ```

3. **Update the default admin credentials**:
   ```sql
   UPDATE users 
   SET email = 'your@email.com', password_hash = 'your_hash' 
   WHERE username = 'admin';
   ```

## Troubleshooting

### Foreign Key Errors
If you see FK constraint errors, check that:
- All referenced tables exist
- Data types match between old and new tables
- Run with `SET FOREIGN_KEY_CHECKS = 0;` temporarily

### Duplicate Key Errors
The migration uses `ON DUPLICATE KEY UPDATE` to handle re-runs safely.
If you need a clean slate, run the appropriate rollback script first.

### Missing Data
Check the migration procedures' output messages for which tables were migrated.
Some tables may be empty in your legacy database.

## Support

For issues with migration, check:
1. MySQL error logs
2. Migration procedure output messages
3. Row counts before and after migration
