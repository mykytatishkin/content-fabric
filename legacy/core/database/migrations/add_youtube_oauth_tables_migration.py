#!/usr/bin/env python3
"""
Migration script to create tables required for automated YouTube OAuth re-authentication.
Creates:
  - youtube_account_credentials
  - youtube_reauth_audit
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


def create_youtube_account_credentials(db: YouTubeMySQLDatabase) -> None:
    """Create youtube_account_credentials table if it does not exist."""
    if table_exists(db, "youtube_account_credentials"):
        print("ℹ️  Table 'youtube_account_credentials' already exists")
        return

    create_table_sql = """
        CREATE TABLE youtube_account_credentials (
            id INT AUTO_INCREMENT PRIMARY KEY,
            channel_name VARCHAR(255) NOT NULL,
            login_email VARCHAR(320) NOT NULL,
            login_password TEXT NOT NULL COMMENT 'Stored in raw form; ensure server access is restricted',
            totp_secret VARCHAR(64),
            backup_codes JSON,
            proxy_host VARCHAR(255),
            proxy_port INT,
            proxy_username VARCHAR(255),
            proxy_password VARCHAR(255),
            profile_path VARCHAR(500),
            user_agent VARCHAR(500),
            last_success_at DATETIME,
            last_attempt_at DATETIME,
            last_error TEXT,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_name) REFERENCES youtube_channels(name) ON DELETE CASCADE,
            UNIQUE KEY idx_channel_unique (channel_name),
            INDEX idx_login_email (login_email),
            INDEX idx_enabled (enabled),
            INDEX idx_last_success (last_success_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    db._execute_query(create_table_sql)
    print("✅ Created table 'youtube_account_credentials'")


def create_youtube_reauth_audit(db: YouTubeMySQLDatabase) -> None:
    """Create youtube_reauth_audit table if it does not exist."""
    if table_exists(db, "youtube_reauth_audit"):
        print("ℹ️  Table 'youtube_reauth_audit' already exists")
        return

    create_table_sql = """
        CREATE TABLE youtube_reauth_audit (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            channel_name VARCHAR(255) NOT NULL,
            initiated_at DATETIME NOT NULL,
            completed_at DATETIME,
            status VARCHAR(32) NOT NULL,
            error_message TEXT,
            metadata JSON,
            FOREIGN KEY (channel_name) REFERENCES youtube_channels(name) ON DELETE CASCADE,
            INDEX idx_channel_status (channel_name, status),
            INDEX idx_initiated (initiated_at),
            INDEX idx_completed (completed_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    db._execute_query(create_table_sql)
    print("✅ Created table 'youtube_reauth_audit'")


def main() -> None:
    """Execute migration."""
    print("=" * 72)
    print("Migration: Create YouTube OAuth automation tables")
    print("=" * 72)
    print()

    mysql_config = load_mysql_config()

    try:
        db = YouTubeMySQLDatabase(config=mysql_config)
        print()

        try:
            create_youtube_account_credentials(db)
            create_youtube_reauth_audit(db)
        except Error as exc:
            print(f"❌ Migration failed: {exc}")
            sys.exit(1)

        print()
        print("=" * 72)
        print("✅ Migration completed successfully!")
        print("=" * 72)
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


