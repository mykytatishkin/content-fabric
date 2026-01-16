#!/usr/bin/env python3
"""
Migration script to add Google Cloud Console support.
Creates:
  - google_consoles table for storing Google Cloud Console credentials
  - Adds console_name column to youtube_channels table
"""

import sys
import os
import yaml
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.database.mysql_db import YouTubeMySQLDatabase
from mysql.connector import Error


def load_mysql_config() -> Optional[dict]:
    """Load MySQL configuration from config/mysql_config.yaml if present."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "config",
        "mysql_config.yaml",
    )

    if not os.path.exists(config_path):
        print(f"⚠️  MySQL config not found at {config_path}")
        print("Using environment variables or defaults")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
        print(f"✅ Loaded MySQL config from {config_path}")
        return config
    except Exception as exc:
        print(f"⚠️  Failed to load MySQL config: {exc}")
        return None


def table_exists(db: YouTubeMySQLDatabase, table_name: str) -> bool:
    """Check whether table already exists in the current database."""
    query = """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
    """
    result = db._execute_query(query, (table_name,), fetch=True)
    return bool(result and result[0][0])


def column_exists(db: YouTubeMySQLDatabase, table_name: str, column_name: str) -> bool:
    """Check whether column already exists in the specified table."""
    query = """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """
    result = db._execute_query(query, (table_name, column_name), fetch=True)
    return bool(result and result[0][0])


def create_google_consoles_table(db: YouTubeMySQLDatabase) -> None:
    """Create google_consoles table if it does not exist."""
    if table_exists(db, "google_consoles"):
        print("ℹ️  Table 'google_consoles' already exists")
        return

    create_table_sql = """
        CREATE TABLE google_consoles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL COMMENT 'Human-readable name for the console (used as unique identifier)',
            client_id TEXT NOT NULL COMMENT 'OAuth Client ID from Google Cloud Console',
            client_secret TEXT NOT NULL COMMENT 'OAuth Client Secret from Google Cloud Console',
            credentials_file CHAR(500) COMMENT 'Path to credentials.json file (optional)',
            description TEXT COMMENT 'Optional description of the console/project',
            enabled TINYINT(1) DEFAULT 1 COMMENT 'Whether this console is active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_name (name),
            INDEX idx_enabled (enabled)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    db._execute_query(create_table_sql)
    print("✅ Created table 'google_consoles'")


def add_console_name_to_youtube_channels(db: YouTubeMySQLDatabase) -> None:
    """Add console_name column to youtube_channels table if it does not exist."""
    if column_exists(db, "youtube_channels", "console_name"):
        print("ℹ️  Column 'console_name' already exists in 'youtube_channels'")
        return

    # Add console_name column
    add_column_sql = """
        ALTER TABLE youtube_channels
        ADD COLUMN console_name VARCHAR(255) COMMENT 'Reference to google_consoles.name (nullable for backward compatibility)'
        AFTER channel_id
    """
    db._execute_query(add_column_sql)
    print("✅ Added column 'console_name' to 'youtube_channels'")

    # Add index
    add_index_sql = """
        ALTER TABLE youtube_channels
        ADD INDEX idx_console_name (console_name)
    """
    try:
        db._execute_query(add_index_sql)
        print("✅ Added index 'idx_console_name' to 'youtube_channels'")
    except Error as e:
        # Index might already exist
        if "Duplicate key name" not in str(e):
            raise

    # Add foreign key constraint
    add_fk_sql = """
        ALTER TABLE youtube_channels
        ADD CONSTRAINT fk_youtube_channels_console_name
        FOREIGN KEY (console_name) REFERENCES google_consoles(name) ON DELETE SET NULL
    """
    try:
        db._execute_query(add_fk_sql)
        print("✅ Added foreign key constraint 'fk_youtube_channels_console_name'")
    except Error as e:
        # Foreign key might already exist or table might be empty
        if "Duplicate key name" not in str(e) and "Cannot add foreign key constraint" not in str(e):
            print(f"⚠️  Could not add foreign key constraint: {e}")
            print("   This is OK if the table is empty or constraint already exists")


def make_client_id_secret_nullable(db: YouTubeMySQLDatabase) -> None:
    """Make client_id and client_secret nullable in youtube_channels for backward compatibility."""
    try:
        # Check current nullability
        query = """
            SELECT IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'youtube_channels'
              AND COLUMN_NAME = 'client_id'
        """
        result = db._execute_query(query, fetch=True)
        if result and result[0][0] == 'NO':
            # Make client_id nullable
            alter_sql = """
                ALTER TABLE youtube_channels
                MODIFY COLUMN client_id TEXT COMMENT 'Deprecated: use google_consoles.client_id instead (kept for backward compatibility)'
            """
            db._execute_query(alter_sql)
            print("✅ Made 'client_id' nullable in 'youtube_channels'")
        else:
            print("ℹ️  Column 'client_id' is already nullable")
    except Error as e:
        print(f"⚠️  Could not modify 'client_id': {e}")

    try:
        # Check current nullability
        query = """
            SELECT IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'youtube_channels'
              AND COLUMN_NAME = 'client_secret'
        """
        result = db._execute_query(query, fetch=True)
        if result and result[0][0] == 'NO':
            # Make client_secret nullable
            alter_sql = """
                ALTER TABLE youtube_channels
                MODIFY COLUMN client_secret TEXT COMMENT 'Deprecated: use google_consoles.client_secret instead (kept for backward compatibility)'
            """
            db._execute_query(alter_sql)
            print("✅ Made 'client_secret' nullable in 'youtube_channels'")
        else:
            print("ℹ️  Column 'client_secret' is already nullable")
    except Error as e:
        print(f"⚠️  Could not modify 'client_secret': {e}")


def main() -> None:
    """Execute migration."""
    print("=" * 72)
    print("Migration: Add Google Cloud Console support")
    print("=" * 72)
    print()

    mysql_config = load_mysql_config()

    try:
        db = YouTubeMySQLDatabase(config=mysql_config)
        print()

        try:
            # Step 1: Create google_consoles table
            create_google_consoles_table(db)
            
            # Step 2: Add console_name column to youtube_channels
            add_console_name_to_youtube_channels(db)
            
            # Step 3: Make client_id and client_secret nullable for backward compatibility
            make_client_id_secret_nullable(db)
            
        except Error as exc:
            print(f"❌ Migration failed: {exc}")
            sys.exit(1)

        print()
        print("=" * 72)
        print("✅ Migration completed successfully!")
        print("=" * 72)
        print()
        print("Next steps:")
        print("  1. Add Google Console configurations using:")
        print("     db.add_google_console(name='main', client_id='...', client_secret='...')")
        print("  2. Update YouTube channels to use console_name:")
        print("     UPDATE youtube_channels SET console_name='main' WHERE name='channel_name'")
        print()
        db.close()
    except Exception as exc:
        print(f"❌ Failed to connect to database: {exc}")
        print()
        print("Please ensure:")
        print("  1. MySQL server is running")
        print("  2. Database credentials are correct in config/mysql_config.yaml or environment")
        print("  3. Database 'content_fabric' exists")
        sys.exit(1)


if __name__ == "__main__":
    main()

