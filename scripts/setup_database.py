#!/usr/bin/env python3
"""
Setup script for MySQL migration.
"""

import os
import sys
import yaml
import argparse
from pathlib import Path

# Add core directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'core'))

from core.database.sqlite_db import get_database_by_type
from core.database.mysql_db import YouTubeMySQLDatabase


def load_mysql_config(config_file: str = None) -> dict:
    """Load MySQL configuration from file or environment."""
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('mysql', {})
    
    # Fallback to environment variables
    return {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'database': os.getenv('MYSQL_DATABASE', 'content_fabric'),
        'user': os.getenv('MYSQL_USER', 'content_fabric_user'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'charset': 'utf8mb4',
        'collation': 'utf8mb4_unicode_ci'
    }


def setup_mysql_database(config: dict) -> bool:
    """Setup MySQL database and tables."""
    print("🔧 Setting up MySQL database...")
    
    try:
        # Connect to MySQL (without specifying database first)
        mysql_config = config.copy()
        mysql_config.pop('database', None)
        
        import mysql.connector
        from mysql.connector import Error
        
        # Connect to MySQL server
        connection = mysql.connector.connect(**mysql_config)
        cursor = connection.cursor()
        
        # Create database
        database_name = config.get('database', 'content_fabric')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {database_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"✅ Database '{database_name}' created/verified")
        
        # Use the database
        cursor.execute(f"USE {database_name}")
        
        # Read and execute schema
        schema_file = Path(__file__).parent / 'mysql_schema.sql'
        if schema_file.exists():
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            for statement in statements:
                if statement and not statement.startswith('--'):
                    try:
                        cursor.execute(statement)
                    except Error as e:
                        if e.errno == 1061:  # Duplicate key name
                            print(f"⚠️ Index already exists, skipping: {statement[:50]}...")
                            continue
                        else:
                            raise e
            
            connection.commit()
            print("✅ Database schema created successfully")
        else:
            print("⚠️ Schema file not found, creating basic tables...")
            # Create basic tables if schema file is missing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS youtube_channels (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) UNIQUE NOT NULL,
                    channel_id VARCHAR(255) NOT NULL,
                    client_id TEXT NOT NULL,
                    client_secret TEXT NOT NULL,
                    access_token TEXT,
                    refresh_token TEXT,
                    token_expires_at DATETIME,
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS youtube_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    channel_name VARCHAR(255) NOT NULL,
                    token_type VARCHAR(100) NOT NULL,
                    token_value TEXT NOT NULL,
                    expires_at DATETIME,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_name) REFERENCES youtube_channels(name) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            connection.commit()
            print("✅ Basic tables created")
        
        cursor.close()
        connection.close()
        return True
        
    except Error as e:
        print(f"❌ Error setting up MySQL: {e}")
        return False


def test_mysql_connection(config: dict) -> bool:
    """Test MySQL connection."""
    print("🔍 Testing MySQL connection...")
    
    try:
        db = YouTubeMySQLDatabase(config)
        stats = db.get_database_stats()
        print("✅ MySQL connection successful")
        print(f"📊 Database stats: {stats}")
        db.close()
        return True
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return False


def migrate_from_sqlite(sqlite_path: str, mysql_config: dict) -> bool:
    """Migrate data from SQLite to MySQL."""
    print("📦 Starting migration from SQLite to MySQL...")
    
    try:
        # Import and run migration
        from migrate_to_mysql import DatabaseMigrator
        
        migrator = DatabaseMigrator(sqlite_path, mysql_config)
        success = migrator.run_migration()
        
        if success:
            print("🎉 Migration completed successfully!")
        else:
            print("❌ Migration failed!")
        
        return success
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Setup MySQL for Content Fabric")
    parser.add_argument('--config', default='mysql_config.yaml', 
                       help='MySQL configuration file')
    parser.add_argument('--sqlite-path', default='youtube_channels.db', 
                       help='Path to SQLite database to migrate')
    parser.add_argument('--setup-only', action='store_true', 
                       help='Only setup database, skip migration')
    parser.add_argument('--test-only', action='store_true', 
                       help='Only test connection, skip setup')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_mysql_config(args.config)
    
    if not config.get('password'):
        print("❌ MySQL password not provided!")
        print("Set MYSQL_PASSWORD environment variable or update config file")
        sys.exit(1)
    
    # Test connection
    if args.test_only:
        success = test_mysql_connection(config)
        sys.exit(0 if success else 1)
    
    # Setup database
    if not setup_mysql_database(config):
        print("❌ Failed to setup MySQL database")
        sys.exit(1)
    
    # Test connection after setup
    if not test_mysql_connection(config):
        print("❌ MySQL connection test failed after setup")
        sys.exit(1)
    
    # Migrate data if requested
    if not args.setup_only and os.path.exists(args.sqlite_path):
        if not migrate_from_sqlite(args.sqlite_path, config):
            print("❌ Migration failed")
            sys.exit(1)
    elif not args.setup_only:
        print(f"⚠️ SQLite file not found: {args.sqlite_path}")
        print("Skipping migration. You can run migration later with:")
        print(f"python migrate_to_mysql.py --sqlite-path {args.sqlite_path}")
    
    print("🎉 MySQL setup completed successfully!")
    print("\n📝 Next steps:")
    print("1. Set DB_TYPE=mysql in your environment or .env file")
    print("2. Update your application configuration to use MySQL")
    print("3. Test your application with the new MySQL database")


if __name__ == '__main__':
    main()
