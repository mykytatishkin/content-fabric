# Database Migrations

This folder contains all database migration scripts for the Content Fabric project.

## Available Migrations

### 1. Add upload_id to tasks table
**File**: `add_upload_id_migration.py`  
**Purpose**: Adds `upload_id` column to store video IDs after successful uploads

**Run migration:**
```bash
python3 core/database/migrations/scripts/run_migration_upload_id.py
```

or directly:
```bash
python3 core/database/migrations/add_upload_id_migration.py
```

**What it does:**
- Adds `upload_id VARCHAR(255)` column to `tasks` table
- Creates index on `upload_id` for better query performance
- Checks if column already exists (safe to run multiple times)

### 2. Add error_message to tasks table
**File**: `add_error_message_migration.py`  
**Purpose**: Adds `error_message` column to store error details when tasks fail

**Run migration:**
```bash
python3 core/database/migrations/scripts/run_migration_error_message.py
```

or directly:
```bash
python3 core/database/migrations/add_error_message_migration.py
```

**What it does:**
- Adds `error_message TEXT` column to `tasks` table
- Stores error messages for failed tasks
- Enables error categorization in daily reports (Auth, No file, etc.)
- Checks if column already exists (safe to run multiple times)

### 3. Add Google Cloud Console support
**File**: `add_google_consoles_migration.py`  
**Purpose**: Adds support for multiple Google Cloud Console projects to distribute API quota

**Run migration:**
```bash
# Using default config (config/mysql_config.yaml)
python3 core/database/migrations/scripts/run_migration_google_consoles.py

# Or specify custom config file for production
python3 core/database/migrations/scripts/run_migration_google_consoles.py --config config/mysql_config_prod.yaml
```

or directly:
```bash
python3 core/database/migrations/add_google_consoles_migration.py --config config/mysql_config_prod.yaml
```

**What it does:**
- Creates `google_consoles` table to store multiple Google Cloud Console projects
- Adds `console_id` column to `youtube_channels` table
- Enables channels to use different Google Cloud Console projects
- Helps distribute API quota across multiple console projects
- Stores `project_id` and `redirect_uris` from credentials.json
- Checks if tables/columns already exist (safe to run multiple times)

### 4. Add project_id and redirect_uris to google_consoles
**File**: `add_google_consoles_fields_migration.py`  
**Purpose**: Adds `project_id` and `redirect_uris` fields to existing `google_consoles` table

**Run migration:**
```bash
python3 core/database/migrations/scripts/run_migration_google_consoles_fields.py
```

**What it does:**
- Adds `project_id VARCHAR(255)` column to store Google Cloud Project ID
- Adds `redirect_uris JSON` column to store OAuth redirect URIs
- Adds index on `project_id` for better query performance
- Safe to run if fields already exist

## Migration Guidelines

1. All migrations should be idempotent (safe to run multiple times)
2. Always check if changes already exist before applying
3. Include rollback instructions when applicable
4. Test migrations on a backup database first
5. Document what each migration does

## Creating New Migrations

When creating a new migration:

1. Create the migration file in `core/database/migrations/`
2. Follow naming convention: `<description>_migration.py`
3. Create a runner script in `core/database/migrations/scripts/`: `run_migration_<name>.py`
4. Update this README with migration details
5. Test thoroughly before running in production

