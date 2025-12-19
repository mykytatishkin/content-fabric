#!/usr/bin/env python3
"""
Migration script to remove deprecated client_id and client_secret columns
from youtube_channels table.

These columns are no longer needed as credentials are now stored in
google_consoles table and accessed via console_name/console_id.
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


def column_exists(db: YouTubeMySQLDatabase, table_name: str, column_name: str) -> bool:
    """Check whether column exists in the specified table."""
    query = """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """
    result = db._execute_query(query, (table_name, column_name), fetch=True)
    return bool(result and result[0][0])


def check_channels_without_console(db: YouTubeMySQLDatabase) -> int:
    """Check how many channels don't have console_name or console_id set."""
    query = """
        SELECT COUNT(*)
        FROM youtube_channels
        WHERE (console_name IS NULL OR console_name = '')
          AND (console_id IS NULL OR console_id = 0)
    """
    result = db._execute_query(query, fetch=True)
    count = result[0][0] if result else 0
    return count


def remove_client_id_column(db: YouTubeMySQLDatabase) -> None:
    """Remove client_id column from youtube_channels table."""
    if not column_exists(db, "youtube_channels", "client_id"):
        print("ℹ️  Column 'client_id' does not exist in 'youtube_channels'")
        return

    # Check if there are channels without console assignment
    channels_without_console = check_channels_without_console(db)
    if channels_without_console > 0:
        print(f"⚠️  WARNING: Found {channels_without_console} channel(s) without console_name or console_id")
        print("   These channels will not be able to use OAuth credentials after migration.")
        print("   Please assign console_name or console_id to these channels first.")
        response = input("   Continue anyway? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Migration cancelled by user")
            sys.exit(1)

    # Drop the column
    alter_sql = """
        ALTER TABLE youtube_channels
        DROP COLUMN client_id
    """
    try:
        db._execute_query(alter_sql)
        print("✅ Removed column 'client_id' from 'youtube_channels'")
    except Error as e:
        print(f"❌ Failed to remove 'client_id' column: {e}")
        raise


def remove_client_secret_column(db: YouTubeMySQLDatabase) -> None:
    """Remove client_secret column from youtube_channels table."""
    if not column_exists(db, "youtube_channels", "client_secret"):
        print("ℹ️  Column 'client_secret' does not exist in 'youtube_channels'")
        return

    # Drop the column
    alter_sql = """
        ALTER TABLE youtube_channels
        DROP COLUMN client_secret
    """
    try:
        db._execute_query(alter_sql)
        print("✅ Removed column 'client_secret' from 'youtube_channels'")
    except Error as e:
        print(f"❌ Failed to remove 'client_secret' column: {e}")
        raise


def main() -> None:
    """Execute migration."""
    print("=" * 72)
    print("Migration: Remove deprecated client_id and client_secret columns")
    print("=" * 72)
    print()
    print("This migration removes client_id and client_secret columns from")
    print("youtube_channels table. Credentials are now stored in google_consoles")
    print("table and accessed via console_name/console_id.")
    print()

    mysql_config = load_mysql_config()

    try:
        db = YouTubeMySQLDatabase(config=mysql_config)
        print()

        try:
            # Check channels without console
            channels_without_console = check_channels_without_console(db)
            if channels_without_console > 0:
                print(f"⚠️  Found {channels_without_console} channel(s) without console assignment")
                print("   These channels should have console_name or console_id set")
                print("   before removing client_id/client_secret columns.")
                print()

            # Step 1: Remove client_id column
            remove_client_id_column(db)
            
            # Step 2: Remove client_secret column
            remove_client_secret_column(db)
            
        except Error as exc:
            print(f"❌ Migration failed: {exc}")
            sys.exit(1)

        print()
        print("=" * 72)
        print("✅ Migration completed successfully!")
        print("=" * 72)
        print()
        print("Next steps:")
        print("  1. Ensure all channels have console_name or console_id set")
        print("  2. Update code to use get_console_credentials_for_channel()")
        print("  3. Remove any fallback logic for channel.client_id/client_secret")
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

