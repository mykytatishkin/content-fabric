#!/usr/bin/env python3
"""
Migration script to add support for multiple Google Cloud Console projects.
Creates:
  - google_consoles table (stores console credentials)
  - Adds console_id column to youtube_channels table
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
        
        # Config file has data at root level, not under 'mysql' key
        # But also check for 'mysql' key for compatibility
        if isinstance(config, dict):
            if 'mysql' in config:
                mysql_config = config['mysql']
            else:
                # Data is at root level
                mysql_config = config
            
            # Ensure all required fields are present
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


def create_google_consoles_table(db: YouTubeMySQLDatabase) -> None:
    """Create google_consoles table if it does not exist."""
    if table_exists(db, "google_consoles"):
        print("ℹ️  Table 'google_consoles' already exists")
        # Verify the table structure
        try:
            result = db._execute_query("SELECT COUNT(*) FROM google_consoles", fetch=True)
            if result:
                print(f"   Table contains {result[0][0]} records")
        except Exception as e:
            print(f"⚠️  Warning: Could not verify table structure: {e}")
        return

    create_table_sql = """
        CREATE TABLE IF NOT EXISTS google_consoles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL COMMENT 'Human-readable name for the console',
            project_id VARCHAR(255) COMMENT 'Google Cloud Project ID (from credentials.json)',
            client_id TEXT NOT NULL COMMENT 'OAuth Client ID from Google Cloud Console',
            client_secret TEXT NOT NULL COMMENT 'OAuth Client Secret from Google Cloud Console',
            credentials_file VARCHAR(500) COMMENT 'Path to credentials.json file (optional)',
            redirect_uris JSON COMMENT 'OAuth redirect URIs from credentials.json',
            description TEXT COMMENT 'Optional description of the console/project',
            enabled BOOLEAN DEFAULT TRUE COMMENT 'Whether this console is active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_name (name),
            INDEX idx_project_id (project_id),
            INDEX idx_enabled (enabled)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    try:
        db._execute_query(create_table_sql)
        # Verify table was created
        if table_exists(db, "google_consoles"):
            print("✅ Created table 'google_consoles'")
        else:
            print("❌ Failed to create table 'google_consoles' - table does not exist after creation")
            raise Exception("Table creation failed")
    except Error as e:
        print(f"❌ Error creating table 'google_consoles': {e}")
        raise


def add_console_id_to_channels(db: YouTubeMySQLDatabase) -> None:
    """Add console_id column to youtube_channels table if it doesn't exist."""
    if column_exists(db, "youtube_channels", "console_id"):
        print("ℹ️  Column 'console_id' already exists in 'youtube_channels'")
        return

    # First, add the column as nullable
    alter_table_sql = """
        ALTER TABLE youtube_channels
        ADD COLUMN console_id INT NULL COMMENT 'Reference to google_consoles.id'
    """

    try:
        db._execute_query(alter_table_sql)
        # Verify column was added
        if column_exists(db, "youtube_channels", "console_id"):
            print("✅ Added 'console_id' column to 'youtube_channels' table")
        else:
            print("❌ Failed to add 'console_id' column - column does not exist after creation")
            raise Exception("Column creation failed")
    except Error as e:
        if e.errno == 1060:  # Duplicate column name
            print("ℹ️  Column 'console_id' already exists in 'youtube_channels'")
        else:
            print(f"❌ Error adding 'console_id' column: {e}")
            raise
    
    # Add index separately (might already exist)
    try:
        index_sql = "ALTER TABLE youtube_channels ADD INDEX idx_console_id (console_id)"
        db._execute_query(index_sql)
        print("✅ Added index for 'console_id' column")
    except Error as e:
        if "Duplicate key name" in str(e) or e.errno == 1061:
            print("ℹ️  Index 'idx_console_id' already exists")
        else:
            print(f"⚠️  Could not add index: {e}")

    # Add foreign key constraint
    try:
        add_fk_sql = """
            ALTER TABLE youtube_channels
            ADD CONSTRAINT fk_youtube_channels_console_id
            FOREIGN KEY (console_id) REFERENCES google_consoles(id) ON DELETE SET NULL
        """
        db._execute_query(add_fk_sql)
        print("✅ Added foreign key constraint for 'console_id'")
    except Error as e:
        # Foreign key might fail if there are existing channels without valid console_id
        # This is okay, we'll handle it gracefully
        print(f"⚠️  Could not add foreign key constraint: {e}")
        print("   This is normal if there are existing channels. You can add the constraint later.")


def main() -> None:
    """Execute migration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Add Google Cloud Console support migration")
    parser.add_argument('--config', type=str, default=None,
                       help='Path to MySQL config file (default: config/mysql_config.yaml)')
    args = parser.parse_args()
    
    print("=" * 72)
    print("Migration: Add Google Cloud Console support")
    print("=" * 72)
    print()

    # Load config from specified file or default
    if args.config:
        config_path = args.config
        if not os.path.exists(config_path):
            print(f"❌ Config file not found: {config_path}")
            sys.exit(1)
        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                config = yaml.safe_load(config_file)
            if isinstance(config, dict):
                if 'mysql' in config:
                    mysql_config = config['mysql']
                else:
                    mysql_config = config
                required_fields = ['host', 'port', 'database', 'user', 'password']
                if not all(field in mysql_config for field in required_fields):
                    print(f"❌ Config file missing required fields")
                    sys.exit(1)
                print(f"✅ Loaded MySQL config from {config_path}")
            else:
                print(f"❌ Invalid config format")
                sys.exit(1)
        except Exception as exc:
            print(f"❌ Failed to load config: {exc}")
            sys.exit(1)
    else:
        # Load from env vars or config file
        mysql_config = load_mysql_config()

    if not mysql_config:
        print("❌ MySQL configuration not found!")
        print("Please provide --config parameter or ensure config/mysql_config.yaml exists")
        sys.exit(1)
    
    # Show which database we're connecting to
    print(f"📊 Connecting to: {mysql_config.get('host')}:{mysql_config.get('port')}/{mysql_config.get('database')}")
    print()
    
    try:
        db = YouTubeMySQLDatabase(config=mysql_config)
        print()

        try:
            # Create google_consoles table first
            create_google_consoles_table(db)
            
            # Add console_id to youtube_channels
            add_console_id_to_channels(db)
            
        except Error as exc:
            print(f"❌ Migration failed: {exc}")
            sys.exit(1)

        print()
        print("=" * 72)
        print("✅ Migration completed successfully!")
        print("=" * 72)
        print()
        print("Next steps:")
        print("  1. Add Google Cloud Console projects using:")
        print("     python scripts/account_manager.py console add <name> <client_id> <client_secret>")
        print("  2. Update existing channels to use a console:")
        print("     python scripts/account_manager.py channel set-console <channel_name> <console_name>")
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

