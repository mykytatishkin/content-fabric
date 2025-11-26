#!/usr/bin/env python3
"""
Migration script to add project_id and redirect_uris fields to google_consoles table.
Run this if you already have google_consoles table without these fields.
"""

import sys
import os
import yaml
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.database.mysql_db import YouTubeMySQLDatabase
from mysql.connector import Error


def load_mysql_config() -> Optional[dict]:
    """Load MySQL configuration from config/mysql_config.yaml or environment variables."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "config",
        "mysql_config.yaml",
    )

    # First, try to load from environment variables (for production)
    env_config = {
        'host': os.getenv('MYSQL_HOST'),
        'port': os.getenv('MYSQL_PORT'),
        'database': os.getenv('MYSQL_DATABASE'),
        'user': os.getenv('MYSQL_USER'),
        'password': os.getenv('MYSQL_PASSWORD'),
    }
    
    # If all required env vars are set, use them (production mode)
    if all(env_config.values()):
        try:
            mysql_config = {
                'host': env_config['host'],
                'port': int(env_config['port']),
                'database': env_config['database'],
                'user': env_config['user'],
                'password': env_config['password'],
                'charset': 'utf8mb4',
                'collation': 'utf8mb4_unicode_ci',
                'autocommit': True
            }
            print("✅ Loaded MySQL config from environment variables")
            return mysql_config
        except (ValueError, TypeError) as e:
            print(f"⚠️  Invalid environment variables: {e}")
            print("Falling back to config file...")

    # Fallback to config file if env vars not set
    if not os.path.exists(config_path):
        print(f"⚠️  MySQL config not found at {config_path}")
        print("⚠️  Environment variables not set")
        print("Please set MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD")
        return None

    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
        
        if isinstance(config, dict):
            if 'mysql' in config:
                mysql_config = config['mysql']
            else:
                mysql_config = config
            
            required_fields = ['host', 'port', 'database', 'user', 'password']
            if all(field in mysql_config for field in required_fields):
                print(f"✅ Loaded MySQL config from {config_path}")
                return mysql_config
            else:
                print(f"⚠️  MySQL config missing required fields")
                return None
        else:
            print(f"⚠️  Invalid MySQL config format")
            return None
    except Exception as exc:
        print(f"⚠️  Failed to load MySQL config: {exc}")
        return None


def column_exists(db: YouTubeMySQLDatabase, table_name: str, column_name: str) -> bool:
    """Check whether column already exists in the table."""
    query = """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
    """
    result = db._execute_query(query, (table_name, column_name), fetch=True)
    return bool(result and result[0][0])


def add_project_id_column(db: YouTubeMySQLDatabase) -> None:
    """Add project_id column to google_consoles table if it doesn't exist."""
    if column_exists(db, "google_consoles", "project_id"):
        print("ℹ️  Column 'project_id' already exists in 'google_consoles'")
        return

    try:
        alter_table_sql = """
            ALTER TABLE google_consoles
            ADD COLUMN project_id VARCHAR(255) COMMENT 'Google Cloud Project ID (from credentials.json)'
        """
        db._execute_query(alter_table_sql)
        
        # Add index
        try:
            index_sql = "ALTER TABLE google_consoles ADD INDEX idx_project_id (project_id)"
            db._execute_query(index_sql)
            print("✅ Added 'project_id' column and index to 'google_consoles' table")
        except Error as e:
            if "Duplicate key name" in str(e) or e.errno == 1061:
                print("✅ Added 'project_id' column to 'google_consoles' table")
            else:
                print(f"⚠️  Could not add index: {e}")
    except Error as e:
        if e.errno == 1060:  # Duplicate column name
            print("ℹ️  Column 'project_id' already exists in 'google_consoles'")
        else:
            print(f"❌ Error adding 'project_id' column: {e}")
            raise


def add_redirect_uris_column(db: YouTubeMySQLDatabase) -> None:
    """Add redirect_uris column to google_consoles table if it doesn't exist."""
    if column_exists(db, "google_consoles", "redirect_uris"):
        print("ℹ️  Column 'redirect_uris' already exists in 'google_consoles'")
        return

    try:
        alter_table_sql = """
            ALTER TABLE google_consoles
            ADD COLUMN redirect_uris JSON COMMENT 'OAuth redirect URIs from credentials.json'
        """
        db._execute_query(alter_table_sql)
        print("✅ Added 'redirect_uris' column to 'google_consoles' table")
    except Error as e:
        if e.errno == 1060:  # Duplicate column name
            print("ℹ️  Column 'redirect_uris' already exists in 'google_consoles'")
        else:
            print(f"❌ Error adding 'redirect_uris' column: {e}")
            raise


def main() -> None:
    """Execute migration."""
    print("=" * 72)
    print("Migration: Add project_id and redirect_uris to google_consoles")
    print("=" * 72)
    print()

    mysql_config = load_mysql_config()
    
    if not mysql_config:
        print("❌ MySQL configuration not found!")
        print("Please set environment variables or ensure config/mysql_config.yaml exists")
        sys.exit(1)
    
    print(f"📊 Connecting to: {mysql_config.get('host')}:{mysql_config.get('port')}/{mysql_config.get('database')}")
    print()
    
    try:
        db = YouTubeMySQLDatabase(config=mysql_config)
        print()

        try:
            add_project_id_column(db)
            add_redirect_uris_column(db)
            
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
        sys.exit(1)


if __name__ == "__main__":
    main()

