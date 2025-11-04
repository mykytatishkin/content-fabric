#!/usr/bin/env python3
"""
Migration script to add error_message column to tasks table.
This script adds the error_message field to store error details when tasks fail.
"""

import sys
import os
import yaml

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from core.database.mysql_db import YouTubeMySQLDatabase
from mysql.connector import Error


def load_mysql_config():
    """Load MySQL configuration from yaml file."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        'config',
        'mysql_config.yaml'
    )
    
    if not os.path.exists(config_path):
        print(f"⚠️  MySQL config not found at {config_path}")
        print("Using environment variables or defaults")
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print(f"✅ Loaded MySQL config from {config_path}")
        return config
    except Exception as e:
        print(f"⚠️  Failed to load MySQL config: {e}")
        return None


def add_error_message_column(db: YouTubeMySQLDatabase) -> bool:
    """Add error_message column to tasks table if it doesn't exist."""
    
    try:
        # Check if column already exists
        check_query = """
            SELECT COUNT(*) 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'tasks' 
            AND COLUMN_NAME = 'error_message'
        """
        
        result = db._execute_query(check_query, fetch=True)
        
        if result and result[0][0] > 0:
            print("✅ Column 'error_message' already exists in tasks table")
            return True
        
        # Add the column
        alter_query = """
            ALTER TABLE tasks 
            ADD COLUMN error_message TEXT COMMENT 'Error message when task fails'
        """
        
        db._execute_query(alter_query)
        print("✅ Successfully added 'error_message' column to tasks table")
        
        return True
        
    except Error as e:
        print(f"❌ Error during migration: {e}")
        return False


def main():
    """Run migration."""
    print("=" * 60)
    print("Migration: Add error_message column to tasks table")
    print("=" * 60)
    print()
    
    # Load MySQL configuration
    mysql_config = load_mysql_config()
    
    # Initialize database connection
    try:
        db = YouTubeMySQLDatabase(config=mysql_config)
        print()
        
        # Run migration
        if add_error_message_column(db):
            print()
            print("=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            print()
            print("The 'error_message' field will now store error details")
            print("when tasks fail, allowing for better error categorization.")
            print()
        else:
            print()
            print("=" * 60)
            print("❌ Migration failed!")
            print("=" * 60)
            print()
            sys.exit(1)
        
        db.close()
        
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        print()
        print("Please ensure:")
        print("  1. MySQL server is running")
        print("  2. Database credentials are correct in config/mysql_config.yaml")
        print("  3. Database 'content_fabric' exists")
        sys.exit(1)


if __name__ == "__main__":
    main()

